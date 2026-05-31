# =============================================================================
# lated.supervision.alerts.severity_mapper — score -> Severity (concrete)
# =============================================================================
#
# Decides Alert.severity from (score, host_id, path_length).
#
# Two ways to declare a host as critical:
#   - the legacy `critical_asset_ids` set passed at construction (still honored
#     for tests and explicit overrides),
#   - an `is_critical_host` callable, typically a thin closure over the
#     `NetworkTopology` + host registry. This is the path used in production
#     wiring so that "critical" can mean either an explicit host_id, an IP
#     match, or membership in a `sensitive: true` zone.
#
# A host marked critical bumps the severity one rung up the ladder. Same for
# alerts that come from a correlated path of length >= 3.
# =============================================================================

from __future__ import annotations

from typing import Callable

from lated.common.schemas import Severity


_LADDER = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]


class SeverityMapper:
    """Score + context -> Severity enum value."""

    def __init__(
        self,
        critical_asset_ids: set[str] | None = None,
        is_critical_host: Callable[[str], bool] | None = None,
    ):
        self.critical_asset_ids = set(critical_asset_ids or set())
        self._is_critical_host = is_critical_host

    def is_critical(self, host_id: str) -> bool:
        if not host_id:
            return False
        if host_id in self.critical_asset_ids:
            return True
        if self._is_critical_host is not None:
            try:
                return bool(self._is_critical_host(host_id))
            except Exception:
                # Never let an asset lookup failure poison alert dispatch.
                return False
        return False

    def map(self, score: float, host_id: str = "", path_length: int = 0) -> str:
        base = self._base_for(score)
        index = _LADDER.index(base)
        if path_length >= 3:
            index = min(index + 1, len(_LADDER) - 1)
        if self.is_critical(host_id):
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
