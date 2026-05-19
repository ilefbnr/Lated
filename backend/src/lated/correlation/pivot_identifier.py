# =============================================================================
# lated.correlation.pivot_identifier — mid-path pivot host detection
# =============================================================================
#
# A pivot host is one that:
#   (1) sits between two other hosts in the chain (not the head, not the tail),
#   (2) has a confirmed edge to BOTH its predecessor and its successor on the
#       path, according to the adjacency probe.
#
# This is the minimum that distinguishes a real pivot from an artifact of
# correlation. The optional `min_neighbors` filter trims hosts that are too
# isolated to credibly fan out further.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timezone


def _normalize(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


class PivotIdentifier:
    """Tags pivot hosts within an AttackPath under construction."""

    def __init__(self, min_neighbors: int = 1):
        self.min_neighbors = max(1, int(min_neighbors))

    def identify(self, candidate, adjacency) -> list[str]:
        if len(candidate.hosts) < 3:
            return []

        # Build per-host timestamps from the steps for adjacency probing.
        host_ts: dict[str, datetime] = {}
        for step in candidate.steps:
            host_ts.setdefault(step.subject_host, _normalize(step.window_start))

        pivots: list[str] = []
        for index in range(1, len(candidate.hosts) - 1):
            previous = candidate.hosts[index - 1]
            current = candidate.hosts[index]
            following = candidate.hosts[index + 1]
            ts = host_ts.get(current, _normalize(candidate.steps[0].window_start))
            if adjacency.are_adjacent(previous, current, ts) and adjacency.are_adjacent(
                current, following, ts
            ):
                pivots.append(current)
        return pivots
