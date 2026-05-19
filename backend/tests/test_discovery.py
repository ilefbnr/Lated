# =============================================================================
# tests/test_discovery.py — discovery hardened MVP coverage
# =============================================================================

from __future__ import annotations

import socket
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.discovery.active_discovery import ActiveDiscovery, ActiveDiscoveryDisabled
from lated.discovery.baseline_graph import BaselineGraph
from lated.discovery.discovery_service import DiscoveryService
from lated.discovery.host_registry import HostRegistry
from lated.discovery.passive_discovery import PassiveDiscovery
from lated.discovery.topology_builder import TopologyBuilder


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "discovery"
SAMPLE = FIXTURES / "sample.json"
CHURN = FIXTURES / "churn.json"
LIVE_DIR = FIXTURES / "live"
ZEEK_CONN_LOG = Path(__file__).resolve().parents[1] / "data" / "demo_zeek" / "conn.log"


@dataclass(frozen=True)
class _DiscoveryCfg:
    mode: str = "passive"
    passive_window_seconds: int = 86400
    active_scan_enabled: bool = False


def test_host_registry_assigns_stable_host_id() -> None:
    registry = HostRegistry()
    first = registry.upsert(
        {"ip": "10.0.0.21", "mac": "aa:bb:cc:00:00:21", "hostname": "ws-finance-01",
         "first_seen": "2024-01-01T00:00:00Z", "last_seen": "2024-01-01T00:30:00Z"}
    )
    second = registry.upsert(
        {"ip": "10.0.0.99", "mac": "aa:bb:cc:00:00:21",
         "first_seen": "2024-01-01T01:00:00Z", "last_seen": "2024-01-01T01:30:00Z"}
    )
    assert first == second
    host = registry.get(first)
    assert "10.0.0.21" in host.ip_addresses
    assert "10.0.0.99" in host.ip_addresses


def test_host_registry_resolve_ip_at_ts_distinguishes_churn() -> None:
    registry = HostRegistry()
    laptop_a = registry.upsert(
        {"ip": "10.0.0.50", "mac": "aa:bb:cc:00:00:aa", "hostname": "laptop-a",
         "first_seen": "2024-01-01T08:00:00Z", "last_seen": "2024-01-01T09:00:00Z"}
    )
    laptop_b = registry.upsert(
        {"ip": "10.0.0.50", "mac": "aa:bb:cc:00:00:bb", "hostname": "laptop-b",
         "first_seen": "2024-01-01T18:00:00Z", "last_seen": "2024-01-01T19:00:00Z"}
    )
    assert laptop_a != laptop_b
    morning = datetime(2024, 1, 1, 8, 30, tzinfo=timezone.utc)
    evening = datetime(2024, 1, 1, 18, 30, tzinfo=timezone.utc)
    assert registry.resolve("10.0.0.50", morning) == laptop_a
    assert registry.resolve("10.0.0.50", evening) == laptop_b


def test_host_registry_save_and_load_roundtrip(tmp_path) -> None:
    registry = HostRegistry()
    laptop = registry.upsert(
        {"ip": "10.0.0.50", "mac": "aa:bb:cc:00:00:aa", "hostname": "laptop-a",
         "first_seen": "2024-01-01T08:00:00Z", "last_seen": "2024-01-01T09:00:00Z"}
    )
    target = tmp_path / "registry.json"
    registry.save(target)

    reloaded = HostRegistry.load(target)
    assert {host.host_id for host in reloaded.list()} == {laptop}
    when = datetime(2024, 1, 1, 8, 30, tzinfo=timezone.utc)
    assert reloaded.resolve("10.0.0.50", when) == laptop


def test_passive_discovery_replay_extracts_hosts_and_edges() -> None:
    registry = HostRegistry()
    discovery = PassiveDiscovery(registry, SAMPLE)
    result = discovery.observe()

    hostnames = {host.hostname for host in result.hosts}
    assert {"ws-finance-01", "fs-core-02", "dc-core-01", "gw-edge-01", "ws-remote-50"} <= hostnames
    assert len(result.edges) == 7


def test_passive_discovery_live_directory_mode() -> None:
    registry = HostRegistry()
    discovery = PassiveDiscovery(registry, LIVE_DIR)
    result = discovery.observe()

    hostnames = {host.hostname for host in result.hosts if host.hostname}
    macs = {host.metadata.get("mac") for host in result.hosts}
    assert "ws-east-10" in hostnames
    assert "fs-east-20" in hostnames
    assert "aa:bb:cc:00:02:0a" in macs
    assert len(result.edges) == 1
    assert result.edges[0].dst_port == 445


def test_passive_discovery_parses_zeek_conn_log_file() -> None:
    registry = HostRegistry()
    discovery = PassiveDiscovery(registry, ZEEK_CONN_LOG)
    result = discovery.observe()

    assert len(result.hosts) >= 6
    assert len(result.edges) == 13
    first = result.edges[0]
    assert first.src_port == 51200
    assert first.dst_port == 445


def test_topology_builder_identifies_gateway_and_service() -> None:
    registry = HostRegistry()
    observation = PassiveDiscovery(registry, SAMPLE).observe()
    topology = TopologyBuilder().build(observation.hosts, observation.edges)

    gateway_id = registry.resolve("10.0.1.1", "2024-01-01T00:30:00Z")
    dc_id = registry.resolve("10.0.0.5", "2024-01-01T00:30:00Z")
    workstation_id = registry.resolve("10.0.0.21", "2024-01-01T00:10:00Z")

    assert gateway_id in topology["gateways"]
    assert workstation_id not in topology["gateways"]
    assert dc_id in topology["services"]


def test_baseline_graph_save_and_load_roundtrip(tmp_path) -> None:
    registry = HostRegistry()
    observation = PassiveDiscovery(registry, SAMPLE).observe()
    topology = TopologyBuilder().build(observation.hosts, observation.edges)
    baseline = BaselineGraph.build(registry, topology)

    target = tmp_path / "baseline.json"
    baseline.save(target)
    reloaded = BaselineGraph.load(target)
    assert reloaded.schema_version == baseline.schema_version
    assert len(reloaded.nodes) == len(baseline.nodes)
    assert reloaded.subnets == baseline.subnets


def test_baseline_graph_signature_roundtrip(tmp_path) -> None:
    registry = HostRegistry()
    observation = PassiveDiscovery(registry, SAMPLE).observe()
    topology = TopologyBuilder().build(observation.hosts, observation.edges)
    baseline = BaselineGraph.build(registry, topology)

    target = tmp_path / "baseline.json"
    baseline.save(target, secret_key="dev-secret", env="development")
    sig_path = target.with_name(target.name + ".sig")
    assert sig_path.exists()

    BaselineGraph.load(target, secret_key="dev-secret", env="development")

    sig_path.write_text("0" * 64, encoding="utf-8")
    try:
        BaselineGraph.load(target, secret_key="dev-secret", env="development")
    except ValueError as exc:
        assert "signature" in str(exc).lower()
    else:
        raise AssertionError("Tampered signature must be rejected.")


def test_baseline_production_requires_signature(tmp_path) -> None:
    registry = HostRegistry()
    observation = PassiveDiscovery(registry, SAMPLE).observe()
    topology = TopologyBuilder().build(observation.hosts, observation.edges)
    baseline = BaselineGraph.build(registry, topology)

    target = tmp_path / "baseline.json"
    baseline.save(target)  # development save with no secret -> no sig

    try:
        BaselineGraph.load(target, secret_key="prod-secret", env="production")
    except ValueError as exc:
        assert "sig" in str(exc).lower() or "signed" in str(exc).lower()
    else:
        raise AssertionError("Production load without signature must fail loud.")


def test_baseline_graph_rejects_incompatible_schema(tmp_path) -> None:
    target = tmp_path / "bad.json"
    target.write_text('{"schema_version": "0.0.0", "nodes": [], "edges": []}', encoding="utf-8")
    try:
        BaselineGraph.load(target)
    except ValueError as exc:
        assert "schema_version" in str(exc)
    else:
        raise AssertionError("BaselineGraph.load must reject incompatible schema_version.")


def test_discovery_service_run_passive_persists_registry_and_baseline(tmp_path) -> None:
    config = _DiscoveryCfg(mode="passive", active_scan_enabled=False)
    baseline_path = tmp_path / "baseline" / "latest.json"
    registry_path = tmp_path / "discovery" / "host_registry.json"
    service = DiscoveryService(
        config,
        source_path=SAMPLE,
        baseline_path=baseline_path,
        registry_path=registry_path,
    )
    baseline = service.run()

    assert baseline_path.exists()
    assert registry_path.exists()
    assert baseline_path.with_name(baseline_path.name + ".sig").exists()
    first_node_ids = {node.host_id for node in baseline.nodes}

    # second run reloads the persisted registry — same host_ids preserved
    service2 = DiscoveryService(
        _DiscoveryCfg(mode="passive"),
        source_path=SAMPLE,
        baseline_path=baseline_path,
        registry_path=registry_path,
    )
    baseline2 = service2.run()
    assert first_node_ids == {node.host_id for node in baseline2.nodes}


def test_discovery_service_run_passive_from_zeek_conn_log(tmp_path) -> None:
    config = _DiscoveryCfg(mode="passive", active_scan_enabled=False)
    baseline_path = tmp_path / "baseline" / "latest.json"
    registry_path = tmp_path / "discovery" / "host_registry.json"
    service = DiscoveryService(
        config,
        source_path=ZEEK_CONN_LOG,
        baseline_path=baseline_path,
        registry_path=registry_path,
    )
    baseline = service.run()

    assert baseline_path.exists()
    assert registry_path.exists()
    assert len(baseline.nodes) >= 6
    assert len(baseline.edges) >= 5


def test_discovery_service_active_mode_requires_flag(tmp_path) -> None:
    config = _DiscoveryCfg(mode="active", active_scan_enabled=False)
    service = DiscoveryService(
        config,
        source_path=SAMPLE,
        baseline_path=tmp_path / "baseline.json",
        registry_path=tmp_path / "registry.json",
    )
    try:
        service.run()
    except Exception as exc:
        assert "active_scan_enabled" in str(exc)
    else:
        raise AssertionError("Active mode without flag must raise an explicit error.")


def test_active_discovery_refuses_when_disabled() -> None:
    registry = HostRegistry()
    active = ActiveDiscovery(enabled=False, host_registry=registry)
    try:
        active.scan(["127.0.0.1"])
    except ActiveDiscoveryDisabled:
        return
    raise AssertionError("ActiveDiscovery must refuse to scan when disabled.")


def test_active_discovery_detects_listening_port() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    accepted: list[socket.socket] = []

    def _accept_loop():
        try:
            while True:
                conn, _ = server.accept()
                accepted.append(conn)
        except OSError:
            return

    thread = threading.Thread(target=_accept_loop, daemon=True)
    thread.start()
    try:
        registry = HostRegistry()
        active = ActiveDiscovery(
            enabled=True,
            host_registry=registry,
            rate_limit_pps=100,
            ports=(port,),
            timeout_seconds=0.5,
        )
        responders = active.scan(["127.0.0.1"])
    finally:
        server.close()
        for sock in accepted:
            try:
                sock.close()
            except OSError:
                pass
        thread.join(timeout=1.0)

    assert len(responders) == 1
    host = registry.get(responders[0])
    assert host.metadata.get("open_ports") == [port]
    assert host.metadata.get("active_response") is True


def test_discovery_service_hybrid_runs_active_when_enabled(tmp_path) -> None:
    config = _DiscoveryCfg(mode="hybrid", active_scan_enabled=True)
    probed: list[str] = []

    def fake_probe(ip: str, port: int, timeout: float) -> bool:
        probed.append(ip)
        return ip == "10.0.0.21" and port == 445

    service = DiscoveryService(
        config,
        source_path=SAMPLE,
        baseline_path=tmp_path / "baseline.json",
        registry_path=tmp_path / "registry.json",
        active_targets=["10.0.0.21", "10.0.0.11"],
    )
    service.active = ActiveDiscovery(
        enabled=True,
        host_registry=service.host_registry,
        rate_limit_pps=1000,
        ports=(445,),
        probe_fn=fake_probe,
    )
    service.run()

    assert "10.0.0.21" in probed
    assert "10.0.0.11" in probed
    target_host = service.host_registry.resolve("10.0.0.21", "2024-01-01T00:10:00Z")
    assert service.host_registry.get(target_host).metadata.get("active_response") is True
