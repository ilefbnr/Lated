# =============================================================================
# lated.correlation.propagation_analyzer — propagation metadata
# =============================================================================
#
# Computes a small, explainable propagation envelope per candidate path:
#
#   - host_count            : len(unique hosts on path)
#   - duration_seconds      : last_ts - first_ts (clipped to >= 0)
#   - propagation_velocity  : host_count / max(duration_minutes, eps)
#   - graph_supported_steps : how many consecutive hops are backed by the
#     adjacency probe (this is what stops us from fabricating propagation
#     when adjacency does not back the chain)
#   - propagation_ratio     : graph_supported_steps / max(steps_evaluated, 1)
#
# This is deliberately small: rich propagation analytics belong in a later
# phase. The numbers here are sufficient to drive the timeline and decide
# whether a candidate is "real enough" to emit.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _normalize(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


class PropagationAnalyzer:
    """Computes a small propagation envelope for an attack path candidate."""

    def analyze(self, candidate, adjacency) -> dict[str, Any]:
        hosts = list(candidate.hosts)
        host_count = len(hosts)
        first_ts = _normalize(candidate.first_ts)
        last_ts = _normalize(candidate.last_ts)
        duration_seconds = max(0.0, (last_ts - first_ts).total_seconds())
        velocity = host_count / max(duration_seconds / 60.0, 1e-6)

        graph_supported = 0
        steps_evaluated = max(0, host_count - 1)
        if steps_evaluated > 0:
            host_ts: dict[str, datetime] = {}
            for step in candidate.steps:
                host_ts.setdefault(step.subject_host, _normalize(step.window_start))
            for index in range(steps_evaluated):
                a = hosts[index]
                b = hosts[index + 1]
                ts = host_ts.get(b, last_ts)
                if adjacency.are_adjacent(a, b, ts):
                    graph_supported += 1

        ratio = graph_supported / steps_evaluated if steps_evaluated else 1.0

        return {
            "host_count": host_count,
            "duration_seconds": duration_seconds,
            "propagation_velocity": velocity,
            "graph_supported_steps": graph_supported,
            "propagation_ratio": ratio,
        }
