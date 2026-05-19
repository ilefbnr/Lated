# =============================================================================
# lated.graph.graph_builder — CanonicalFlow -> TemporalSnapshot orchestrator
# =============================================================================
#
# Consumes a (sync) stream of CanonicalFlow records and emits one
# TemporalSnapshot per closed window. Windows are non-overlapping and aligned
# by SnapshotManager. Late flows beyond `tolerance_seconds` are dropped with
# a counter — never attributed retroactively (would break non-overlap).
#
# Determinism guarantees:
#   - nodes and edges are sorted before emission,
#   - dict keys are stringified deterministically,
#   - feature aggregations are sum/Counter based (order-independent),
#   - replay state (last seen ts per edge) is only updated AFTER the window
#     using it has been finalized.
# =============================================================================

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable, Iterator

from lated.common.schemas import CanonicalFlow, TemporalSnapshot

from lated.graph.edge_features import EdgeFeatureEngineer
from lated.graph.graph_store import GraphStore
from lated.graph.node_features import NodeFeatureEngineer
from lated.graph.snapshot_manager import SnapshotManager


class GraphBuilderMetrics:
    """Tiny counter bag for replay observability."""

    def __init__(self) -> None:
        self.windows_emitted = 0
        self.flows_consumed = 0
        self.flows_dropped_late = 0


class GraphBuilder:
    """Builds TemporalSnapshots from a CanonicalFlow stream."""

    def __init__(
        self,
        window_seconds: int,
        store: GraphStore | None = None,
        feature_set: Iterable[str] | None = None,
        node_history_store=None,
        baseline_node_ids: Iterable[str] | None = None,
        tolerance_seconds: int = 5,
    ):
        self.snapshot_manager = SnapshotManager(window_seconds, tolerance_seconds=tolerance_seconds)
        self.edge_engineer = EdgeFeatureEngineer(feature_set=feature_set)
        self.node_engineer = NodeFeatureEngineer(history_store=node_history_store)
        self.store = store
        self.baseline_node_ids: set[str] = set(baseline_node_ids or ())
        self.metrics = GraphBuilderMetrics()
        self._last_seen_edge: dict[tuple[str, str], datetime] = {}

    def build(self, flows: Iterable[CanonicalFlow]) -> Iterator[TemporalSnapshot]:
        current_start: datetime | None = None
        buffer: list[CanonicalFlow] = []

        for flow in flows:
            self.metrics.flows_consumed += 1
            start, _ = self.snapshot_manager.window_for(flow.ts)

            if current_start is None:
                current_start = start

            if start < current_start:
                if self.snapshot_manager.is_late(current_start, flow.ts):
                    self.metrics.flows_dropped_late += 1
                    continue
                # within tolerance — attribute to current window
                buffer.append(flow)
                continue

            if start > current_start:
                snapshot = self._finalize(current_start, buffer)
                yield snapshot
                buffer = []
                current_start = start

            buffer.append(flow)

        if current_start is not None and buffer:
            yield self._finalize(current_start, buffer)

    def run(self, flows: Iterable[CanonicalFlow]) -> list[TemporalSnapshot]:
        return list(self.build(flows))

    def _finalize(self, window_start: datetime, flows: list[CanonicalFlow]) -> TemporalSnapshot:
        _, window_end = self.snapshot_manager.window_for(window_start)

        edge_flows: dict[tuple[str, str], list[CanonicalFlow]] = defaultdict(list)
        out_neighbors: dict[str, set[str]] = defaultdict(set)
        in_neighbors: dict[str, set[str]] = defaultdict(set)
        host_flow_count: dict[str, int] = defaultdict(int)

        for flow in flows:
            edge = (flow.src_host, flow.dst_host)
            edge_flows[edge].append(flow)
            out_neighbors[flow.src_host].add(flow.dst_host)
            in_neighbors[flow.dst_host].add(flow.src_host)
            host_flow_count[flow.src_host] += 1
            host_flow_count[flow.dst_host] += 1

        nodes = sorted(set(out_neighbors.keys()) | set(in_neighbors.keys()) | self.baseline_node_ids)
        edges = sorted(edge_flows.keys())

        edge_features = {}
        for edge in edges:
            src, dst = edge
            fan_out = len(out_neighbors.get(src, ()))
            fan_in = len(in_neighbors.get(dst, ()))
            previous_ts = self._last_seen_edge.get(edge)
            edge_features[f"{src}->{dst}"] = self.edge_engineer.compute(
                edge_flows[edge],
                fan_out=fan_out,
                fan_in=fan_in,
                previous_seen_ts=previous_ts,
            )

        node_features = {}
        for host_id in nodes:
            node_features[host_id] = self.node_engineer.compute(
                host_id=host_id,
                out_neighbors=out_neighbors.get(host_id, set()),
                in_neighbors=in_neighbors.get(host_id, set()),
                flow_count=host_flow_count.get(host_id, 0),
                window_seconds=self.snapshot_manager.window_seconds,
            )

        snapshot = TemporalSnapshot(
            snapshot_id=SnapshotManager.snapshot_id(window_start),
            window_start=window_start,
            window_end=window_end,
            nodes=nodes,
            edges=edges,
            edge_features=edge_features,
            node_features=node_features,
        )

        # update replay state AFTER emission so it never leaks into the
        # window being finalized
        for edge, edge_flow_list in edge_flows.items():
            self._last_seen_edge[edge] = max(flow.ts for flow in edge_flow_list)

        if self.store is not None:
            self.store.save(snapshot)
        self.metrics.windows_emitted += 1
        return snapshot
