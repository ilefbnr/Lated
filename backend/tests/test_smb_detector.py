# =============================================================================
# tests/test_smb_detector.py — SMB detector coverage
# =============================================================================

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.schemas import CanonicalFlow
from lated.detection.protocols.smb_detector import SMBDetector


def _flow(
    flow_id: str,
    ts: datetime,
    src: str,
    dst: str,
    dst_port: int = 445,
) -> CanonicalFlow:
    return CanonicalFlow(
        flow_id=flow_id,
        ts=ts,
        src_host=src,
        dst_host=dst,
        src_port=51200,
        dst_port=dst_port,
        protocol="tcp",
        duration=0.5,
        packet_count=40,
        byte_count=2400,
        source_sensor="zeek",
    )


def test_smb_detector_flags_multi_target_smb_activity() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    flows = [
        _flow("s1", base + timedelta(seconds=1), "host-a", "host-b", 445),
        _flow("s2", base + timedelta(seconds=2), "host-a", "host-c", 445),
        _flow("s3", base + timedelta(seconds=3), "host-a", "host-d", 445),
    ]
    scores = SMBDetector(window_seconds=30).run(flows)
    assert len(scores) == 1
    score = scores[0]
    assert score.detector == "smb_detector"
    assert score.protocol == "smb"
    assert "smb_remote_access" in score.triggered_signals
    assert "smb_fanout" in score.triggered_signals
    assert "T1021.002" in score.mitre_tags


def test_smb_detector_ignores_non_smb_flows() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    flows = [
        _flow("n1", base + timedelta(seconds=1), "host-a", "host-b", 80),
        _flow("n2", base + timedelta(seconds=2), "host-a", "host-c", 443),
    ]
    scores = SMBDetector(window_seconds=30).run(flows)
    assert scores == []
