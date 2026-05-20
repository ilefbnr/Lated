# =============================================================================
# tests/test_rare_edge_detector.py — first-seen relationship detector coverage
# =============================================================================

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.schemas import CanonicalFlow
from lated.detection.protocols.rare_edge_detector import RareEdgeDetector


def _flow(flow_id: str, ts: datetime, src: str, dst: str, dst_port: int = 445) -> CanonicalFlow:
    return CanonicalFlow(
        flow_id=flow_id,
        ts=ts,
        src_host=src,
        dst_host=dst,
        src_port=50000,
        dst_port=dst_port,
        protocol="tcp",
        duration=0.5,
        packet_count=10,
        byte_count=1000,
        source_sensor="zeek",
    )


def test_rare_edge_detector_flags_edge_absent_from_baseline() -> None:
    detector = RareEdgeDetector(window_seconds=30, baseline_edges={("host-a", "host-b")})
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    flows = [
        _flow("r1", base + timedelta(seconds=1), "host-a", "host-b", 445),
        _flow("r2", base + timedelta(seconds=2), "host-a", "host-c", 445),
    ]
    scores = detector.run(flows)
    assert len(scores) == 1
    score = scores[0]
    assert score.detector == "rare_edge_detector"
    assert score.new_relation is True
    assert "first_seen_edge" in score.triggered_signals
    assert score.target_hosts == ["host-c"]


def test_rare_edge_detector_does_not_repeat_same_runtime_edge() -> None:
    detector = RareEdgeDetector(window_seconds=30, baseline_edges=set())
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    first = detector.run([_flow("r1", base + timedelta(seconds=1), "host-a", "host-c", 445)])
    second = detector.run([_flow("r2", base + timedelta(seconds=31), "host-a", "host-c", 445)])
    assert len(first) == 1
    assert second == []
