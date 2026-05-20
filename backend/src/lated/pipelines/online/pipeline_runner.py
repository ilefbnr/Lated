# =============================================================================
# lated.pipelines.online.pipeline_runner — replay-first entrypoint
# =============================================================================
#
# Builds the detection pipeline from the existing config + repository surfaces
# and runs the replay orchestrator. Returns the `PipelineResult` so callers
# (tests, an admin endpoint, a CLI wrapper) can introspect what happened.
#
# Live-mode wiring is intentionally absent here: the architecture splits the
# API tier from the detection tier, and live tailing belongs to a later phase.
# =============================================================================

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from lated.correlation.correlation_engine import CorrelationEngine
from lated.correlation.correlation_store import CorrelationStore, session_factory_for
from lated.correlation.graph_adjacency import GraphAdjacency, StaticAdjacency
from lated.detection.fusion.risk_scorer import RiskScorer
from lated.detection.fusion.suspicion_fusion import SuspicionFusion
from lated.detection.protocols.rare_edge_detector import RareEdgeDetector
from lated.detection.protocols.smb_detector import SMBDetector
from lated.detection.recon.recon_detector import ReconDetector
from lated.detection.tgnn.tgnn_inference import TGNNInference
from lated.detection.tgnn.model_loader import ModelLoader
from lated.discovery.host_registry import HostRegistry
from lated.graph.graph_builder import GraphBuilder
from lated.graph.graph_store import GraphStore
from lated.ingestion.flow_store import FlowStore
from lated.ingestion.ingestion_service import IngestionService
from lated.pipelines.online.stream_orchestrator import StreamOrchestrator
from lated.supervision.alerts.alert_engine import AlertEngine
from lated.supervision.alerts.alert_repository import AlertRepository
from lated.supervision.alerts.severity_mapper import SeverityMapper
from lated.supervision.websocket.event_publisher import EventPublisher


@dataclass
class PipelineComponents:
    """Aggregate handle to every constructed component (for introspection)."""

    orchestrator: StreamOrchestrator
    ingestion: IngestionService
    graph_builder: GraphBuilder
    graph_store: GraphStore
    recon_detector: ReconDetector
    smb_detector: SMBDetector
    rare_edge_detector: RareEdgeDetector
    lm_inference: TGNNInference
    fusion: SuspicionFusion
    correlation: CorrelationEngine
    alert_engine: AlertEngine
    alert_repository: AlertRepository
    correlation_store: CorrelationStore
    publisher: EventPublisher
    risk_scorer: RiskScorer
    host_registry: HostRegistry
    flow_store: FlowStore | None


def build_components(
    config,
    *,
    supervision_db_path: str | Path,
    graph_store_path: str | Path,
    flow_store_path: str | Path | None = None,
    host_registry: HostRegistry | None = None,
    publisher: EventPublisher | None = None,
    suspicion_threshold: float = 0.5,
    min_path_confidence: float | None = None,
    adjacency=None,
) -> PipelineComponents:
    """Assemble every component the orchestrator needs."""

    registry = host_registry or HostRegistry()
    flow_store = FlowStore(flow_store_path) if flow_store_path is not None else None
    ingestion = IngestionService(config.ingestion, registry, flow_store=flow_store)

    graph_store = GraphStore(graph_store_path)
    graph_builder = GraphBuilder(
        window_seconds=config.graph.snapshot_window_seconds,
        store=graph_store,
    )

    recon_detector = ReconDetector(
        config.thresholds.recon,
        window_seconds=config.graph.snapshot_window_seconds,
    )

    smb_detector = SMBDetector(
        window_seconds=config.graph.snapshot_window_seconds,
    )

    backend_root = Path(__file__).resolve().parents[4]
    baseline_path = backend_root / "data" / "baseline" / "latest.json"
    rare_edge_detector = RareEdgeDetector.from_baseline_path(
        baseline_path,
        window_seconds=config.graph.snapshot_window_seconds,
    )

    artifact = None
    tgnn_cfg = getattr(getattr(config, "detection", None), "tgnn", None)
    model_path_value = getattr(tgnn_cfg, "model_path", "") if tgnn_cfg is not None else ""
    model_path = Path(model_path_value or "")
    secret_key = os.environ.get("LATED_MODEL_SECRET_KEY") or os.environ.get("LATED_SECRET_KEY")
    if model_path_value and model_path.exists() and secret_key:
        try:
            artifact = ModelLoader(secret_key=secret_key).load(model_path)
        except Exception:
            artifact = None
    lm_inference = TGNNInference(artifact=artifact)

    risk_scorer = RiskScorer(decay_per_hour=config.thresholds.fusion.host_risk_decay_per_hour)
    fusion = SuspicionFusion(config.detection.fusion, risk_scorer)

    factory = session_factory_for(supervision_db_path)
    correlation_store = CorrelationStore(factory)
    alert_repository = AlertRepository(factory)

    adjacency_obj = adjacency if adjacency is not None else GraphAdjacency(graph_store)
    correlation = CorrelationEngine(
        config.correlation,
        adjacency_obj,
        min_path_confidence=(
            min_path_confidence
            if min_path_confidence is not None
            else config.thresholds.correlation.min_path_confidence
        ),
        enable_mitre_tags=config.correlation.enable_mitre_tags,
        pivot_min_neighbors=config.thresholds.correlation.pivot_min_neighbors,
    )

    publisher = publisher or EventPublisher()
    alert_engine = AlertEngine(
        repository=alert_repository,
        publisher=publisher,
        severity_mapper=SeverityMapper(),
        suspicion_threshold=suspicion_threshold,
    )

    orchestrator = StreamOrchestrator(
        ingestion=ingestion,
        graph_builder=graph_builder,
        recon_detector=recon_detector,
        smb_detector=smb_detector,
        rare_edge_detector=rare_edge_detector,
        lm_inference=lm_inference,
        fusion=fusion,
        correlation=correlation,
        alert_engine=alert_engine,
        correlation_store=correlation_store,
        publisher=publisher,
    )

    return PipelineComponents(
        orchestrator=orchestrator,
        ingestion=ingestion,
        graph_builder=graph_builder,
        graph_store=graph_store,
        recon_detector=recon_detector,
        smb_detector=smb_detector,
        rare_edge_detector=rare_edge_detector,
        lm_inference=lm_inference,
        fusion=fusion,
        correlation=correlation,
        alert_engine=alert_engine,
        alert_repository=alert_repository,
        correlation_store=correlation_store,
        publisher=publisher,
        risk_scorer=risk_scorer,
        host_registry=registry,
        flow_store=flow_store,
    )


def run_replay(config, **kwargs) -> dict[str, Any]:
    """Build components and run a single replay pass. Returns the result dict."""
    components = build_components(config, **kwargs)
    result = components.orchestrator.run_replay()
    return {"components": components, "result": result}


def run() -> None:
    """Console-script entry point. Loads config + runs replay end-to-end."""
    # Deferred import: avoid pulling ConfigManager at module import time so the
    # tests that just import build_components don't need a fully resolved repo.
    from lated.common.config_manager import ConfigManager
    from lated.common.logger import configure_logging

    backend_root = Path(__file__).resolve().parents[4]
    config = ConfigManager.load(
        str(backend_root / "config" / "settings.yaml"),
        str(backend_root / "config" / "detection_thresholds.yaml"),
    )
    configure_logging(config.logging)

    supervision_db = backend_root / "data" / "supervision.sqlite3"
    graph_db = backend_root / "data" / "graph" / "snapshots.sqlite3"
    flow_path = backend_root / "data" / "flows" / "canonical.jsonl"

    outcome = run_replay(
        config,
        supervision_db_path=supervision_db,
        graph_store_path=graph_db,
        flow_store_path=flow_path,
    )
    result = outcome["result"]
    print(
        "lated-online replay complete: "
        f"flows={result.metrics['flows']} "
        f"snapshots={result.metrics['snapshots']} "
        f"alerts={result.metrics['alerts']} "
        f"paths={result.metrics['paths']} "
        f"errors={result.metrics['errors']}"
    )
