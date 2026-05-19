# =============================================================================
# lated.detection.recon.recon_detector — heuristic recon coordinator
# =============================================================================
#
# Subscribes directly to a CanonicalFlow stream (NOT to TemporalSnapshot), so
# a failure in the graph/LM branch cannot silence recon. Emits ReconScore per
# (host, window) when any heuristic fires.
#
# Scoring: each analyzer returns a [0,1] partial score. The host's overall
# recon score is the mean of the three analyzer scores in this MVP — that
# both rewards multi-signal incidents and keeps single-signal scores modest.
# Bounded to [0, 1].
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator

from lated.common.schemas import CanonicalFlow, ReconScore

from lated.detection.recon.burst_detector import BurstDetector
from lated.detection.recon.fanout_analyzer import FanoutAnalyzer
from lated.detection.recon.port_diversity import PortDiversityAnalyzer
from lated.detection.recon.sliding_window import SlidingWindow


@dataclass(frozen=True)
class _Thresholds:
    fanout: int
    port_diversity: int
    burst_pps: int


class ReconDetector:
    """Heuristic recon signal coordinator."""

    def __init__(
        self,
        thresholds,
        window_seconds: int = 60,
        step_seconds: int | None = None,
    ):
        cfg = self._coerce_thresholds(thresholds)
        self.thresholds = cfg
        self.fanout = FanoutAnalyzer(cfg.fanout)
        self.port_diversity = PortDiversityAnalyzer(cfg.port_diversity)
        self.burst = BurstDetector(cfg.burst_pps)
        self.window = SlidingWindow(size_seconds=window_seconds, step_seconds=step_seconds)

    def score(self, flow_stream: Iterable[CanonicalFlow]) -> Iterator[ReconScore]:
        for flow in flow_stream:
            self.window.add(flow)
            if self.window.tick():
                yield from self._emit_for_current_completed()
                self.window.consume()
        if self.window.flush():
            yield from self._emit_for_current_completed()
            self.window.consume()

    def run(self, flow_stream: Iterable[CanonicalFlow]) -> list[ReconScore]:
        return list(self.score(flow_stream))

    def _emit_for_current_completed(self) -> Iterator[ReconScore]:
        start = self.window.window_start()
        if start is None:
            return
        for host in self.window.subjects():
            fan_fired, fan_score, unique_dst = self.fanout.evaluate(host, self.window)
            port_fired, port_score, unique_ports = self.port_diversity.evaluate(host, self.window)
            burst_fired, burst_score, burst_rate = self.burst.evaluate(host, self.window)

            triggered: list[str] = []
            if fan_fired:
                triggered.append(self.fanout.name)
            if port_fired:
                triggered.append(self.port_diversity.name)
            if burst_fired:
                triggered.append(self.burst.name)
            if not triggered:
                continue

            combined = min(1.0, max(0.0, (fan_score + port_score + burst_score) / 3.0))
            yield ReconScore(
                window_start=start,
                subject_host=host,
                score=combined,
                unique_destinations=unique_dst,
                unique_dst_ports=unique_ports,
                burst_rate=float(burst_rate),
                target_hosts=sorted(self.window.unique_dst(host)),
                triggered_signals=triggered,
                evidence=[
                    f"unique_destinations={unique_dst}",
                    f"unique_dst_ports={unique_ports}",
                    f"burst_rate={float(burst_rate):.2f}",
                ],
            )

    @staticmethod
    def _coerce_thresholds(thresholds) -> _Thresholds:
        # Accept either ReconThresholds (config dataclass), a dict, or anything with attrs.
        fanout = getattr(thresholds, "fanout_threshold", None)
        port_diversity = getattr(thresholds, "port_diversity_threshold", None)
        burst_pps = getattr(thresholds, "burst_packets_per_sec", None)
        if fanout is None and isinstance(thresholds, dict):
            fanout = thresholds.get("fanout_threshold")
            port_diversity = thresholds.get("port_diversity_threshold")
            burst_pps = thresholds.get("burst_packets_per_sec")
        if fanout is None or port_diversity is None or burst_pps is None:
            raise ValueError("thresholds must expose fanout/port_diversity/burst keys")
        return _Thresholds(int(fanout), int(port_diversity), int(burst_pps))
