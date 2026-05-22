# =============================================================================
# lated.pipelines.online.stream_orchestrator — wire components together
# =============================================================================
#
# Replay-first sync orchestrator. The wiring:
#
#       IngestionService.run() ───── flows ─────┐
#                                                │
#                                  ┌─────────────┴─────────────┐
#                                  ▼                           ▼
#                       GraphBuilder.run()             ReconDetector.run()
#                                  │                           │
#                                  ▼                           │
#                       TGNNInference.run()                    │
#                                  │                           │
#                                  └────────────┐  ┌───────────┘
#                                               ▼  ▼
#                                       SuspicionFusion.run()
#                                               │
#                                               ▼
#                                    CorrelationEngine.run()
#                                               │
#                                               ▼
#                                       AlertEngine.consume()
#                                               │
#                                               ▼
#                              EventPublisher.publish_sync() (WS fanout)
#
# Branch isolation:
#   - LM and recon branches are run in independent try/except blocks. Failing
#     branch reports its exception in `PipelineResult.errors` and the other
#     branch still feeds fusion (with the missing side imputed to zero, the
#     fail-safe behavior already implemented in SuspicionFusion).
#   - A failure further downstream (correlation, alert engine) is still
#     captured so callers can decide what to do.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineResult:
    flows: list = field(default_factory=list)
    snapshots: list = field(default_factory=list)
    lm_scores: list = field(default_factory=list)
    recon_scores: list = field(default_factory=list)
    smb_scores: list = field(default_factory=list)
    rare_edge_scores: list = field(default_factory=list)
    rule_scores: list = field(default_factory=list)
    suspicions: list = field(default_factory=list)
    correlation_results: list = field(default_factory=list)
    alerts: list = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


class StreamOrchestrator:
    """Replay orchestrator (sync). One run -> one PipelineResult."""

    def __init__(
        self,
        ingestion,
        graph_builder,
        recon_detector,
        smb_detector,
        rare_edge_detector,
        lm_inference,
        fusion,
        correlation,
        alert_engine,
        correlation_store=None,
        publisher=None,
        mitre_rules_detector=None,
    ):
        self.ingestion = ingestion
        self.graph_builder = graph_builder
        self.recon_detector = recon_detector
        self.smb_detector = smb_detector
        self.rare_edge_detector = rare_edge_detector
        self.lm_inference = lm_inference
        self.fusion = fusion
        self.correlation = correlation
        self.alert_engine = alert_engine
        self.correlation_store = correlation_store
        self.publisher = publisher
        self.mitre_rules_detector = mitre_rules_detector

    def run_replay(self) -> PipelineResult:
        result = PipelineResult()

        # 1. Ingestion — fatal if it fails. No data, no pipeline.
        result.flows = list(self.ingestion.run())

        # 2. Graph branch (LM): produce snapshots then LM scores.
        try:
            result.snapshots = list(self.graph_builder.run(result.flows))
        except Exception as exc:  # noqa: BLE001
            result.errors["graph_builder"] = f"{type(exc).__name__}: {exc}"
            result.snapshots = []

        try:
            # Prefer event-based real TGN inference when the model is loaded;
            # the placeholder structural scorer over snapshots is the fallback.
            tgn_runtime = getattr(self.lm_inference, "_tgn_runtime", None)
            if tgn_runtime is not None and hasattr(self.lm_inference, "score_flows"):
                result.lm_scores = list(self.lm_inference.score_flows(result.flows))
            else:
                result.lm_scores = list(self.lm_inference.run(result.snapshots))
        except Exception as exc:  # noqa: BLE001
            result.errors["lm_inference"] = f"{type(exc).__name__}: {exc}"
            result.lm_scores = []

        # 3. Recon branch — independent of graph/LM.
        try:
            result.recon_scores = list(self.recon_detector.run(result.flows))
        except Exception as exc:  # noqa: BLE001
            result.errors["recon_detector"] = f"{type(exc).__name__}: {exc}"
            result.recon_scores = []

        try:
            result.smb_scores = list(self.smb_detector.run(result.flows))
        except Exception as exc:  # noqa: BLE001
            result.errors["smb_detector"] = f"{type(exc).__name__}: {exc}"
            result.smb_scores = []

        try:
            result.rare_edge_scores = list(self.rare_edge_detector.run(result.flows))
        except Exception as exc:  # noqa: BLE001
            result.errors["rare_edge_detector"] = f"{type(exc).__name__}: {exc}"
            result.rare_edge_scores = []

        if self.mitre_rules_detector is not None:
            try:
                result.rule_scores = list(self.mitre_rules_detector.run(result.flows))
            except Exception as exc:  # noqa: BLE001
                result.errors["mitre_rules_detector"] = f"{type(exc).__name__}: {exc}"
                result.rule_scores = []

        # 4. Fusion joins both branches (missing branch imputed to zero).
        try:
            result.suspicions = list(self.fusion.run(
                result.lm_scores,
                [
                    *result.recon_scores,
                    *result.smb_scores,
                    *result.rare_edge_scores,
                    *result.rule_scores,
                ],
            ))
        except Exception as exc:  # noqa: BLE001
            result.errors["fusion"] = f"{type(exc).__name__}: {exc}"
            result.suspicions = []

        # 5. Correlation -> AttackPath candidates.
        try:
            result.correlation_results = list(self.correlation.run(result.suspicions))
        except Exception as exc:  # noqa: BLE001
            result.errors["correlation"] = f"{type(exc).__name__}: {exc}"
            result.correlation_results = []

        # 6. Persist correlation outputs into supervision tables (if wired).
        if self.correlation_store is not None and result.correlation_results:
            try:
                self.correlation_store.save_many(result.correlation_results)
            except Exception as exc:  # noqa: BLE001
                result.errors["correlation_store"] = f"{type(exc).__name__}: {exc}"

        # 7. Alert engine consumes suspicions + correlation outputs.
        try:
            result.alerts = list(
                self.alert_engine.consume(result.suspicions, result.correlation_results)
            )
        except Exception as exc:  # noqa: BLE001
            result.errors["alert_engine"] = f"{type(exc).__name__}: {exc}"
            result.alerts = []

        result.metrics = self._collect_metrics(result)
        return result

    def _collect_metrics(self, result: PipelineResult) -> dict[str, Any]:
        return {
            "flows": len(result.flows),
            "snapshots": len(result.snapshots),
            "lm_scores": len(result.lm_scores),
            "recon_scores": len(result.recon_scores),
            "smb_scores": len(result.smb_scores),
            "rare_edge_scores": len(result.rare_edge_scores),
            "rule_scores": len(result.rule_scores),
            "suspicions": len(result.suspicions),
            "paths": len(result.correlation_results),
            "alerts": len(result.alerts),
            "alert_engine": dict(getattr(self.alert_engine, "metrics", {})),
            "ingestion": getattr(self.ingestion, "metrics", None).__dict__
            if getattr(self.ingestion, "metrics", None) is not None
            else {},
            "errors": dict(result.errors),
            "published_events": len(self.publisher.history()) if self.publisher is not None else 0,
        }
