# =============================================================================
# lated.detection.recon.burst_detector — packets-per-second burst signal
# =============================================================================

from __future__ import annotations


class BurstDetector:
    """Fires when a host's outgoing pps in window >= threshold."""

    name = "burst"

    def __init__(self, pps_threshold: int):
        if pps_threshold <= 0:
            raise ValueError("burst pps threshold must be > 0")
        self.pps_threshold = int(pps_threshold)

    def evaluate(self, host_id: str, window) -> tuple[bool, float, float]:
        packets = window.total_packets(host_id)
        window_seconds = window.window_seconds
        pps = packets / window_seconds if window_seconds > 0 else 0.0
        fires = pps >= self.pps_threshold
        score = min(1.0, pps / (2.0 * self.pps_threshold))
        return fires, score, pps
