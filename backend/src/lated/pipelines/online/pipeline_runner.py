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
from lated.detection.protocols.rdp_detector import RDPDetector
from lated.detection.protocols.smb_detector import SMBDetector
from lated.detection.protocols.winrm_detector import WinRMDetector
from lated.detection.recon.recon_detector import ReconDetector
from lated.detection.rules import MITRERulesDetector, load_rules
from lated.detection.tgnn.tgnn_inference import TGNNInference
from lated.detection.tgnn.model_loader import ModelLoader, load_unsigned_artifact
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
    rdp_detector: RDPDetector
    winrm_detector: WinRMDetector
    rare_edge_detector: RareEdgeDetector
    mitre_rules_detector: MITRERulesDetector | None
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
    rdp_detector = RDPDetector(
        window_seconds=config.graph.snapshot_window_seconds,
    )
    winrm_detector = WinRMDetector(
        window_seconds=config.graph.snapshot_window_seconds,
    )

    backend_root = Path(__file__).resolve().parents[4]
    baseline_path = backend_root / "data" / "baseline" / "latest.json"
    rare_edge_detector = RareEdgeDetector.from_baseline_path(
        baseline_path,
        window_seconds=config.graph.snapshot_window_seconds,
        host_registry=registry,
    )

    mitre_rules_detector: MITRERulesDetector | None = None
    rules_path = backend_root / "config" / "detection_rules.yaml"
    if rules_path.is_file():
        try:
            mitre_rules_detector = MITRERulesDetector(
                rules=load_rules(rules_path),
                window_seconds=config.graph.snapshot_window_seconds,
                host_registry=registry,
            )
        except Exception:
            mitre_rules_detector = None

    artifact = None
    tgnn_cfg = getattr(getattr(config, "detection", None), "tgnn", None)
    model_path_value = getattr(tgnn_cfg, "model_path", "") if tgnn_cfg is not None else ""
    node_mapping_value = getattr(tgnn_cfg, "node_mapping_path", "") if tgnn_cfg is not None else ""

    # LATED_TGN_MODEL env var override — takes priority over settings.yaml.
    # Accepts an absolute path or a name relative to backend/data/models/.
    env_model = os.environ.get("LATED_TGN_MODEL", "").strip()
    if env_model:
        candidate = Path(env_model)
        if not candidate.is_absolute():
            candidate = backend_root / "data" / "models" / candidate
        model_path_value = str(candidate)
        # Reset node_mapping_value so the runtime auto-resolves by checkpoint name.
        node_mapping_value = ""

    model_path = (backend_root / model_path_value).resolve() if model_path_value and not Path(model_path_value).is_absolute() else Path(model_path_value or "")
    node_mapping = None
    if node_mapping_value:
        candidate = Path(node_mapping_value)
        if not candidate.is_absolute():
            candidate = backend_root / node_mapping_value
        node_mapping = candidate.resolve() if candidate.exists() else None

    secret_key = os.environ.get("LATED_MODEL_SECRET_KEY") or os.environ.get("LATED_SECRET_KEY")
    dev_mode = os.environ.get("LATED_DEV_MODE", "").lower() in {"1", "true", "yes"}

    if model_path_value and model_path.exists():
        if secret_key and not dev_mode:
            try:
                artifact = ModelLoader(secret_key=secret_key).load(model_path)
            except Exception:
                artifact = None
        if artifact is None and dev_mode:
            try:
                artifact = load_unsigned_artifact(
                    model_path,
                    node_mapping_path=node_mapping,
                )
            except Exception:
                artifact = None
    lm_inference = TGNNInference(
        artifact=artifact,
        window_seconds=config.graph.snapshot_window_seconds,
    )

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

    # NetworkTopology-aware critical-asset lookup. Falls back to host_id-only
    # check when the host has no IP binding yet (early-discovery edge case).
    topology = config.network_topology.topology

    def _is_critical_host(host_id: str) -> bool:
        try:
            host = registry.get(host_id)
            return topology.is_critical_asset(host_id, list(host.ip_addresses))
        except KeyError:
            return topology.is_critical_asset(host_id, None)

    severity_mapper = SeverityMapper(
        critical_asset_ids=set(config.network_topology.critical_assets),
        is_critical_host=_is_critical_host,
    )
    alert_engine = AlertEngine(
        repository=alert_repository,
        publisher=publisher,
        severity_mapper=severity_mapper,
        suspicion_threshold=suspicion_threshold,
    )

    orchestrator = StreamOrchestrator(
        ingestion=ingestion,
        graph_builder=graph_builder,
        recon_detector=recon_detector,
        smb_detector=smb_detector,
        rdp_detector=rdp_detector,
        winrm_detector=winrm_detector,
        rare_edge_detector=rare_edge_detector,
        lm_inference=lm_inference,
        fusion=fusion,
        correlation=correlation,
        alert_engine=alert_engine,
        correlation_store=correlation_store,
        publisher=publisher,
        mitre_rules_detector=mitre_rules_detector,
    )

    return PipelineComponents(
        orchestrator=orchestrator,
        ingestion=ingestion,
        graph_builder=graph_builder,
        graph_store=graph_store,
        recon_detector=recon_detector,
        smb_detector=smb_detector,
        rdp_detector=rdp_detector,
        winrm_detector=winrm_detector,
        rare_edge_detector=rare_edge_detector,
        mitre_rules_detector=mitre_rules_detector,
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
