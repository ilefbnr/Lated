# =============================================================================
# lated.correlation.graph_adjacency — read-only adjacency probe
# =============================================================================
#
# Tiny shim around graph.GraphStore so correlation never queries snapshots
# directly. Adjacency is checked over a lookback window around the candidate
# event timestamp — recent enough to be relevant, broad enough to absorb the
# 30-second snapshot grain.
#
# Tests can substitute this with a plain dict-based adjacency provider — both
# expose `are_adjacent(a, b, ts) -> bool`.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _normalize(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


class GraphAdjacency:
    """Reads adjacency from a GraphStore. Read-only."""

    def __init__(self, graph_store, lookback_seconds: int = 300):
        self.graph_store = graph_store
        self.lookback = timedelta(seconds=int(lookback_seconds))

    def are_adjacent(self, host_a: str, host_b: str, ts: datetime) -> bool:
        if host_a == host_b:
            return True
        when = _normalize(ts)
        snapshots = self.graph_store.query_window(when - self.lookback, when + self.lookback)
        for snapshot in snapshots:
            edges = snapshot.edges
            if (host_a, host_b) in edges or (host_b, host_a) in edges:
                return True
        return False


class StaticAdjacency:
    """In-memory adjacency, useful for tests and seeded baselines."""

    def __init__(self, edges: list[tuple[str, str]] | None = None):
        self._edges: set[tuple[str, str]] = set()
        for src, dst in edges or []:
            self.add(src, dst)

    def add(self, src: str, dst: str) -> None:
        self._edges.add((src, dst))
        self._edges.add((dst, src))

    def are_adjacent(self, host_a: str, host_b: str, ts: datetime) -> bool:
        del ts  # static — no time relevance
        if host_a == host_b:
            return True
        return (host_a, host_b) in self._edges
