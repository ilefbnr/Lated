# =============================================================================
# lated.pipelines.offline.weak_labeler — RedteamEvent -> per-flow labels
# =============================================================================
#
# PURPOSE
# -------
# Projects sparse PicoDomain Red Log events onto the (much larger) flow
# stream. Each flow gets a label ∈ {0, 1, 2} suitable as the supervised
# target for:
#     - Stage 2 : LM classifier head training (target = 1 if label ∈ {2, 3})
#     - Stage 5 : LM Fusion training (y = 1 if any LM_ok flow leaves the
#                  host in this window)
#
# LABEL CONVENTION (matches the design spec)
# ------------------------------------------
#   0  benign            (no Red Log event in scope)
#   1  recon             (phase=="recon" event in scope)
#   2  LM_ok             (phase ∈ LM_PHASES event in scope)
#   3  LM_ko             unused — Red Log doesn't expose success/failure
#   4  c2                unused — beacons are out of scope (per spec)
#
# MATCHING RULES
# --------------
# A flow is labeled `lm` or `recon` if ALL of:
#   - src_ip == event.victim_ip
#   - flow ts ∈ [event.ts - LOOKBACK, event.ts + LOOKAHEAD]
#   - flow's responder is internal (excludes C2 beacons by construction)
#
# DEFAULTS (configurable via constructor)
# ---------------------------------------
#   LM_PHASES       = {"lateral", "credential", "privesc"}
#   RECON_PHASES    = {"recon"}
#   LOOKBACK        = 30 s   (operator-console clock drift tolerance)
#   LOOKAHEAD       = 300 s  (command-to-effect latency upper bound)
#
# CYBERSECURITY REASONING
# -----------------------
# Operator-console timestamps in the Red Log are when the *command was
# issued*, not when the network artefact appeared. A small forward window
# captures execution latency; a tiny backward window absorbs clock drift.
# Restricting to local responders eliminates the easy false-positive of
# labeling beacon traffic as LM.
# =============================================================================

from __future__ import annotations

import bisect
from datetime import datetime, timezone
from typing import Iterable, Iterator

from lated.pipelines.offline.picodomain_parser import RedteamEvent


# --- label codes (kept as ints, not Enum, to match the spec verbatim) ---
LABEL_BENIGN = 0
LABEL_RECON  = 1
LABEL_LM_OK  = 2

_DEFAULT_LM_PHASES    = frozenset({"lateral", "credential", "privesc"})
_DEFAULT_RECON_PHASES = frozenset({"recon"})


def _parse_zeek_ts(ts: str) -> datetime:
    """Parse a Zeek JSON timestamp (`"...Z"` suffix) to a UTC datetime."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


class WeakLabeler:
    """Attach a `label` field to every flow based on Red Log events."""

    def __init__(
        self,
        lm_phases: Iterable[str] = _DEFAULT_LM_PHASES,
        recon_phases: Iterable[str] = _DEFAULT_RECON_PHASES,
        lookback_s: float = 30.0,
        lookahead_s: float = 300.0,
        internal_only: bool = True,
    ):
        self.lm_phases = frozenset(lm_phases)
        self.recon_phases = frozenset(recon_phases)
        self.lookback_s = lookback_s
        self.lookahead_s = lookahead_s
        self.internal_only = internal_only
        # Populated by _index_events:
        self._events_by_ip: dict[str, list[tuple[float, str]]] = {}
        # Counters for visibility:
        self.counts: dict[int, int] = {LABEL_BENIGN: 0, LABEL_RECON: 0, LABEL_LM_OK: 0}

    # ------------------------------------------------------------------ API

    def label(
        self,
        flows: Iterable[dict],
        redteam_events: Iterable[RedteamEvent],
    ) -> Iterator[dict]:
        """
        Yields each input flow dict with two new fields:
            label        : int  (0 / 1 / 2)
            label_reason : str | None  (phase name when labeled, else None)
        """
        self._index_events(redteam_events)

        for rec in flows:
            label, reason = self._classify(rec)
            rec["label"] = label
            rec["label_reason"] = reason
            self.counts[label] = self.counts.get(label, 0) + 1
            yield rec

    # ----------------------------------------------------------- internals

    def _index_events(self, events: Iterable[RedteamEvent]) -> None:
        """Group events by victim_ip, sort by epoch-seconds for bisect."""
        bucket: dict[str, list[tuple[float, str]]] = {}
        for e in events:
            if e.victim_ip is None:
                continue
            if e.phase not in self.lm_phases and e.phase not in self.recon_phases:
                continue
            bucket.setdefault(e.victim_ip, []).append((e.ts.timestamp(), e.phase))
        for ip in bucket:
            bucket[ip].sort(key=lambda x: x[0])
        self._events_by_ip = bucket

    def _classify(self, flow: dict) -> tuple[int, str | None]:
        src_ip = flow.get("id.orig_h")
        if src_ip is None:
            return LABEL_BENIGN, None
        events = self._events_by_ip.get(src_ip)
        if not events:
            return LABEL_BENIGN, None

        # Optionally require the responder to be internal so we don't label
        # beacon traffic.
        if self.internal_only and not flow.get("local_resp", False):
            return LABEL_BENIGN, None

        ts_raw = flow.get("ts")
        if not isinstance(ts_raw, str):
            return LABEL_BENIGN, None
        flow_ts = _parse_zeek_ts(ts_raw).timestamp()

        # Find the rightmost event with event.ts <= flow_ts + lookback (i.e.
        # the event window has started). Then scan forward until window ends.
        # Because per-IP buckets are tiny (≤ 40 events), a linear scan over
        # the bisect-localised slice is fine.
        ts_lo = flow_ts - self.lookahead_s   # event.ts must be >= this
        ts_hi = flow_ts + self.lookback_s    # event.ts must be <= this

        lo = bisect.bisect_left(events,  (ts_lo, ""))
        hi = bisect.bisect_right(events, (ts_hi, "￿"))
        if lo >= hi:
            return LABEL_BENIGN, None

        # Prefer LM label over recon if both match the same flow.
        best_label = LABEL_BENIGN
        best_reason: str | None = None
        for _ts, phase in events[lo:hi]:
            if phase in self.lm_phases and best_label < LABEL_LM_OK:
                best_label, best_reason = LABEL_LM_OK, phase
            elif phase in self.recon_phases and best_label < LABEL_RECON:
                best_label, best_reason = LABEL_RECON, phase
        return best_label, best_reason
