# =============================================================================

from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.config_manager import ConfigManager
from lated.supervision.api.app import create_app


def _load_config():
    root = Path(__file__).resolve().parents[1]
    return ConfigManager.load(
        str(root / "config" / "settings.yaml"),
        str(root / "config" / "detection_thresholds.yaml"),
    )


def test_health_responds_ok() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["modules"]["api"] == "ok"


def test_alerts_requires_auth() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/alerts")

    assert response.status_code == 401


def test_metrics_endpoint_exposes_prometheus_text() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "lated_health_requests_total" in response.text


def test_alerts_list_returns_rows_for_authenticated_user() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/alerts", headers={"Authorization": "Bearer analyst-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert payload["rows"][0]["alert_id"] == "alert-001"


def test_hosts_top_risky_returns_seeded_hosts() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/hosts/top-risky", headers={"Authorization": "Bearer analyst-token"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1
    assert payload[0]["host_id"] == "host-workstation-01"


def test_admin_reload_thresholds_requires_admin_role() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.post(
            "/admin/reload-thresholds",
            headers={"Authorization": "Bearer analyst-token"},
        )

    assert response.status_code == 403


def test_websocket_receives_heartbeat() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws",
            headers={"Authorization": "Bearer analyst-token"},
        ) as websocket:
            frame = websocket.receive_json()

    assert frame["channel"] == "health"
    assert frame["event"] == "health.heartbeat"
    assert frame["payload"]["status"] == "ok"


def test_websocket_rejects_missing_auth() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/ws"):
                assert False, "websocket should not connect without auth"
        except Exception as exc:
            assert "WebSocketDisconnect" in type(exc).__name__


_AUTH = {"Authorization": "Bearer analyst-token"}


def test_graph_baseline_requires_auth() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/graph/baseline")
    assert response.status_code == 401


def test_graph_baseline_returns_payload() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/graph/baseline", headers=_AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert "nodes" in payload and "edges" in payload
    assert "generated_at" in payload
    assert len(payload["nodes"]) >= 1
    assert len(payload["edges"]) >= 1
    labels = {node["data"].get("label") for node in payload["nodes"]}
    assert "ws-finance-01" in labels or "host-workstation-01" in {node["data"]["id"] for node in payload["nodes"]}


def test_graph_snapshot_latest_returns_payload() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/graph/snapshot/latest", headers=_AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert "nodes" in payload and "edges" in payload


def test_graph_host_ego_returns_neighbors() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/graph/host/host-workstation-01", headers=_AUTH)
    assert response.status_code == 200
    payload = response.json()
    labels = {node["data"].get("label") for node in payload["nodes"]}
    assert "ws-finance-01" in labels
    assert len(payload["nodes"]) >= 2


def test_flows_requires_auth() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/flows")
    assert response.status_code == 401


def test_flows_list_returns_rows_and_total() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/flows", headers=_AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert isinstance(payload["rows"], list)
    flow_ids = {row["flow_id"] for row in payload["rows"]}
    assert "flow-001" in flow_ids


def test_flows_get_single_flow() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/flows/flow-001", headers=_AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["flow_id"] == "flow-001"
    assert payload["protocol"] == "tcp"


def test_flows_by_host_filters_by_endpoint() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/flows/by-host/host-workstation-01", headers=_AUTH)
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 1
    for row in rows:
        assert row["src_host"] == "host-workstation-01" or row["dst_host"] == "host-workstation-01"


def test_paths_requires_auth() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/paths")
    assert response.status_code == 401


def test_paths_list_returns_rows() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/paths", headers=_AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    path_ids = {row["path_id"] for row in payload["rows"]}
    assert "path-001" in path_ids


def test_paths_timeline_returns_alerts() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/paths/path-001/timeline", headers=_AUTH)
    assert response.status_code == 200
    timeline = response.json()
    assert len(timeline) >= 1
    assert "alert_id" in timeline[0]


def test_paths_graph_returns_subgraph_of_path_hosts() -> None:
    app = create_app(_load_config())
    with TestClient(app) as client:
        response = client.get("/paths/path-001/graph", headers=_AUTH)
    assert response.status_code == 200
    payload = response.json()
    labels = {node["data"].get("label") for node in payload["nodes"]}
    assert "ws-finance-01" in labels
    for edge in payload["edges"]:
        node_ids = {node["data"]["id"] for node in payload["nodes"]}
        assert edge["data"]["source"] in node_ids
        assert edge["data"]["target"] in node_ids


def test_graph_baseline_reads_discovery_artifact_when_present(tmp_path) -> None:
    from dataclasses import dataclass
    from lated.discovery.discovery_service import DiscoveryService

    @dataclass(frozen=True)
    class _Cfg:
        mode: str = "passive"
        passive_window_seconds: int = 86400
        active_scan_enabled: bool = False

    fixture = Path(__file__).resolve().parent / "fixtures" / "discovery" / "sample.json"
    baseline_path = tmp_path / "baseline" / "latest.json"
    DiscoveryService(
        _Cfg(),
        source_path=fixture,
        baseline_path=baseline_path,
        registry_path=tmp_path / "registry.json",
    ).run()

    app = create_app(_load_config(), baseline_path=baseline_path)
    with TestClient(app) as client:
        response = client.get("/graph/baseline", headers=_AUTH)

    assert response.status_code == 200
    payload = response.json()
    hostnames = {node["data"]["label"] for node in payload["nodes"]}
    assert "gw-edge-01" in hostnames
    assert "ws-finance-01" in hostnames
    # Edges from discovery carry communication counts as weight
    weights = {edge["data"]["weight"] for edge in payload["edges"]}
    assert any(weight >= 1 for weight in weights)


def test_discovery_bootstrap_generates_baseline_from_zeek_source(tmp_path) -> None:
    app = create_app(_load_config())
    app.state.baseline_path = tmp_path / "baseline" / "latest.json"
    app.state.registry_path = tmp_path / "discovery" / "host_registry.json"
    app.state.graph_repository.baseline_path = app.state.baseline_path

    backend_root = Path(__file__).resolve().parents[1]
    app.state.backend_root = backend_root
    app.state.config.ingestion.zeek_log_dir  # touch for clarity in test failures

    with TestClient(app) as client:
        response = client.post("/discovery/bootstrap", headers=_AUTH)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["host_count"] >= 6
    assert app.state.baseline_path.exists()

    with TestClient(app) as client:
        baseline_response = client.get("/graph/baseline", headers=_AUTH)

    assert baseline_response.status_code == 200
    baseline_payload = baseline_response.json()
    assert baseline_payload["summary"]["host_count"] >= 6
    assert "summary" in baseline_payload
# tests/test_api.py — API + WebSocket test plan
# =============================================================================
#
# COVERAGE PLAN
# -------------
#   - GET /health responds 200 with status fields.
#   - /alerts requires auth; anon -> 401.
#   - /admin/* requires admin role; analyst -> 403.
#   - /admin/model requires X-Confirm-Action header.
#   - WebSocket /ws closes 1008 on missing bearer token.
#   - WebSocket subscription receives `EVT_ALERT_NEW` after alert insertion.
#
# SECURITY-FOCUSED CASES
# ----------------------
#   - Rate limit enforced on /alerts (HTTP 429 after N req/sec).
#   - Exception in a handler returns the LatedError code, never a stack trace.
#   - Mutation endpoints write to event_store with actor + before/after.
# =============================================================================
