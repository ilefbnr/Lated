# =============================================================================
# tests/test_online_pipeline.py — phase 8 replay orchestrator coverage
# =============================================================================

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.config_manager import ConfigManager
from lated.detection.tgnn.tgnn_inference import TGNNInference
from lated.pipelines.online.pipeline_runner import build_components
from lated.pipelines.online.runtime_controller import RuntimeController
from lated.supervision.api.app import create_app


@dataclass(frozen=True)
class _Recon:
    fanout_threshold: int = 2
    port_diversity_threshold: int = 2
    burst_packets_per_sec: int = 200
    low_bytes_per_connection: int = 256
    sequential_probe_min_seq: int = 8


@dataclass(frozen=True)
class _Fusion:
    suspicion_alert_threshold: float = 0.3
    host_risk_decay_per_hour: float = 0.05


@dataclass(frozen=True)
class _CorrelationThresholds:
    recon_to_lm_max_gap_seconds: int = 600
    min_path_confidence: float = 0.3
    pivot_min_neighbors: int = 1


@dataclass(frozen=True)
class _Tgnn:
    lm_alert_threshold: float = 0.5
    lm_severity_high: float = 0.9
    lm_severity_medium: float = 0.75


@dataclass(frozen=True)
class _Thresholds:
    tgnn: _Tgnn = _Tgnn()
    recon: _Recon = _Recon()
    fusion: _Fusion = _Fusion()
    correlation: _CorrelationThresholds = _CorrelationThresholds()


@dataclass(frozen=True)
class _Ingestion:
    mode: str
    source: str
    pcap_interface: str
    pcap_path: str
    zeek_log_dir: str
    netflow_port: int
    batch_size: int


@dataclass(frozen=True)
class _GraphCfg:
    snapshot_window_seconds: int = 30


@dataclass(frozen=True)
class _FusionWeights:
    weight_lm: float = 0.6
    weight_recon: float = 0.3
    weight_history: float = 0.1


@dataclass(frozen=True)
class _DetectionCfg:
    fusion: _FusionWeights = _FusionWeights()


@dataclass(frozen=True)
class _CorrelationCfg:
    temporal_continuity_seconds: int = 300
    max_path_length: int = 8
    enable_mitre_tags: bool = True


@dataclass(frozen=True)
class _AppCfg:
    ingestion: _Ingestion
    graph: _GraphCfg
    detection: _DetectionCfg
    correlation: _CorrelationCfg
    thresholds: _Thresholds


def _write_zeek_scan_fixture(directory: Path) -> None:
    """Write a Zeek conn.log fixture that triggers recon + path correlation."""
    directory.mkdir(parents=True, exist_ok=True)
    base_ts = 1704067200  # 2024-01-01T00:00:00Z, aligned to 30s window
    lines = []
    # Window [0, 30): host-a scans 3 destinations on 3 ports + reaches host-b
    for i, (dst_ip, port) in enumerate(
        [("10.0.0.11", 1000), ("10.0.0.12", 1001), ("10.0.0.13", 1002), ("10.0.0.20", 80)]
    ):
        lines.append(json.dumps({
            "ts": base_ts + i,
            "uid": f"Cwin0-{i}",
            "id.orig_h": "10.0.0.21",
            "id.orig_p": 51200 + i,
            "id.resp_h": dst_ip,
            "id.resp_p": port,
            "proto": "tcp",
            "duration": 0.5,
            "orig_pkts": 80,
            "resp_pkts": 80,
            "orig_ip_bytes": 600,
            "resp_ip_bytes": 600,
        }))
    # Window [30, 60): host-b probes 3 destinations on 3 ports
    for i, (dst_ip, port) in enumerate(
        [("10.0.0.31", 1000), ("10.0.0.32", 1001), ("10.0.0.33", 1002)]
    ):
        lines.append(json.dumps({
            "ts": base_ts + 35 + i,
            "uid": f"Cwin1-{i}",
            "id.orig_h": "10.0.0.20",
            "id.orig_p": 52000 + i,
            "id.resp_h": dst_ip,
            "id.resp_p": port,
            "proto": "tcp",
            "duration": 0.5,
            "orig_pkts": 80,
            "resp_pkts": 80,
            "orig_ip_bytes": 600,
            "resp_ip_bytes": 600,
        }))
    (directory / "conn.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_config(zeek_dir: Path) -> _AppCfg:
    return _AppCfg(
        ingestion=_Ingestion(
            mode="replay",
            source="zeek",
            pcap_interface="",
            pcap_path="",
            zeek_log_dir=str(zeek_dir),
            netflow_port=2055,
            batch_size=100,
        ),
        graph=_GraphCfg(snapshot_window_seconds=30),
        detection=_DetectionCfg(),
        correlation=_CorrelationCfg(),
        thresholds=_Thresholds(),
    )


def _components_for(tmp_path: Path):
    zeek_dir = tmp_path / "zeek"
    _write_zeek_scan_fixture(zeek_dir)
    config = _make_config(zeek_dir)
    return build_components(
        config,
        supervision_db_path=tmp_path / "supervision.sqlite3",
        graph_store_path=tmp_path / "graph.sqlite3",
        flow_store_path=tmp_path / "flows.jsonl",
        suspicion_threshold=0.3,
        min_path_confidence=0.3,
    )


def test_replay_pipeline_runs_end_to_end(tmp_path: Path) -> None:
    components = _components_for(tmp_path)
    result = components.orchestrator.run_replay()

    assert result.metrics["flows"] > 0
    assert result.metrics["snapshots"] > 0
    assert result.metrics["recon_scores"] > 0
    assert result.metrics["smb_scores"] >= 0
    assert result.metrics["rare_edge_scores"] >= 0
    # The placeholder LM should score at least one node in the busy window
    assert result.metrics["lm_scores"] > 0
    assert result.metrics["alerts"] > 0
    assert result.errors == {}


def test_replay_emits_websocket_events(tmp_path: Path) -> None:
    components = _components_for(tmp_path)
    components.orchestrator.run_replay()

    published = components.publisher.history()
    assert published, "Replay must publish at least one WS event"
    names = {event.event for event in published}
    assert "alert.new" in names


def test_replay_persists_alerts_visible_through_alert_repository(tmp_path: Path) -> None:
    components = _components_for(tmp_path)
    result = components.orchestrator.run_replay()

    rows, total = components.alert_repository.list(
        filters={"severity": [], "host": None, "since": None, "until": None},
        page=1,
    )
    assert total >= len(result.alerts) >= 1
    assert any(alert.kind in {"fusion", "lateral_movement", "reconnaissance", "correlation"} for alert in rows)


def test_replay_is_deterministic(tmp_path: Path) -> None:
    components_a = _components_for(tmp_path / "a")
    components_b = _components_for(tmp_path / "b")
    result_a = components_a.orchestrator.run_replay()
    result_b = components_b.orchestrator.run_replay()

    assert [alert.alert_id for alert in result_a.alerts] == [
        alert.alert_id for alert in result_b.alerts
    ]
    assert result_a.metrics["alerts"] == result_b.metrics["alerts"]
    assert result_a.metrics["paths"] == result_b.metrics["paths"]


def test_lm_branch_failure_does_not_silence_recon(tmp_path: Path) -> None:
    zeek_dir = tmp_path / "zeek"
    _write_zeek_scan_fixture(zeek_dir)
    config = _make_config(zeek_dir)
    # Without LM contribution, fusion caps at weight_recon (0.3 by default).
    # Lower the alerting threshold so recon-only suspicions still surface.
    components = build_components(
        config,
        supervision_db_path=tmp_path / "supervision.sqlite3",
        graph_store_path=tmp_path / "graph.sqlite3",
        flow_store_path=tmp_path / "flows.jsonl",
        suspicion_threshold=0.1,
        min_path_confidence=0.1,
    )

    class _FailingLm(TGNNInference):
        def run(self, snapshot_stream):  # type: ignore[override]
            raise RuntimeError("simulated LM branch crash")

    components.lm_inference = _FailingLm()
    components.orchestrator.lm_inference = components.lm_inference

    result = components.orchestrator.run_replay()

    assert "lm_inference" in result.errors
    # Recon branch must still have produced suspicions + alerts.
    assert result.metrics["recon_scores"] > 0
    assert result.metrics["alerts"] > 0


def test_supervision_api_reflects_replay_generated_alerts(tmp_path: Path) -> None:
    components = _components_for(tmp_path)
    components.orchestrator.run_replay()

    config = ConfigManager.load(
        str(Path(__file__).resolve().parents[1] / "config" / "settings.yaml"),
        str(Path(__file__).resolve().parents[1] / "config" / "detection_thresholds.yaml"),
    )
    app = create_app(config, supervision_db_path=tmp_path / "supervision.sqlite3")
    with TestClient(app) as client:
        response = client.get("/alerts", headers={"Authorization": "Bearer analyst-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    alert_ids = {row["alert_id"] for row in payload["rows"]}
    # Replay-emitted alerts use the alert-<kind>-<host>-<ts> shape
    assert any(alert_id.startswith("alert-") for alert_id in alert_ids)


def test_runtime_controller_reports_status_and_pause(tmp_path: Path) -> None:
    components = _components_for(tmp_path)
    controller = RuntimeController(components)

    initial = controller.status()
    assert initial.paused is False
    assert "placeholder" in initial.model_version

    paused = controller.pause(actor="admin.local")
    assert paused.paused is True
    assert paused.last_action_actor == "admin.local"

    resumed = controller.resume(actor="admin.local")
    assert resumed.paused is False
