# =============================================================================
# tests/test_graph.py — phase 5 temporal graph coverage
# =============================================================================

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.schemas import CanonicalFlow
from lated.graph.edge_features import EdgeFeatureEngineer
from lated.graph.graph_builder import GraphBuilder
from lated.graph.graph_store import GraphStore
from lated.graph.node_features import NodeFeatureEngineer
from lated.graph.snapshot_manager import SnapshotManager


def _flow(
    flow_id: str,
    ts: datetime,
    src: str,
    dst: str,
    src_port: int = 51200,
    dst_port: int = 445,
    bytes_: int = 1000,
    packets: int = 10,
    duration: float = 1.0,
) -> CanonicalFlow:
    return CanonicalFlow(
        flow_id=flow_id,
        ts=ts,
        src_host=src,
        dst_host=dst,
        src_port=src_port,
        dst_port=dst_port,
        protocol="tcp",
        duration=duration,
        packet_count=packets,
        byte_count=bytes_,
        source_sensor="zeek",
    )


def _flow_stream() -> list[CanonicalFlow]:
    base = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return [
        _flow("f1", base + timedelta(seconds=1), "host-a", "host-b", dst_port=445, bytes_=1000),
        _flow("f2", base + timedelta(seconds=5), "host-a", "host-b", dst_port=445, bytes_=2000),
        _flow("f3", base + timedelta(seconds=10), "host-a", "host-c", dst_port=80, bytes_=500),
        # next window
        _flow("f4", base + timedelta(seconds=31), "host-b", "host-a", dst_port=22, bytes_=800),
        _flow("f5", base + timedelta(seconds=45), "host-a", "host-c", dst_port=443, bytes_=1200),
        # third window — sparse, single host pair
        _flow("f6", base + timedelta(seconds=75), "host-d", "host-e", dst_port=53, bytes_=200),
    ]


def test_snapshot_manager_aligns_windows_to_utc_boundary() -> None:
    mgr = SnapshotManager(window_seconds=30)
    start, end = mgr.window_for(datetime(2024, 1, 1, 0, 0, 17, tzinfo=timezone.utc))
    assert start == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2024, 1, 1, 0, 0, 30, tzinfo=timezone.utc)


def test_snapshot_windows_are_non_overlapping() -> None:
    builder = GraphBuilder(window_seconds=30)
    snapshots = builder.run(_flow_stream())
    assert len(snapshots) >= 2
    for previous, current in zip(snapshots, snapshots[1:]):
        assert previous.window_end <= current.window_start
        assert previous.window_end != current.window_end


def test_graph_builder_replay_is_deterministic() -> None:
    a = GraphBuilder(window_seconds=30).run(_flow_stream())
    b = GraphBuilder(window_seconds=30).run(_flow_stream())
    assert [snap.snapshot_id for snap in a] == [snap.snapshot_id for snap in b]
    assert [snap.model_dump(mode="json") for snap in a] == [
        snap.model_dump(mode="json") for snap in b
    ]


def test_graph_builder_window_aggregates_edges_and_features() -> None:
    snapshots = GraphBuilder(window_seconds=30).run(_flow_stream())
    first = snapshots[0]
    assert ("host-a", "host-b") in first.edges
    assert ("host-a", "host-c") in first.edges
    ab = first.edge_features["host-a->host-b"]
    assert ab.bytes == 3000.0
    assert ab.packets == 20.0
    assert ab.fan_out == 2.0  # host-a has two distinct destinations in this window
    # host-a is source for two destinations -> NodeFeatures.fan_out == 2
    assert first.node_features["host-a"].fan_out == 2.0
    assert first.node_features["host-a"].unique_neighbors == 2
    assert first.node_features["host-a"].historical_risk == 0.0


def test_graph_builder_temporal_delta_uses_previous_window_only() -> None:
    snapshots = GraphBuilder(window_seconds=30).run(_flow_stream())
    first = snapshots[0]
    second = snapshots[1]
    # First occurrence of host-a -> host-b has no prior history.
    assert first.edge_features["host-a->host-b"].temporal_delta == 0.0
    # Second window has host-a -> host-c again; delta > 0.
    assert second.edge_features["host-a->host-c"].temporal_delta > 0.0


def test_edge_engineer_handles_empty_window_gracefully() -> None:
    feats = EdgeFeatureEngineer().compute(
        flows=[], fan_out=0, fan_in=0, previous_seen_ts=None
    )
    assert feats.bytes == 0.0 and feats.port_entropy == 0.0
    assert feats.temporal_delta == 0.0


def test_node_engineer_zero_history_for_unknown_host() -> None:
    feats = NodeFeatureEngineer().compute(
        host_id="host-x",
        out_neighbors=set(),
        in_neighbors=set(),
        flow_count=0,
        window_seconds=30,
    )
    assert feats.fan_out == 0.0
    assert feats.communication_frequency == 0.0
    assert feats.historical_risk == 0.0


def test_node_engineer_uses_injected_history_store() -> None:
    class _Store:
        def risk_for(self, host_id: str) -> float:
            return 0.5 if host_id == "host-a" else 0.0

    feats = NodeFeatureEngineer(history_store=_Store()).compute(
        host_id="host-a",
        out_neighbors={"host-b"},
        in_neighbors=set(),
        flow_count=2,
        window_seconds=30,
    )
    assert feats.historical_risk == 0.5
    assert feats.communication_frequency == 2 / 30


def test_graph_store_save_load_roundtrip(tmp_path) -> None:
    store = GraphStore(tmp_path / "graph.sqlite3")
    snapshots = GraphBuilder(window_seconds=30, store=store).run(_flow_stream())
    assert store.count() == len(snapshots)

    first = snapshots[0]
    reloaded = store.load(first.window_start)
    assert reloaded == first


def test_graph_store_query_window_returns_expected(tmp_path) -> None:
    store = GraphStore(tmp_path / "graph.sqlite3")
    snapshots = GraphBuilder(window_seconds=30, store=store).run(_flow_stream())

    window_start = snapshots[0].window_start
    window_end = snapshots[-1].window_end
    result = store.query_window(window_start, window_end)
    assert [snap.snapshot_id for snap in result] == [snap.snapshot_id for snap in snapshots]


def test_graph_store_query_host_filters_by_membership(tmp_path) -> None:
    store = GraphStore(tmp_path / "graph.sqlite3")
    snapshots = GraphBuilder(window_seconds=30, store=store).run(_flow_stream())
    window_start = snapshots[0].window_start
    window_end = snapshots[-1].window_end

    host_d_snaps = store.query_host("host-d", window_start, window_end)
    host_a_snaps = store.query_host("host-a", window_start, window_end)

    # host-d only appears in the third window
    assert len(host_d_snaps) == 1
    # host-a appears in the first two windows
    assert len(host_a_snaps) == 2


def test_graph_store_save_is_idempotent_under_replay(tmp_path) -> None:
    store = GraphStore(tmp_path / "graph.sqlite3")
    GraphBuilder(window_seconds=30, store=store).run(_flow_stream())
    count_after_first = store.count()
    GraphBuilder(window_seconds=30, store=store).run(_flow_stream())
    assert store.count() == count_after_first


def test_graph_builder_includes_baseline_nodes_when_seeded() -> None:
    builder = GraphBuilder(window_seconds=30, baseline_node_ids={"host-baseline-only"})
    snapshots = builder.run(_flow_stream())
    assert "host-baseline-only" in snapshots[0].nodes
    # baseline host has no observed flows -> features remain at zero
    feats = snapshots[0].node_features["host-baseline-only"]
    assert feats.fan_out == 0.0
    assert feats.fan_in == 0.0
