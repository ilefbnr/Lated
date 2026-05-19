# =============================================================================
# lated.detection.recon.port_diversity — unique dst-port signal
# =============================================================================

from __future__ import annotations


class PortDiversityAnalyzer:
    """Fires when a host probed >= threshold distinct dst ports in window."""

    name = "port_diversity"

    def __init__(self, threshold: int):
        if threshold <= 0:
            raise ValueError("port_diversity threshold must be > 0")
        self.threshold = int(threshold)

    def evaluate(self, host_id: str, window) -> tuple[bool, float, int]:
        count = len(window.unique_dst_ports(host_id))
        fires = count >= self.threshold
        score = min(1.0, count / (2.0 * self.threshold))
        return fires, score, count
