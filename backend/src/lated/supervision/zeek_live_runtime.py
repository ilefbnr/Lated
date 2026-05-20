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
    ):
        self.config = config
        self.host_registry = host_registry or HostRegistry()
        self.realtime_graph = realtime_graph
        self.ws_channels = ws_channels
        self.normalizer = FlowNormalizer(self.host_registry)
        self.validator = FlowValidator()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

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

    def _run_loop(self) -> None:
        ingestion = self.config.ingestion
        parser = ZeekParser(
            ingestion.zeek_log_dir,
            mode=str(ingestion.mode),
            poll_interval_seconds=0.5,
            max_idle_seconds=3600,
            replay_speed=float(getattr(ingestion, "replay_speed", 1.0)),
        )
        for raw in parser.records():
            if self._stop.is_set():
                return
            try:
                normalized = self.normalizer.normalize(raw, source_sensor="zeek")
                ok, _reason = self.validator.is_valid(normalized)
                if not ok:
                    continue
                flow = CanonicalSchema.from_normalized(normalized)
                self.realtime_graph.ingest(flow)
                self._publish_flow(flow.model_dump(mode="json"))
            except Exception:
                continue

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
