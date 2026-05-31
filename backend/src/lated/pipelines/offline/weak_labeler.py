# =============================================================================
# lated.pipelines.offline.weak_labeler — RedteamEvent -> per-flow binary label
# =============================================================================
#
# PURPOSE
# -------
# Projects sparse PicoDomain Red Log events onto the (much larger) flow
# stream. Each flow gets a BINARY label suitable as the supervised target
# for the LM classifier head (Stage 2) and downstream fusion (Stage 5).
#
# LABEL CONVENTION (binary)
# -------------------------
#   0  benign   (no LM event in scope — includes recon events, ignored here)
#   1  LM       (phase ∈ LM_PHASES event in scope)
#
# Recon events are NOT used as a supervised target: in this codebase recon
# is detected by the online heuristic head (sliding_window / burst /
# fanout / port_diversity) rather than by the TGN head. Folding recon into
# `benign` keeps the supervised signal pure (LM-vs-not-LM) and avoids
# teaching the head to confuse the two phases.
#
# MATCHING RULES
# --------------
# A flow is labeled 1 (LM) if ALL of:
#   - src_ip == event.victim_ip
#   - flow ts ∈ [event.ts - LOOKBACK, event.ts + LOOKAHEAD]
#   - flow's responder is internal (excludes C2 beacons by construction)
#
# DEFAULTS (configurable via constructor)
# ---------------------------------------
#   LM_PHASES       = {"lateral", "credential", "privesc"}
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
from datetime import datetime
from typing import Iterable, Iterator

from lated.pipelines.offline.picodomain_parser import RedteamEvent


# --- binary label codes -------------------------------------------------
LABEL_BENIGN = 0
LABEL_LM     = 1

_DEFAULT_LM_PHASES = frozenset({"lateral", "credential", "privesc"})


def _parse_zeek_ts(ts: str) -> datetime:
    """Parse a Zeek JSON timestamp (`"...Z"` suffix) to a UTC datetime."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


class WeakLabeler:
    """Attach a binary `label` field to every flow based on Red Log events."""

    def __init__(
        self,
        lm_phases: Iterable[str] = _DEFAULT_LM_PHASES,
        lookback_s: float = 30.0,
        lookahead_s: float = 300.0,
        internal_only: bool = True,
    ):
        self.lm_phases = frozenset(lm_phases)
        self.lookback_s = lookback_s
        self.lookahead_s = lookahead_s
        self.internal_only = internal_only
        # Populated by _index_events:
        self._events_by_ip: dict[str, list[tuple[float, str]]] = {}
        # Counters for visibility:
        self.counts: dict[int, int] = {LABEL_BENIGN: 0, LABEL_LM: 0}

    # ------------------------------------------------------------------ API

    def label(
        self,
        flows: Iterable[dict],
        redteam_events: Iterable[RedteamEvent],
    ) -> Iterator[dict]:
        """
        Yields each input flow dict with two new fields:
            label        : int  (0 benign / 1 LM)
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
        """Group LM events by victim_ip, sort by epoch-seconds for bisect."""
        bucket: dict[str, list[tuple[float, str]]] = {}
        for e in events:
            if e.victim_ip is None:
                continue
            if e.phase not in self.lm_phases:
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

        ts_lo = flow_ts - self.lookahead_s   # event.ts must be >= this
        ts_hi = flow_ts + self.lookback_s    # event.ts must be <= this

        lo = bisect.bisect_left(events,  (ts_lo, ""))
        hi = bisect.bisect_right(events, (ts_hi, "￿"))
        if lo >= hi:
            return LABEL_BENIGN, None

        # Any LM event in window flips the flow to LM. Reason = first match.
        for _ts, phase in events[lo:hi]:
            return LABEL_LM, phase
        return LABEL_BENIGN, None
