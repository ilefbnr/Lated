# =============================================================================
# lated.detection.protocols.rare_edge_detector — first-seen relationship detector
# =============================================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from lated.common.schemas import CanonicalFlow, DetectorName, DetectionKind, ReconScore
from lated.detection.recon.sliding_window import SlidingWindow


@dataclass(frozen=True)
class RareEdgeThresholds:
    min_score_emission: float = 0.3
    cross_subnet_bonus: float = 0.1
    privileged_port_bonus: float = 0.1


class RareEdgeDetector:
    """Flags host-to-host relationships absent from the known baseline."""

    def __init__(
        self,
        window_seconds: int = 60,
        baseline_edges: set[tuple[str, str]] | None = None,
        thresholds: RareEdgeThresholds | None = None,
    ):
        self.window = SlidingWindow(size_seconds=window_seconds)
        self.thresholds = thresholds or RareEdgeThresholds()
        self.baseline_edges = set(baseline_edges or ())
        self._seen_runtime_edges: set[tuple[str, str]] = set(self.baseline_edges)

    @classmethod
    def from_baseline_path(
        cls,
        baseline_path: str | Path | None,
        window_seconds: int = 60,
        thresholds: RareEdgeThresholds | None = None,
    ) -> "RareEdgeDetector":
        edges: set[tuple[str, str]] = set()
        if baseline_path is not None:
            path = Path(baseline_path)
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                for edge in payload.get("edges", []):
                    src = edge.get("src")
                    dst = edge.get("dst")
                    if isinstance(src, str) and isinstance(dst, str):
                        edges.add((src, dst))
        return cls(window_seconds=window_seconds, baseline_edges=edges, thresholds=thresholds)

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
            subject_flows = self.window.flows_for(subject)
            novel = []
            for flow in subject_flows:
                edge = (flow.src_host, flow.dst_host)
                if edge in self._seen_runtime_edges:
                    continue
                novel.append(flow)

            if not novel:
                continue

            targets = sorted({flow.dst_host for flow in novel})
            score = min(1.0, 0.35 + 0.15 * max(0, len(targets) - 1))
            cross_subnet = any(self._subnet(flow.src_host) != self._subnet(flow.dst_host) for flow in novel)
            if cross_subnet:
                score += self.thresholds.cross_subnet_bonus
            privileged_ports = {53, 88, 135, 389, 445, 636, 3389, 5985, 5986}
            touched_privileged = any(flow.dst_port in privileged_ports for flow in novel)
            if touched_privileged:
                score += self.thresholds.privileged_port_bonus
            score = min(1.0, max(0.0, score))

            if score < self.thresholds.min_score_emission:
                continue

            for flow in novel:
                self._seen_runtime_edges.add((flow.src_host, flow.dst_host))

            signals = ["first_seen_edge"]
            if cross_subnet:
                signals.append("cross_subnet_first_seen")
            if touched_privileged:
                signals.append("privileged_service_first_seen")

            yield ReconScore(
                detector=DetectorName.RARE_EDGE,
                kind=DetectionKind.LM,
                window_start=start,
                subject_host=subject,
                score=score,
                unique_destinations=len(targets),
                unique_dst_ports=len({flow.dst_port for flow in novel}),
                burst_rate=0.0,
                target_hosts=targets,
                protocol=(novel[0].protocol if novel else None),
                triggered_signals=signals,
                evidence=[f"{flow.src_host}->{flow.dst_host}:{flow.dst_port}" for flow in novel[:8]],
                confidence=score,
                critical_asset_touched=touched_privileged,
                new_relation=True,
            )

    @staticmethod
    def _subnet(host_id: str) -> str:
        return host_id.split("-")[0] if "-" in host_id else host_id
