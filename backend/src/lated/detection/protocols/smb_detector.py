# =============================================================================
# lated.detection.protocols.smb_detector — SMB lateral movement heuristic
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from lated.common.schemas import CanonicalFlow, DetectorName, DetectionKind, ReconScore
from lated.detection.recon.sliding_window import SlidingWindow


SMB_PORTS = frozenset({139, 445})


@dataclass(frozen=True)
class SMBThresholds:
    min_unique_targets: int = 2
    min_score_emission: float = 0.35
    cross_subnet_bonus: float = 0.15
    service_target_bonus: float = 0.1


class SMBDetector:
    """Heuristic SMB detector over CanonicalFlow windows."""

    def __init__(
        self,
        window_seconds: int = 60,
        thresholds: SMBThresholds | None = None,
    ):
        self.window = SlidingWindow(size_seconds=window_seconds)
        self.thresholds = thresholds or SMBThresholds()

    def score(self, flow_stream: Iterable[CanonicalFlow]) -> Iterator[ReconScore]:
        for flow in flow_stream:
            self.window.add(flow)
            if self.window.tick():
                yield from self._emit_completed_window()
                self.window.consume()
        if self.window.flush():
            yield from self._emit_completed_window()
            self.window.consume()

    def run(self, flow_stream: Iterable[CanonicalFlow]) -> list[ReconScore]:
        return list(self.score(flow_stream))

    def _emit_completed_window(self) -> Iterator[ReconScore]:
        start = self.window.window_start()
        if start is None:
            return
        for subject in self.window.subjects():
            flows = [flow for flow in self.window.flows_for(subject) if flow.dst_port in SMB_PORTS]
            if not flows:
                continue

            unique_targets = sorted({flow.dst_host for flow in flows})
            unique_ports = sorted({flow.dst_port for flow in flows})
            cross_subnet = any(flow.src_host.split('-')[0:1] != flow.dst_host.split('-')[0:1] for flow in flows)
            likely_service_target = any(flow.dst_port == 445 for flow in flows)

            score = min(1.0, len(unique_targets) / max(self.thresholds.min_unique_targets + 1, 3))
            if cross_subnet:
                score += self.thresholds.cross_subnet_bonus
            if likely_service_target:
                score += self.thresholds.service_target_bonus
            score = min(1.0, max(0.0, score))

            if score < self.thresholds.min_score_emission:
                continue

            signals = ["smb_remote_access"]
            if len(unique_targets) >= self.thresholds.min_unique_targets:
                signals.append("smb_fanout")
            if cross_subnet:
                signals.append("cross_subnet_smb")
            if 445 in unique_ports:
                signals.append("smb_admin_service")

            yield ReconScore(
                detector=DetectorName.SMB,
                kind=DetectionKind.LM,
                window_start=start,
                subject_host=subject,
                score=score,
                unique_destinations=len(unique_targets),
                unique_dst_ports=len(unique_ports),
                burst_rate=0.0,
                target_hosts=unique_targets,
                protocol="smb",
                triggered_signals=signals,
                evidence=[
                    f"targets={','.join(unique_targets)}",
                    f"ports={','.join(str(port) for port in unique_ports)}",
                ],
                mitre_tags=["T1021.002"],
                confidence=score,
                critical_asset_touched=likely_service_target,
                new_relation=len(unique_targets) > 0,
            )
