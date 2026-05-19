# =============================================================================
# lated.graph.node_features — per-node feature engineering
# =============================================================================
#
# Computes NodeFeatures for each host appearing in the current window.
#
# `historical_risk` is read from a tiny injectable interface — anything with a
# `risk_for(host_id) -> float` method works (typically the fusion engine's
# decayed-risk store). When no store is wired, historical_risk = 0.0 — this
# is the explicit safe value, not a faked ML score.
# =============================================================================

from __future__ import annotations

from typing import Protocol

from lated.common.schemas import NodeFeatures


class HistoricalRiskStore(Protocol):
    def risk_for(self, host_id: str) -> float: ...


class _ZeroRiskStore:
    def risk_for(self, host_id: str) -> float:  # noqa: ARG002
        return 0.0


class NodeFeatureEngineer:
    """Compute NodeFeatures from per-node aggregates and an optional risk store."""

    def __init__(self, history_store: HistoricalRiskStore | None = None):
        self.history_store = history_store or _ZeroRiskStore()

    def compute(
        self,
        host_id: str,
        out_neighbors: set[str],
        in_neighbors: set[str],
        flow_count: int,
        window_seconds: int,
    ) -> NodeFeatures:
        fan_out = float(len(out_neighbors))
        fan_in = float(len(in_neighbors))
        unique_neighbors = len(out_neighbors | in_neighbors)
        frequency = float(flow_count) / float(window_seconds) if window_seconds > 0 else 0.0
        risk = float(self.history_store.risk_for(host_id))
        return NodeFeatures(
            fan_out=fan_out,
            fan_in=fan_in,
            unique_neighbors=unique_neighbors,
            communication_frequency=frequency,
            historical_risk=risk,
        )
