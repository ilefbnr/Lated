# =============================================================================
# lated.ingestion.ingestion_service — top-level dispatcher
# =============================================================================
#
# Selects the configured ingestion source, runs the
#     parse -> normalize -> validate -> CanonicalFlow
# pipeline, and (optionally) appends accepted flows to the forensic store.
#
# Sync stream API — the MVP is replay-first; we don't need asyncio yet. Live
# tailing will wrap this into an async loop in a later phase.
# =============================================================================

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from lated.common.exceptions import FlowValidationError, IngestionError
from lated.common.schemas import CanonicalFlow

from lated.ingestion.canonical_schema import CanonicalSchema
from lated.ingestion.flow_normalizer import FlowNormalizer
from lated.ingestion.flow_store import FlowStore
from lated.ingestion.flow_validator import FlowValidator
from lated.ingestion.netflow_parser import NetFlowParser
from lated.ingestion.pcap_parser import PCAPParser
from lated.ingestion.zeek_parser import ZeekParser


SUPPORTED_SOURCES = {"zeek", "pcap", "netflow"}


class IngestionMetrics:
    """Tiny counter bag — kept here to avoid a heavy metrics framework."""

    def __init__(self) -> None:
        self.parsed = 0
        self.accepted = 0
        self.rejected = 0
        self.rejected_reasons: dict[str, int] = {}

    def record_rejection(self, reason: str | None) -> None:
        self.rejected += 1
        key = reason or "unknown"
        self.rejected_reasons[key] = self.rejected_reasons.get(key, 0) + 1


class IngestionService:
    """Drives parser + normalizer + validator and yields CanonicalFlow."""

    def __init__(
        self,
        config,
        host_registry,
        flow_store: FlowStore | None = None,
    ):
        self.config = config
        self.host_registry = host_registry
        self.flow_store = flow_store
        self.normalizer = FlowNormalizer(host_registry)
        self.validator = FlowValidator()
        self.metrics = IngestionMetrics()
        self.parser = self._build_parser()

    def stream(self) -> Iterator[CanonicalFlow]:
        for raw in self.parser.records():
            self.metrics.parsed += 1
            try:
                normalized = self.normalizer.normalize(raw, source_sensor=self.config.source)
            except Exception as exc:  # normalizer must not halt the stream
                self.metrics.record_rejection(f"normalize_error:{type(exc).__name__}")
                continue

            ok, reason = self.validator.is_valid(normalized)
            if not ok:
                self.metrics.record_rejection(reason)
                continue

            try:
                flow = CanonicalSchema.from_normalized(normalized)
            except FlowValidationError as exc:
                self.metrics.record_rejection(f"pydantic:{exc.code}")
                continue

            self.metrics.accepted += 1
            if self.flow_store is not None:
                self.flow_store.append(flow)
            yield flow

    def run(self) -> list[CanonicalFlow]:
        """Drain the stream eagerly (useful for batch replay + tests)."""
        return list(self.stream())

    def _build_parser(self):
        source = self.config.source
        if source not in SUPPORTED_SOURCES:
            raise IngestionError(
                f"ingestion.source={source!r} is not supported by this MVP. "
                f"Supported: {sorted(SUPPORTED_SOURCES)}."
            )
        if source == "zeek":
            zeek_dir = Path(self.config.zeek_log_dir or "")
            if not zeek_dir.exists():
                raise IngestionError(
                    f"ingestion.zeek_log_dir not found: {zeek_dir}"
                )
            return ZeekParser(zeek_dir, mode=getattr(self.config, "mode", "replay"))
        if source == "pcap":
            candidate = Path(self.config.pcap_path or "")
            if getattr(self.config, "mode", "replay") == "replay":
                if not candidate.exists():
                    raise IngestionError(f"ingestion.pcap_path not found: {candidate}")
                return PCAPParser(str(candidate), mode="replay")
            iface = str(self.config.pcap_interface or "")
            if not iface:
                raise IngestionError("ingestion.pcap_interface is required in live pcap mode")
            return PCAPParser(iface, mode="live")
        if source == "netflow":
            replay_path = str(self.config.pcap_path or self.config.zeek_log_dir or "")
            return NetFlowParser(
                port=int(self.config.netflow_port),
                allowlist=[],
                source_path=replay_path or None,
                mode=getattr(self.config, "mode", "replay"),
            )
        raise IngestionError(f"Unhandled source: {source}")
