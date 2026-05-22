# =============================================================================
# lated.supervision.live_detection_pipeline — streaming detection
# =============================================================================
#
# Runs the full detection pipeline on the live flow stream produced by
# ZeekLiveRuntime. Mirrors what StreamOrchestrator.run_replay does, but in
# a windowed/tick-driven fashion:
#
#   1. Buffer flows in a 60s window (aligned to UTC).
#   2. When a flow arrives whose window is later than the buffered one,
#      flush the buffered window through:
#         GraphBuilder -> TGN
#         ReconDetector
#         SMBDetector
#         RareEdgeDetector
#         MITRERulesDetector
#         SuspicionFusion
#         CorrelationEngine
#         AlertEngine
#   3. Emit a `host.risk` WS event for every SuspicionScore produced.
#
# Designed to be called from the ZeekLiveRuntime worker thread — all
# operations are sync; WS fanout happens via the provided WSChannels
# (we never block the live thread on a network roundtrip).
# =============================================================================

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import Any

from lated.common.schemas import (
    CanonicalFlow, WSChannel, WSEvent, WSEventName,
)


class LiveDetectionPipeline:
    """Streaming wrapper that runs the detection pipeline window by window."""

    def __init__(
        self,
        *,
        graph_builder,
        recon_detector,
        smb_detector,
        rare_edge_detector,
        mitre_rules_detector,
        lm_inference,
        fusion,
        correlation,
        alert_engine,
        correlation_store=None,
        ws_channels,
        window_seconds: int = 60,
    ):
        self.graph_builder = graph_builder
        self.recon_detector = recon_detector
        self.smb_detector = smb_detector
        self.rare_edge_detector = rare_edge_detector
        self.mitre_rules_detector = mitre_rules_detector
        self.lm_inference = lm_inference
        self.fusion = fusion
        self.correlation = correlation
        self.alert_engine = alert_engine
        self.correlation_store = correlation_store
        self.ws_channels = ws_channels
        self.window_seconds = int(window_seconds)

        self._buffer: list[CanonicalFlow] = []
        self._current_window_start: datetime | None = None
        self._lock = threading.Lock()
        self.metrics: dict[str, int] = {
            "windows_flushed": 0,
            "flows_processed": 0,
            "alerts_emitted": 0,
            "paths_emitted": 0,
            "errors": 0,
        }

    # --------------------------------------------------------------- public

    def ingest(self, flow: CanonicalFlow) -> None:
        """Called by ZeekLiveRuntime for each new flow."""
        window_start = self._window_start_for(flow.ts)
        to_flush: list[CanonicalFlow] | None = None
        with self._lock:
            if self._current_window_start is None:
                self._current_window_start = window_start
            elif window_start > self._current_window_start:
                to_flush = self._buffer
                self._buffer = []
                self._current_window_start = window_start
            self._buffer.append(flow)
        if to_flush:
            self._flush_window(to_flush)

    def flush(self) -> None:
        """Force-flush the current buffer (call on shutdown)."""
        with self._lock:
            to_flush = self._buffer
            self._buffer = []
        if to_flush:
            self._flush_window(to_flush)

    # ------------------------------------------------------------- internals

    def _window_start_for(self, ts: datetime) -> datetime:
        ts_utc = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        epoch = int(ts_utc.timestamp())
        bucket = epoch - (epoch % self.window_seconds)
        return datetime.fromtimestamp(bucket, tz=timezone.utc)

    def _flush_window(self, flows: list[CanonicalFlow]) -> None:
        if not flows:
            return
        self.metrics["flows_processed"] += len(flows)
        self.metrics["windows_flushed"] += 1
        try:
            # --- heuristic detectors (stream-friendly) ---
            recon_scores = list(self.recon_detector.run(flows)) if self.recon_detector else []
            smb_scores = list(self.smb_detector.run(flows)) if self.smb_detector else []
            rare_scores = list(self.rare_edge_detector.run(flows)) if self.rare_edge_detector else []
            rule_scores = list(self.mitre_rules_detector.run(flows)) if self.mitre_rules_detector else []

            # --- TGN branch: prefer event-based real model, else snapshots ---
            lm_scores: list = []
            tgn_runtime = getattr(self.lm_inference, "_tgn_runtime", None)
            if tgn_runtime is not None and hasattr(self.lm_inference, "score_flows"):
                try:
                    lm_scores = list(self.lm_inference.score_flows(flows))
                except Exception:
                    lm_scores = []
            else:
                try:
                    snapshots = list(self.graph_builder.run(flows)) if self.graph_builder else []
                    lm_scores = list(self.lm_inference.run(snapshots)) if self.lm_inference else []
                except Exception:
                    lm_scores = []

            # --- fusion ---
            suspicions = list(self.fusion.run(
                lm_scores,
                [*recon_scores, *smb_scores, *rare_scores, *rule_scores],
            )) if self.fusion else []

            # --- correlation ---
            paths: list = []
            if self.correlation and suspicions:
                try:
                    paths = list(self.correlation.run(suspicions))
                except Exception:
                    paths = []
            if self.correlation_store and paths:
                try:
                    self.correlation_store.save_many(paths)
                except Exception:
                    pass

            # --- alerts ---
            alerts: list = []
            if self.alert_engine:
                try:
                    alerts = list(self.alert_engine.consume(suspicions, paths))
                except Exception:
                    alerts = []
            self.metrics["alerts_emitted"] += len(alerts)
            self.metrics["paths_emitted"] += len(paths)

            # --- host.risk fanout to WS ---
            for s in suspicions:
                self._publish_host_risk(s)

        except Exception:
            self.metrics["errors"] += 1

    def _publish_host_risk(self, suspicion) -> None:
        if self.ws_channels is None:
            return
        try:
            event = WSEvent(
                channel=WSChannel.HOSTS,
                event=WSEventName.HOST_RISK,
                payload={
                    "host_id": suspicion.subject_host,
                    "current_risk": float(suspicion.score),
                    "last_alert_at": suspicion.window_start.isoformat() if hasattr(suspicion.window_start, "isoformat") else None,
                },
                ts=suspicion.window_start if hasattr(suspicion, "window_start") else datetime.now(timezone.utc),
            )
            publish = getattr(self.ws_channels, "publish", None)
            if publish is None:
                return
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(publish(event))
            except RuntimeError:
                # Called from a worker thread without a running loop.
                asyncio.run(publish(event))
        except Exception:
            self.metrics["errors"] += 1
