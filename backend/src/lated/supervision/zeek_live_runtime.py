# =============================================================================
# lated.supervision.zeek_live_runtime — flow-by-flow Zeek live reader
# =============================================================================

from __future__ import annotations

import asyncio
import threading

from lated.discovery.host_registry import HostRegistry
from lated.common.schemas import WSEvent, WSEventName, WSChannel
from lated.ingestion.canonical_schema import CanonicalSchema
from lated.ingestion.flow_normalizer import FlowNormalizer
from lated.ingestion.flow_validator import FlowValidator
from lated.ingestion.live_enricher import LiveZeekEnricher
from lated.ingestion.zeek_parser import ZeekParser


class ZeekLiveRuntime:
    """Continuously tails Zeek JSON logs and pushes flows to realtime graph."""

    def __init__(
        self,
        *,
        config,
        host_registry,
        realtime_graph,
        ws_channels,
        detection_pipeline=None,
        hosts_repository=None,
        flows_repository=None,
    ):
        self.config = config
        self.host_registry = host_registry or HostRegistry()
        self.realtime_graph = realtime_graph
        self.ws_channels = ws_channels
        self.detection_pipeline = detection_pipeline
        self.hosts_repository = hosts_repository
        self.flows_repository = flows_repository
        self.normalizer = FlowNormalizer(self.host_registry)
        self.validator = FlowValidator()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        # Hosts already written to the hosts table this run — avoids re-upserting
        # the same host on every flow (the realtime graph dedups nodes the same way).
        self._persisted_hosts: set[str] = set()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, name="lated-zeek-live", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        # Flush any remaining buffered flows in the detection pipeline.
        if self.detection_pipeline is not None:
            try:
                self.detection_pipeline.flush()
            except Exception:
                pass

    def _run_loop(self) -> None:
        ingestion = self.config.ingestion
        log_types = list(getattr(ingestion, "zeek_log_types", None) or ["conn"])
        parser = ZeekParser(
            ingestion.zeek_log_dir,
            mode=str(ingestion.mode),
            poll_interval_seconds=0.5,
            max_idle_seconds=3600,
            replay_speed=float(getattr(ingestion, "replay_speed", 1.0)),
            log_types=log_types,
        )
        enricher = LiveZeekEnricher()
        # `enrich_stream` consumes raw multi-log records, buffers enrichment
        # by uid, and yields only conn records — each carrying an
        # `enrichment` dict that FlowNormalizer will propagate.
        for conn_raw in enricher.enrich_stream(parser.records()):
            if self._stop.is_set():
                return
            try:
                normalized = self.normalizer.normalize(conn_raw, source_sensor="zeek")
                ok, _reason = self.validator.is_valid(normalized)
                if not ok:
                    continue
                flow = CanonicalSchema.from_normalized(normalized)
                self.realtime_graph.ingest(flow)
                self._persist_supervision(flow)
                self._publish_flow(flow.model_dump(mode="json"))
                if self.detection_pipeline is not None:
                    try:
                        self.detection_pipeline.ingest(flow)
                    except Exception:
                        # Detection failure must not stop the live graph.
                        pass
            except Exception:
                continue

    def _persist_supervision(self, flow) -> None:
        """Write the live flow + its endpoints into the supervision DB so the
        REST views (/flows, /hosts) reflect real traffic. Best-effort: a DB
        hiccup must never break live graph ingestion."""
        if self.flows_repository is not None:
            try:
                self.flows_repository.record(flow)
            except Exception:
                pass
        if self.hosts_repository is not None and self.host_registry is not None:
            for host_id in (flow.src_host, flow.dst_host):
                if host_id in self._persisted_hosts:
                    continue
                try:
                    host = self.host_registry.get(host_id)
                    self.hosts_repository.upsert(host)
                    self._persisted_hosts.add(host_id)
                except Exception:
                    pass

    def _publish_flow(self, payload: dict) -> None:
        event = WSEvent(
            channel=WSChannel.FLOWS,
            event=WSEventName.FLOW_NEW,
            payload={**payload, "suspicion": 0.0},
            ts=payload["ts"],
        )
        publish = getattr(self.ws_channels, "publish", None)
        if publish is None:
            return
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(publish(event))
        finally:
            loop.close()
