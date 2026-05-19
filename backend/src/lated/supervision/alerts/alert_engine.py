# =============================================================================
# lated.supervision.alerts.alert_engine — alert factory + emitter
# =============================================================================
#
# Consumes SuspicionScore + (optional) CorrelationResult batches. For every
# event above the suspicion threshold:
#
#   - build an Alert (deterministic alert_id from (host, kind, window_start))
#   - persist via AlertRepository (INSERT OR REPLACE — replay-safe)
#   - publish a WSEvent through EventPublisher.publish_sync:
#       * alert.new on first sighting within the dedup window,
#       * alert.update on subsequent updates within the dedup window.
#
# Dedup is keyed on (host, kind). Repeated events within
# `dedup_window_seconds` bump the same alert instead of flooding the SOC.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from lated.common.constants import (
    EVT_ALERT_NEW,
    EVT_ALERT_UPDATE,
    EVT_PATH_NEW,
    WS_CHANNEL_ALERTS,
    WS_CHANNEL_TIMELINE,
)
from lated.common.schemas import (
    Alert,
    AttackPath,
    DetectionKind,
    SuspicionScore,
    WSChannel,
    WSEvent,
    WSEventName,
)
from lated.supervision.alerts.severity_mapper import SeverityMapper


def _normalize(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _stable_alert_id(host: str, kind: str, window_start: datetime) -> str:
    return f"alert-{kind}-{host}-{_normalize(window_start).strftime('%Y%m%dT%H%M%SZ')}"


class AlertEngine:
    """Builds + emits Alert objects from suspicion / correlation streams."""

    def __init__(
        self,
        repository,
        publisher,
        severity_mapper: SeverityMapper | None = None,
        suspicion_threshold: float = 0.5,
        dedup_window_seconds: int = 300,
    ):
        self.repository = repository
        self.publisher = publisher
        self.severity_mapper = severity_mapper or SeverityMapper()
        self.suspicion_threshold = float(suspicion_threshold)
        self.dedup_window = timedelta(seconds=int(dedup_window_seconds))
        self._recent: dict[tuple[str, str], tuple[str, datetime]] = {}
        self.metrics = {
            "alerts_emitted": 0,
            "alerts_updated": 0,
            "alerts_dropped_low_score": 0,
            "paths_published": 0,
        }

    def consume(
        self,
        suspicions: Iterable[SuspicionScore],
        correlation_results: Iterable | None = None,
    ) -> list[Alert]:
        emitted: list[Alert] = []
        sorted_suspicions = sorted(
            suspicions, key=lambda s: (_normalize(s.window_start), s.subject_host)
        )
        for suspicion in sorted_suspicions:
            alert = self._handle_suspicion(suspicion)
            if alert is not None:
                emitted.append(alert)

        for result in correlation_results or []:
            alert = self._handle_correlation_result(result)
            if alert is not None:
                emitted.append(alert)

        return emitted

    def _handle_suspicion(self, suspicion: SuspicionScore) -> Alert | None:
        if suspicion.score < self.suspicion_threshold:
            self.metrics["alerts_dropped_low_score"] += 1
            return None

        kind = (
            DetectionKind.LM.value
            if suspicion.lm_contribution >= suspicion.recon_contribution
            else DetectionKind.RECON.value
        )
        ts = _normalize(suspicion.window_start)
        dedup_key = (suspicion.subject_host, kind)
        previous = self._recent.get(dedup_key)
        is_update = previous is not None and (ts - previous[1]) <= self.dedup_window

        alert_id = previous[0] if is_update else _stable_alert_id(
            suspicion.subject_host, kind, ts
        )
        severity = self.severity_mapper.map(suspicion.score, suspicion.subject_host, 0)
        recon_section = (suspicion.explainability or {}).get("recon", {})
        evidence = list(recon_section.get("evidence", []))

        alert = Alert(
            alert_id=alert_id,
            created_at=ts,
            severity=severity,
            kind=kind,
            subject_host=suspicion.subject_host,
            description=f"suspicion score {suspicion.score:.2f} on {suspicion.subject_host}",
            score=suspicion.score,
            evidence=evidence,
            mitre_tags=self._mitre_for_recon(recon_section.get("triggered_signals", [])),
            explainability=dict(suspicion.explainability or {}),
            status="open",
        )
        self.repository.insert(alert)
        self._recent[dedup_key] = (alert_id, ts)

        event_name = WSEventName.ALERT_UPDATE if is_update else WSEventName.ALERT_NEW
        self._publish(WSChannel.ALERTS, event_name, alert.model_dump(mode="json"), ts)

        if is_update:
            self.metrics["alerts_updated"] += 1
        else:
            self.metrics["alerts_emitted"] += 1
        return alert

    def _handle_correlation_result(self, result) -> Alert | None:
        path: AttackPath = result.path
        timeline = getattr(result, "timeline", []) or []
        ts = _normalize(path.created_at)
        kind = DetectionKind.CORRELATION.value
        dedup_key = (path.path_id, kind)
        previous = self._recent.get(dedup_key)
        is_update = previous is not None and (ts - previous[1]) <= self.dedup_window

        alert_id = previous[0] if is_update else f"alert-{kind}-{path.path_id}"
        severity = self.severity_mapper.map(path.path_confidence, path.hosts[0] if path.hosts else "", len(path.hosts))

        alert = Alert(
            alert_id=alert_id,
            created_at=ts,
            severity=severity,
            kind=kind,
            subject_host=path.hosts[0] if path.hosts else "unknown",
            description=f"attack path with {len(path.hosts)} hosts (confidence={path.path_confidence:.2f})",
            score=path.path_confidence,
            evidence=[step_alert.alert_id for step_alert in path.timeline],
            mitre_tags=list(path.mitre_tactic_chain),
            explainability={
                "hosts": list(path.hosts),
                "pivot_hosts": list(path.pivot_hosts),
                "propagation": getattr(result, "propagation", {}),
                "timeline_steps": timeline,
            },
            status="open",
        )
        self.repository.insert(alert)
        self._recent[dedup_key] = (alert_id, ts)

        event_name = WSEventName.ALERT_UPDATE if is_update else WSEventName.ALERT_NEW
        self._publish(WSChannel.ALERTS, event_name, alert.model_dump(mode="json"), ts)
        self._publish(
            WSChannel.TIMELINE,
            WSEventName.PATH_NEW,
            {
                "path_id": path.path_id,
                "hosts": list(path.hosts),
                "path_confidence": path.path_confidence,
                "timeline": timeline,
            },
            ts,
        )

        if is_update:
            self.metrics["alerts_updated"] += 1
        else:
            self.metrics["alerts_emitted"] += 1
        self.metrics["paths_published"] += 1
        return alert

    def _publish(self, channel: WSChannel, event_name: WSEventName, payload: dict, ts: datetime) -> None:
        if self.publisher is None:
            return
        event = WSEvent(channel=channel, event=event_name, payload=payload, ts=ts)
        publish_sync = getattr(self.publisher, "publish_sync", None)
        if publish_sync is not None:
            publish_sync(event)

    @staticmethod
    def _mitre_for_recon(signals) -> list[str]:
        mapping = {"fanout": "T1018", "port_diversity": "T1046", "burst": "T1595"}
        out: list[str] = []
        for signal in signals or []:
            tag = mapping.get(signal)
            if tag and tag not in out:
                out.append(tag)
        return out
