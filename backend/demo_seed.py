"""Demo seeder for LateD.

Runs an end-to-end replay against a realistic Zeek-style fixture, writing
alerts + attack paths into the same supervision SQLite DB used by the API.

Usage (from backend/):
    python demo_seed.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from lated.pipelines.online.pipeline_runner import build_components  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal AppConfig facade — replays the realistic threshold + fusion knobs
# without needing the YAML/env layer.
# ---------------------------------------------------------------------------
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
class _Recon:
    fanout_threshold: int = 3
    port_diversity_threshold: int = 3
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
    min_path_confidence: float = 0.25
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
class _AppCfg:
    ingestion: _Ingestion
    graph: _GraphCfg
    detection: _DetectionCfg
    correlation: _CorrelationCfg
    thresholds: _Thresholds


# ---------------------------------------------------------------------------
# Fixture: a 3-window incident across host-a → host-b → host-c with sprinkled
# recon flows on the side. Generates ~25 flows, lighting up most of the UI.
# ---------------------------------------------------------------------------
def _write_demo_fixture(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    base_ts = 1715850000  # arbitrary "now-ish" anchor

    flows: list[dict] = []

    def push(uid, ts_offset, src, src_port, dst, dst_port, packets=80, bytes_=600):
        flows.append({
            "ts": base_ts + ts_offset,
            "uid": uid,
            "id.orig_h": src,
            "id.orig_p": src_port,
            "id.resp_h": dst,
            "id.resp_p": dst_port,
            "proto": "tcp",
            "duration": 0.5,
            "orig_pkts": packets,
            "resp_pkts": packets,
            "orig_ip_bytes": bytes_,
            "resp_ip_bytes": bytes_,
        })

    # Window [0, 30): host-a recons 4 subnet members
    push("Cw0-1",  1, "10.0.0.21", 51200, "10.0.0.11", 445)
    push("Cw0-2",  3, "10.0.0.21", 51201, "10.0.0.12", 139)
    push("Cw0-3",  5, "10.0.0.21", 51202, "10.0.0.13", 80)
    push("Cw0-4",  9, "10.0.0.21", 51203, "10.0.0.14", 443)
    # ... and reaches the pivot
    push("Cw0-5", 12, "10.0.0.21", 51204, "10.0.0.20", 22, packets=200, bytes_=4000)

    # Window [30, 60): pivot host-b fans out further on admin ports
    push("Cw1-1", 31, "10.0.0.20", 52001, "10.0.1.31", 445)
    push("Cw1-2", 35, "10.0.0.20", 52002, "10.0.1.32", 3389)
    push("Cw1-3", 40, "10.0.0.20", 52003, "10.0.1.33", 5985)
    push("Cw1-4", 45, "10.0.0.20", 52004, "10.0.1.34", 22)

    # Window [60, 90): deep host-c reaches the domain controller
    push("Cw2-1", 65, "10.0.1.31", 60010, "10.0.2.5", 389, packets=140, bytes_=2200)
    push("Cw2-2", 70, "10.0.1.31", 60011, "10.0.2.5", 636, packets=120, bytes_=2200)

    # Bonus benign chatter so the DB isn't sterile
    push("Bc-1", 14, "10.0.0.50", 50000, "10.0.0.11", 80)
    push("Bc-2", 47, "10.0.0.51", 50001, "10.0.0.12", 443)

    (directory / "conn.log").write_text(
        "\n".join(json.dumps(flow) for flow in flows) + "\n",
        encoding="utf-8",
    )


def _build_config(zeek_dir: Path) -> _AppCfg:
    return _AppCfg(
        ingestion=_Ingestion(
            mode="replay",
            source="zeek",
            pcap_interface="",
            pcap_path="",
            zeek_log_dir=str(zeek_dir),
            netflow_port=2055,
            batch_size=200,
        ),
        graph=_GraphCfg(),
        detection=_DetectionCfg(),
        correlation=_CorrelationCfg(),
        thresholds=_Thresholds(),
    )


def main() -> int:
    data_dir = ROOT / "data"
    fixture_dir = data_dir / "demo_zeek"
    supervision_db = data_dir / "supervision.sqlite3"
    graph_db = data_dir / "graph" / "snapshots.sqlite3"
    flow_store = data_dir / "flows" / "demo.jsonl"

    # Wipe stale demo artefacts so the replay is reproducible.
    for stale in (supervision_db, graph_db, flow_store):
        if stale.exists():
            stale.unlink()

    _write_demo_fixture(fixture_dir)
    config = _build_config(fixture_dir)

    components = build_components(
        config,
        supervision_db_path=supervision_db,
        graph_store_path=graph_db,
        flow_store_path=flow_store,
        suspicion_threshold=0.20,
        min_path_confidence=0.20,
    )

    result = components.orchestrator.run_replay()

    print("=" * 60)
    print("LateD demo replay complete")
    print("=" * 60)
    print(f"flows ingested ........... {result.metrics['flows']}")
    print(f"snapshots emitted ........ {result.metrics['snapshots']}")
    print(f"recon scores ............. {result.metrics['recon_scores']}")
    print(f"lm scores ................ {result.metrics['lm_scores']}")
    print(f"suspicions ............... {result.metrics['suspicions']}")
    print(f"correlated paths ......... {result.metrics['paths']}")
    print(f"alerts persisted ......... {result.metrics['alerts']}")
    print(f"ws events fired .......... {result.metrics['published_events']}")
    if result.errors:
        print(f"errors ................... {result.errors}")
    print()
    print(f"supervision db -> {supervision_db}")
    print(f"graph db       -> {graph_db}")
    print(f"flow store     -> {flow_store}")
    print()
    print("Start the API:   python serve.py")
    print("Start the UI:    (from frontend/) npm run dev")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
