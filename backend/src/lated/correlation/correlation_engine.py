# =============================================================================
# lated.correlation.correlation_engine — top-level correlator
# =============================================================================
#
# Sync, deterministic correlator. Consumes a SuspicionScore stream and emits
# AttackPath objects.
#
# Pipeline:
#   1. AttackPathBuilder.extend() — append the event to any matching path or
#      seed a new candidate. Temporal + host + graph continuity all apply.
#   2. After consuming the full stream, build final AttackPath objects from
#      every candidate that:
#         - contains >= 2 distinct hosts (single-host incidents stay as raw
#           suspicion alerts; correlation only deals with multi-host chains),
#         - has confidence >= min_path_confidence.
#   3. PivotIdentifier + PropagationAnalyzer run on each emitted candidate.
#   4. TimelineReconstructor builds the structured timeline payload (kept
#      alongside the AttackPath for downstream consumers — the model itself
#      only stores Alert objects in `timeline`).
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Iterator

from lated.common.schemas import (
    Alert,
    AttackPath,
    DetectionKind,
    Severity,
    SuspicionScore,
)

from lated.correlation.attack_path_builder import AttackPathBuilder, PathCandidate
from lated.correlation.pivot_identifier import PivotIdentifier
from lated.correlation.propagation_analyzer import PropagationAnalyzer
from lated.correlation.timeline_reconstructor import TimelineReconstructor


MITRE_FROM_RECON_SIGNAL = {
    "fanout": "T1018",            # Remote System Discovery
    "port_diversity": "T1046",    # Network Service Scanning
    "burst": "T1595",             # Active Scanning
}


@dataclass
class CorrelationResult:
    """An emitted AttackPath plus its structured timeline payload."""

    path: AttackPath
    timeline: list[dict]
    propagation: dict


class CorrelationEngine:
    """Coordinates path reconstruction from a SuspicionScore stream."""

    def __init__(
        self,
        config,
        adjacency,
        min_path_confidence: float | None = None,
        enable_mitre_tags: bool | None = None,
        pivot_min_neighbors: int | None = None,
    ):
        self.continuity_seconds = int(getattr(config, "temporal_continuity_seconds", 600))
        self.max_path_length = int(getattr(config, "max_path_length", 8))
        if min_path_confidence is None:
            min_path_confidence = float(getattr(config, "min_path_confidence", 0.5))
        if enable_mitre_tags is None:
            enable_mitre_tags = bool(getattr(config, "enable_mitre_tags", True))
        if pivot_min_neighbors is None:
            pivot_min_neighbors = int(getattr(config, "pivot_min_neighbors", 1))

        self.min_path_confidence = float(min_path_confidence)
        self.adjacency = adjacency
        self.builder = AttackPathBuilder(self.continuity_seconds, self.max_path_length)
        self.pivot_identifier = PivotIdentifier(pivot_min_neighbors)
        self.propagation = PropagationAnalyzer()
        self.timeline = TimelineReconstructor(enable_mitre_tags=enable_mitre_tags)

    def correlate(self, suspicion_stream: Iterable[SuspicionScore]) -> Iterator[CorrelationResult]:
        sorted_events = sorted(
            suspicion_stream,
            key=lambda s: (_normalize(s.window_start), s.subject_host),
        )

        in_progress: list[PathCandidate] = []
        for event in sorted_events:
            in_progress = self.builder.extend(event, in_progress, self.adjacency)

        for candidate in in_progress:
            if len(set(candidate.hosts)) < 2:
                continue
            if candidate.confidence < self.min_path_confidence:
                continue
            yield self._finalize(candidate)

    def run(self, suspicion_stream: Iterable[SuspicionScore]) -> list[CorrelationResult]:
        return list(self.correlate(suspicion_stream))

    def _finalize(self, candidate: PathCandidate) -> CorrelationResult:
        alerts = [self._suspicion_to_alert(step) for step in candidate.steps]
        mitre_chain = self._mitre_chain(alerts)
        pivots = self.pivot_identifier.identify(candidate, self.adjacency)
        propagation_metadata = self.propagation.analyze(candidate, self.adjacency)

        path = AttackPath(
            path_id=candidate.path_id,
            created_at=_normalize(candidate.first_ts),
            hosts=list(candidate.hosts),
            pivot_hosts=pivots,
            timeline=alerts,
            path_confidence=min(1.0, max(0.0, candidate.confidence)),
            mitre_tactic_chain=mitre_chain,
        )
        timeline = self.timeline.build(path)
        return CorrelationResult(path=path, timeline=timeline, propagation=propagation_metadata)

    @staticmethod
    def _suspicion_to_alert(step: SuspicionScore) -> Alert:
        recon = (step.explainability or {}).get("recon", {}) if step.explainability else {}
        signals = list(recon.get("triggered_signals", []))
        mitre_tags: list[str] = []
        for signal in signals:
            tag = MITRE_FROM_RECON_SIGNAL.get(signal)
            if tag and tag not in mitre_tags:
                mitre_tags.append(tag)

        severity = (
            Severity.CRITICAL.value
            if step.score >= 0.9
            else Severity.HIGH.value
            if step.score >= 0.75
            else Severity.MEDIUM.value
            if step.score >= 0.5
            else Severity.LOW.value
        )
        kind = (
            DetectionKind.LM.value
            if step.lm_contribution >= step.recon_contribution
            else DetectionKind.RECON.value
        )
        alert_id = f"alert-corr-{step.subject_host}-{_normalize(step.window_start).strftime('%Y%m%dT%H%M%SZ')}"
        return Alert(
            alert_id=alert_id,
            created_at=_normalize(step.window_start),
            severity=severity,
            kind=kind,
            subject_host=step.subject_host,
            description=f"correlated suspicion on {step.subject_host} (score={step.score:.2f})",
            score=step.score,
            evidence=[],
            mitre_tags=mitre_tags,
            explainability=step.explainability or {},
            status="open",
        )

    @staticmethod
    def _mitre_chain(alerts: list[Alert]) -> list[str]:
        seen: list[str] = []
        for alert in alerts:
            for tag in alert.mitre_tags:
                if tag not in seen:
                    seen.append(tag)
        return seen


def _normalize(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
