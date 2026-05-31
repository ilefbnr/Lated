# =============================================================================
# lated.detection.protocols.winrm_detector — WinRM lateral movement heuristic
# =============================================================================
#
# Mirrors `smb_detector.py`. Targets MITRE T1021.006 (Windows Remote Management).
# Triggers when a host initiates WinRM (5985 / 5986) sessions to multiple
# targets in a short window — a common modern alternative to SMB-based pivots
# (used heavily by PowerShell remoting and red-team tooling).
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from lated.common.schemas import CanonicalFlow, DetectorName, DetectionKind, ReconScore
from lated.detection.recon.sliding_window import SlidingWindow


WINRM_PORTS = frozenset({5985, 5986})
WINRM_TLS_PORT = 5986


@dataclass(frozen=True)
class WinRMThresholds:
    min_unique_targets: int = 2
    min_score_emission: float = 0.35
    cross_subnet_bonus: float = 0.15
    tls_bonus: float = 0.05  # prefer 5986 (TLS) — often used by tooling


class WinRMDetector:
    """Heuristic WinRM detector over CanonicalFlow windows."""

    def __init__(
        self,
        window_seconds: int = 60,
        thresholds: WinRMThresholds | None = None,
    ):
        self.window = SlidingWindow(size_seconds=window_seconds)
        self.thresholds = thresholds or WinRMThresholds()

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
            flows = [
                flow for flow in self.window.flows_for(subject)
                if flow.dst_port in WINRM_PORTS
            ]
            if not flows:
                continue

            unique_targets = sorted({flow.dst_host for flow in flows})
            unique_ports = sorted({flow.dst_port for flow in flows})
            cross_subnet = any(
                flow.src_host.split('-')[0:1] != flow.dst_host.split('-')[0:1]
                for flow in flows
            )
            tls_observed = any(flow.dst_port == WINRM_TLS_PORT for flow in flows)

            score = min(1.0, len(unique_targets) / max(self.thresholds.min_unique_targets + 1, 3))
            if cross_subnet:
                score += self.thresholds.cross_subnet_bonus
            if tls_observed:
                score += self.thresholds.tls_bonus
            score = min(1.0, max(0.0, score))

            if score < self.thresholds.min_score_emission:
                continue

            signals = ["winrm_remote_access"]
            if len(unique_targets) >= self.thresholds.min_unique_targets:
                signals.append("winrm_fanout")
            if cross_subnet:
                signals.append("cross_subnet_winrm")
            if tls_observed:
                signals.append("winrm_tls")

            yield ReconScore(
                detector=DetectorName.WINRM,
                kind=DetectionKind.LM,
                window_start=start,
                subject_host=subject,
                score=score,
                unique_destinations=len(unique_targets),
                unique_dst_ports=len(unique_ports),
                burst_rate=0.0,
                target_hosts=unique_targets,
                protocol="winrm",
                triggered_signals=signals,
                evidence=[
                    f"targets={','.join(unique_targets)}",
                    f"ports={','.join(str(port) for port in unique_ports)}",
                ],
                mitre_tags=["T1021.006"],
                confidence=score,
                critical_asset_touched=False,
                new_relation=len(unique_targets) > 0,
            )
