# =============================================================================
# lated.detection.fusion.risk_scorer — per-host historical risk with decay
# =============================================================================
#
# Linear decay model:
#   decayed = max(0, current - decay_per_hour * elapsed_hours)
#
# On update, we first decay the existing risk to the supplied ts, then take
# the max of decayed-current and the new score. This is the deterministic,
# bounded-to-[0,1] behavior expected by the architecture: suspicion never
# disappears instantly, but it always fades without renewal.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator


class RiskScorer:
    """Per-host risk store with linear time decay."""

    def __init__(self, decay_per_hour: float):
        if decay_per_hour < 0:
            raise ValueError("decay_per_hour must be >= 0")
        self.decay_per_hour = float(decay_per_hour)
        self._risk: dict[str, tuple[float, datetime]] = {}

    def update(self, host: str, score: float, ts: datetime) -> float:
        ts = self._to_utc(ts)
        score = self._clamp(score)
        decayed = self._decayed(host, ts)
        new_risk = max(decayed, score)
        self._risk[host] = (new_risk, ts)
        return new_risk

    def read(self, host: str, ts: datetime) -> float:
        return self._decayed(host, self._to_utc(ts))

    def snapshot(self, ts: datetime) -> dict[str, float]:
        ts = self._to_utc(ts)
        return {host: self._decayed(host, ts) for host in self._risk}

    def hosts(self) -> Iterator[str]:
        return iter(self._risk)

    def _decayed(self, host: str, ts: datetime) -> float:
        if host not in self._risk:
            return 0.0
        previous_score, previous_ts = self._risk[host]
        elapsed_hours = max(0.0, (ts - previous_ts).total_seconds() / 3600.0)
        return self._clamp(previous_score - self.decay_per_hour * elapsed_hours)

    @staticmethod
    def _to_utc(ts: datetime) -> datetime:
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

    @staticmethod
    def _clamp(value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return float(value)
