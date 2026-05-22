# =============================================================================
# lated.ingestion.zeek_parser — Zeek log replay / tail (JSON Lines)
# =============================================================================
#
# Reads a directory of Zeek JSON-Lines logs. Supports `conn` only (legacy)
# or multiple log types interleaved by `ts` (for live enrichment with
# smb_files / smb_mapping / dce_rpc / ntlm / kerberos).
#
# Modes
# -----
#   replay      single-pass batch read, files in lexicographic order; used
#               by the offline pipeline.
#   replay_live paced read: records yielded so wall-clock advances at
#               (replay_speed)× archived-time. Interleaves all selected
#               log types in ts order (per-hour heap merge).
#   live        tail-on-rotation of growing log files (production Zeek
#               sensor scenario). Polls every poll_interval_seconds.
#
# Each yielded record carries an injected `_zeek_logtype` field so a
# downstream enricher can route it ("conn" → emit; everything else →
# buffer by uid).
# =============================================================================

from __future__ import annotations

import heapq
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


# Default: backwards compatible — only conn.log is read.
DEFAULT_LOG_TYPES = ("conn",)

# Hourly chunk filename: e.g. `conn.13_00_00-14_00_00.log`. The suffix is
# what we use to merge enrichment files belonging to the same hour.
_HOURLY_SUFFIX_RE = re.compile(r"^(?P<type>\w+)\.(?P<suffix>\d\d_\d\d_\d\d-\d\d_\d\d_\d\d)\.log$")


def _parse_zeek_ts(value) -> float | None:
    """Zeek emits ts as either a float epoch or an ISO-8601 string. Return
    seconds-since-epoch as float, or None if unparseable."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        # Fast path: pure numeric string.
        try:
            return float(value)
        except ValueError:
            pass
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return None


class ZeekParser:
    """Yields raw Zeek records from a directory of JSON-Lines logs.

    `log_types` selects which log types to read. By default only `conn` —
    pass e.g. `["conn", "smb_files", "ntlm"]` to interleave them.
    """

    def __init__(
        self,
        log_dir: str | Path,
        mode: str = "replay",
        poll_interval_seconds: float = 0.5,
        max_idle_seconds: float = 5.0,
        replay_speed: float = 1.0,
        log_types: list[str] | tuple[str, ...] | None = None,
    ):
        self.log_dir = Path(log_dir)
        self.mode = str(mode)
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.max_idle_seconds = float(max_idle_seconds)
        # replay_speed only used in mode == "replay_live": N means N seconds of
        # archived Zeek time per 1 second of wall-clock time. N=60 → 1 min real
        # = 60 min of logs. Must be > 0; clamped silently otherwise.
        self.replay_speed = float(replay_speed) if float(replay_speed) > 0 else 1.0
        types = tuple(log_types) if log_types else DEFAULT_LOG_TYPES
        # `conn` must always be present — every other log only makes sense
        # when joined to a conn record by uid.
        if "conn" not in types:
            types = ("conn",) + tuple(types)
        self.log_types: tuple[str, ...] = types
        self.skipped = 0

    # ----------------------------------------------------------------- API

    def records(self) -> Iterator[dict]:
        if not self.log_dir.exists() or not self.log_dir.is_dir():
            raise FileNotFoundError(f"Zeek log directory not found: {self.log_dir}")

        if self.mode == "live":
            yield from self._tail_live_directory()
            return

        if self.mode == "replay_live":
            yield from self._replay_paced()
            return

        # Default: offline replay (single pass over conn*.log only — the
        # existing offline pipeline does its own enrichment via ZeekEnricher).
        for log_path in sorted(self.log_dir.glob("conn*.log")):
            for record in self._iter_jsonl(log_path, logtype="conn"):
                yield record

    # ------------------------------------------------------------- helpers

    def _iter_jsonl(self, path: Path, logtype: str) -> Iterator[dict]:
        """Read a Zeek JSONL log file, skipping malformed lines, and tag
        each record with its `_zeek_logtype`."""
        try:
            handle = path.open("r", encoding="utf-8")
        except OSError:
            return
        with handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    self.skipped += 1
                    continue
                if not isinstance(record, dict):
                    self.skipped += 1
                    continue
                record["_zeek_logtype"] = logtype
                yield record

    def _discover_hour_suffixes(self) -> list[str]:
        """Return sorted unique hour suffixes seen across `conn.*.log` files."""
        suffixes: set[str] = set()
        for path in self.log_dir.glob("conn.*.log"):
            match = _HOURLY_SUFFIX_RE.match(path.name)
            if match:
                suffixes.add(match.group("suffix"))
        return sorted(suffixes)

    # ------------------------------------------------------------- replay_live

    def _replay_paced(self) -> Iterator[dict]:
        """Merge-sort all selected log types by ts, paced by replay_speed.

        Strategy: PicoDomain Zeek logs are hour-chunked
        (`conn.HH_MM_SS-HH_MM_SS.log`). For each hour we open one iterator
        per log type and heap-merge them by ts. This bounds peak memory to
        a handful of file handles and one record per stream.
        """
        wall_start = time.monotonic()
        archived_anchor: float | None = None

        for hour_suffix in self._discover_hour_suffixes():
            iters = []
            for logtype in self.log_types:
                path = self.log_dir / f"{logtype}.{hour_suffix}.log"
                if not path.is_file():
                    continue
                iters.append(self._keyed_iter(path, logtype))
            if not iters:
                continue
            for _ts, record in heapq.merge(*iters, key=lambda item: item[0]):
                archived_ts = _parse_zeek_ts(record.get("ts"))
                if archived_ts is not None:
                    if archived_anchor is None:
                        archived_anchor = archived_ts
                    archived_elapsed = max(0.0, archived_ts - archived_anchor)
                    target_wall_elapsed = archived_elapsed / self.replay_speed
                    wall_elapsed = time.monotonic() - wall_start
                    sleep_for = target_wall_elapsed - wall_elapsed
                    if sleep_for > 0:
                        time.sleep(sleep_for)
                yield record

    def _keyed_iter(self, path: Path, logtype: str) -> Iterator[tuple[float, dict]]:
        """Iterator of (ts, record) for heapq.merge. Records with no usable
        ts get +inf so they sort after everything else (rare but safe)."""
        for record in self._iter_jsonl(path, logtype=logtype):
            ts = _parse_zeek_ts(record.get("ts"))
            yield (ts if ts is not None else float("inf"), record)

    # ------------------------------------------------------------- live tail

    def _tail_live_directory(self) -> Iterator[dict]:
        """Tail all selected log types in parallel (production Zeek sensor).

        Loops the watch list every poll_interval_seconds. On each pass we
        emit new lines from every selected log file. Ordering across files
        is best-effort — the downstream enricher uses uid-keyed buffering
        and is tolerant of out-of-order arrivals within a small window.
        """
        offsets: dict[Path, int] = {}
        idle_since = time.monotonic()
        while True:
            emitted = False
            for logtype in self.log_types:
                patterns = [f"{logtype}.log", f"{logtype}*.log"]
                seen: set[Path] = set()
                for pattern in patterns:
                    for log_path in sorted(self.log_dir.glob(pattern)):
                        if log_path in seen:
                            continue
                        seen.add(log_path)
                        current_offset = offsets.get(log_path, 0)
                        try:
                            size = log_path.stat().st_size
                        except OSError:
                            continue
                        if size < current_offset:
                            current_offset = 0
                        with log_path.open("r", encoding="utf-8") as handle:
                            handle.seek(current_offset)
                            for raw_line in handle:
                                line = raw_line.strip()
                                if not line or line.startswith("#"):
                                    continue
                                try:
                                    record = json.loads(line)
                                except json.JSONDecodeError:
                                    self.skipped += 1
                                    continue
                                if not isinstance(record, dict):
                                    self.skipped += 1
                                    continue
                                record["_zeek_logtype"] = logtype
                                emitted = True
                                yield record
                            offsets[log_path] = handle.tell()
            if emitted:
                idle_since = time.monotonic()
                continue
            if time.monotonic() - idle_since >= self.max_idle_seconds:
                return
            time.sleep(self.poll_interval_seconds)
