# =============================================================================
# lated.supervision.alerts.severity_mapper — score -> Severity (concrete)
# =============================================================================

from __future__ import annotations

from lated.common.schemas import Severity


_LADDER = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]


class SeverityMapper:
    """Score + context -> Severity enum value."""

    def __init__(self, critical_asset_ids: set[str] | None = None):
        self.critical_asset_ids = set(critical_asset_ids or set())

    def map(self, score: float, host_id: str = "", path_length: int = 0) -> str:
        base = self._base_for(score)
        index = _LADDER.index(base)
        if path_length >= 3:
            index = min(index + 1, len(_LADDER) - 1)
        if host_id in self.critical_asset_ids:
            index = min(index + 1, len(_LADDER) - 1)
        return _LADDER[index].value

    @staticmethod
    def _base_for(score: float) -> Severity:
        if score >= 0.90:
            return Severity.CRITICAL
        if score >= 0.75:
            return Severity.HIGH
        if score >= 0.60:
            return Severity.MEDIUM
        if score >= 0.40:
            return Severity.LOW
        return Severity.INFO
