# =============================================================================
# tests/test_ingestion.py — phase 4 canonical ingestion coverage
# =============================================================================

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.exceptions import IngestionError
from lated.common.schemas import CanonicalFlow
from lated.discovery.host_registry import HostRegistry
from lated.ingestion.canonical_schema import CanonicalSchema
from lated.ingestion.flow_normalizer import FlowNormalizer
from lated.ingestion.flow_store import FlowStore
from lated.ingestion.flow_validator import FlowValidator
from lated.ingestion.ingestion_service import IngestionService
from lated.ingestion.zeek_parser import ZeekParser


ZEEK_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ingestion" / "zeek"


@dataclass(frozen=True)
class _IngestCfg:
    mode: str = "replay"
    source: str = "zeek"
    pcap_interface: str = ""
    pcap_path: str = ""
    zeek_log_dir: str = str(ZEEK_FIXTURE)
    netflow_port: int = 2055
    batch_size: int = 100


def _normalized_sample() -> dict:
    return {
        "flow_id": "flow-test-001",
        "ts": "2024-01-01T00:00:00+00:00",
        "src_host": "host-aaa",
        "dst_host": "host-bbb",
        "src_port": 51200,
        "dst_port": 445,
        "protocol": "tcp",
        "duration": 1.5,
        "packet_count": 10,
        "byte_count": 800,
        "source_sensor": "zeek",
    }


def test_canonical_schema_from_normalized_returns_canonical_flow() -> None:
    flow = CanonicalSchema.from_normalized(_normalized_sample())
    assert isinstance(flow, CanonicalFlow)
    assert flow.flow_id == "flow-test-001"
    assert flow.protocol == "tcp"


def test_canonical_schema_to_storage_and_back_roundtrip() -> None:
    flow = CanonicalSchema.from_normalized(_normalized_sample())
    payload = CanonicalSchema.to_storage(flow)
    assert isinstance(payload["ts"], str)
    reloaded = CanonicalSchema.from_storage(payload)
    assert reloaded == flow


def test_flow_validator_accepts_valid_record() -> None:
    ok, reason = FlowValidator().is_valid(_normalized_sample())
    assert ok and reason is None


def test_flow_validator_rejects_bad_port() -> None:
    record = _normalized_sample()
    record["dst_port"] = 99999
    ok, reason = FlowValidator().is_valid(record)
    assert not ok
    assert reason and reason.startswith("port_range")


def test_flow_validator_rejects_missing_field() -> None:
    record = _normalized_sample()
    record.pop("src_host")
    ok, reason = FlowValidator().is_valid(record)
    assert not ok
    assert reason == "missing_key:src_host"


def test_flow_normalizer_resolves_host_ids() -> None:
    registry = HostRegistry()
    normalizer = FlowNormalizer(registry)
    raw = {
        "ts": 1704067200.0,
        "uid": "C001",
        "id.orig_h": "10.0.0.21",
        "id.orig_p": 51200,
        "id.resp_h": "10.0.0.11",
        "id.resp_p": 445,
        "proto": "tcp",
        "duration": 1.0,
        "orig_pkts": 5,
        "resp_pkts": 5,
        "orig_ip_bytes": 500,
        "resp_ip_bytes": 500,
    }
    normalized = normalizer.normalize(raw, source_sensor="zeek")
    assert normalized["flow_id"] == "C001"
    assert normalized["src_host"].startswith("host-")
    assert normalized["dst_host"].startswith("host-")
    assert normalized["src_host"] != normalized["dst_host"]
    assert normalized["protocol"] == "tcp"
    assert normalized["byte_count"] == 1000


def test_zeek_parser_skips_malformed_lines() -> None:
    parser = ZeekParser(ZEEK_FIXTURE)
    records = list(parser.records())
    assert len(records) == 5
    assert parser.skipped == 1


def test_ingestion_service_replay_yields_canonical_flows() -> None:
    registry = HostRegistry()
    service = IngestionService(_IngestCfg(), registry)
    flows = service.run()
    assert len(flows) == 4  # C001, C002, C003, C005 — C004 has invalid port
    assert all(isinstance(flow, CanonicalFlow) for flow in flows)
    assert service.metrics.parsed == 5
    assert service.metrics.accepted == 4
    assert service.metrics.rejected == 1


def test_ingestion_service_does_not_halt_on_bad_record() -> None:
    registry = HostRegistry()
    service = IngestionService(_IngestCfg(), registry)
    flows = service.run()
    # Stream must include records that come AFTER the bad one (C004 -> then C005).
    flow_ids = [flow.flow_id for flow in flows]
    assert "C005" in flow_ids


def test_ingestion_service_replay_is_deterministic() -> None:
    registry_a = HostRegistry()
    registry_b = HostRegistry()
    a = IngestionService(_IngestCfg(), registry_a).run()
    b = IngestionService(_IngestCfg(), registry_b).run()
    assert [flow.flow_id for flow in a] == [flow.flow_id for flow in b]
    assert [CanonicalSchema.to_storage(flow) for flow in a] == [
        CanonicalSchema.to_storage(flow) for flow in b
    ]


def test_ingestion_service_rejects_netflow_when_replay_source_path_missing() -> None:
    cfg = _IngestCfg(source="netflow", zeek_log_dir="", pcap_path="")
    try:
        IngestionService(cfg, HostRegistry()).run()
    except FileNotFoundError:
        return
    raise AssertionError("NetFlow replay without a source file must fail loud.")


def test_flow_store_appends_and_reads_back(tmp_path) -> None:
    registry = HostRegistry()
    store = FlowStore(tmp_path / "flows.jsonl")
    service = IngestionService(_IngestCfg(), registry, flow_store=store)
    written = service.run()

    assert store.count() == len(written)
    reloaded = list(store.read_all())
    assert [flow.flow_id for flow in reloaded] == [flow.flow_id for flow in written]
    assert reloaded == written


def test_flow_store_serialization_is_stable(tmp_path) -> None:
    store_a = FlowStore(tmp_path / "a.jsonl")
    store_b = FlowStore(tmp_path / "b.jsonl")
    service_a = IngestionService(_IngestCfg(), HostRegistry(), flow_store=store_a)
    service_b = IngestionService(_IngestCfg(), HostRegistry(), flow_store=store_b)
    service_a.run()
    service_b.run()
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()


def test_flow_store_handles_missing_file(tmp_path) -> None:
    store = FlowStore(tmp_path / "nonexistent.jsonl")
    assert list(store.read_all()) == []
    assert store.count() == 0


def test_ingestion_feeds_graph_builder(tmp_path) -> None:
    from lated.graph.graph_builder import GraphBuilder
    from lated.graph.graph_store import GraphStore

    registry = HostRegistry()
    flows = IngestionService(_IngestCfg(), registry).run()
    assert flows, "ingestion must yield at least one flow for this integration"

    graph_store = GraphStore(tmp_path / "graph.sqlite3")
    snapshots = GraphBuilder(window_seconds=30, store=graph_store).run(flows)
    assert snapshots, "graph builder must emit at least one snapshot"
    # every emitted snapshot is persisted
    assert graph_store.count() == len(snapshots)
    # no snapshot has overlapping windows with another
    for previous, current in zip(snapshots, snapshots[1:]):
        assert previous.window_end <= current.window_start
