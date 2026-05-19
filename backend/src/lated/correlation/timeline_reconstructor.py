# =============================================================================
# lated.correlation.timeline_reconstructor — chronological path narrative
# =============================================================================
#
# Converts an AttackPath into a list of step dicts suitable for the SOC UI:
#
#   {
#     "step": 1,
#     "ts": "<ISO>",
#     "kind": "reconnaissance" | "lateral_movement" | "fusion" | "correlation",
#     "subject_host": "host_x",
#     "target_hosts": ["host_y", ...],
#     "evidence_alert_ids": ["alert-..."],
#     "mitre_tags": ["T1046", ...]
#   }
#
# Deterministic: steps are ordered by Alert.created_at then by alert_id.
# =============================================================================

from __future__ import annotations

from typing import Any

from lated.common.schemas import AttackPath


class TimelineReconstructor:
    """Builds structured step-by-step timelines from an AttackPath."""

    def __init__(self, enable_mitre_tags: bool = True):
        self.enable_mitre_tags = bool(enable_mitre_tags)

    def build(self, path: AttackPath) -> list[dict[str, Any]]:
        sorted_alerts = sorted(
            path.timeline,
            key=lambda alert: (alert.created_at, alert.alert_id),
        )

        host_sequence = list(path.hosts)
        steps: list[dict[str, Any]] = []
        for index, alert in enumerate(sorted_alerts, start=1):
            target_hosts = self._infer_targets(alert.subject_host, host_sequence)
            step = {
                "step": index,
                "ts": alert.created_at.isoformat(),
                "kind": alert.kind,
                "subject_host": alert.subject_host,
                "target_hosts": target_hosts,
                "evidence_alert_ids": [alert.alert_id],
                "mitre_tags": list(alert.mitre_tags) if self.enable_mitre_tags else [],
            }
            steps.append(step)
        return steps

    @staticmethod
    def _infer_targets(subject_host: str, host_sequence: list[str]) -> list[str]:
        if subject_host not in host_sequence:
            return []
        position = host_sequence.index(subject_host)
        return list(host_sequence[position + 1 : position + 2])
