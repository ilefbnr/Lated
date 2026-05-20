# =============================================================================
# lated.ingestion.zeek_parser — Zeek conn.log replay (JSON Lines)
# =============================================================================
#
# MVP scope:
#   - replay-friendly single-pass read of `conn.log*` files in a directory,
#   - JSON Lines format only (one JSON object per line; the Zeek JSON output
#     mode emits this natively),
#   - malformed lines are skipped silently with a `skipped` counter; the
#     stream keeps going.
#
# Out of scope here: live tailing with rotation, TSV header parsing, and
# stateful resume-from-offset.
# =============================================================================

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterator


CONN_LOG_GLOB = "conn*.log"


class ZeekParser:
    """Yields raw Zeek conn.log records from a directory of JSON files."""

    def __init__(
        self,
        log_dir: str | Path,
        mode: str = "replay",
        poll_interval_seconds: float = 0.5,
        max_idle_seconds: float = 5.0,
        replay_speed: float = 1.0,
    ):
        self.log_dir = Path(log_dir)
        self.mode = str(mode)
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.max_idle_seconds = float(max_idle_seconds)
        # replay_speed only used in mode == "replay_live": N means N seconds of
        # archived Zeek time per 1 second of wall-clock time. N=60 → 1 min real
        # = 60 min of logs. Must be > 0; clamped silently otherwise.
        self.replay_speed = float(replay_speed) if float(replay_speed) > 0 else 1.0
        self.skipped = 0

    def records(self) -> Iterator[dict]:
        if not self.log_dir.exists() or not self.log_dir.is_dir():
            raise FileNotFoundError(f"Zeek log directory not found: {self.log_dir}")

        if self.mode == "live":
            yield from self._tail_live_directory()
            return

        if self.mode == "replay_live":
            yield from self._replay_paced()
            return

        for log_path in sorted(self.log_dir.glob(CONN_LOG_GLOB)):
            with log_path.open("r", encoding="utf-8") as handle:
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
                    yield record

    def _replay_paced(self) -> Iterator[dict]:
        # Replays archived conn*.log files in timestamp order, pacing emission
        # so wall-clock progresses at (replay_speed)× archived-time. The first
        # record establishes the anchor; subsequent records sleep for
        # max(0, (ts - first_ts)/speed - elapsed) before being yielded.
        wall_start = time.monotonic()
        archived_anchor: float | None = None

        for log_path in sorted(self.log_dir.glob(CONN_LOG_GLOB)):
            with log_path.open("r", encoding="utf-8") as handle:
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

                    ts_value = record.get("ts")
                    try:
                        archived_ts = float(ts_value) if ts_value is not None else None
                    except (TypeError, ValueError):
                        archived_ts = None

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

    def _tail_live_directory(self) -> Iterator[dict]:
        offsets: dict[Path, int] = {}
        idle_since = time.monotonic()
        while True:
            emitted = False
            for log_path in sorted(self.log_dir.glob(CONN_LOG_GLOB)):
                current_offset = offsets.get(log_path, 0)
                size = log_path.stat().st_size
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
                        emitted = True
                        yield record
                    offsets[log_path] = handle.tell()
            if emitted:
                idle_since = time.monotonic()
                continue
            if time.monotonic() - idle_since >= self.max_idle_seconds:
                return
            time.sleep(self.poll_interval_seconds)
