# =============================================================================
# lated.detection.recon.fanout_analyzer — unique-destination signal
# =============================================================================

from __future__ import annotations


class FanoutAnalyzer:
    """Fires when a host contacted >= threshold unique destinations in window."""

    name = "fanout"

    def __init__(self, threshold: int):
        if threshold <= 0:
            raise ValueError("fanout threshold must be > 0")
        self.threshold = int(threshold)

    def evaluate(self, host_id: str, window) -> tuple[bool, float, int]:
        count = len(window.unique_dst(host_id))
        fires = count >= self.threshold
        score = min(1.0, count / (2.0 * self.threshold))
        return fires, score, count
