# =============================================================================
# tests/test_rdp_winrm_detectors.py — RDP + WinRM protocol detectors
# =============================================================================

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.schemas import CanonicalFlow  # noqa: E402
from lated.detection.protocols.rdp_detector import RDPDetector  # noqa: E402
from lated.detection.protocols.winrm_detector import WinRMDetector  # noqa: E402


def _flow(flow_id: str, ts: datetime, src: str, dst: str, dst_port: int) -> CanonicalFlow:
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


# ----------------------------------------------------------------- RDP
def test_rdp_detector_flags_multi_target_rdp_activity() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    flows = [
        _flow("r1", base + timedelta(seconds=1), "host-a", "host-b", 3389),
        _flow("r2", base + timedelta(seconds=2), "host-a", "host-c", 3389),
        _flow("r3", base + timedelta(seconds=3), "host-a", "host-d", 3389),
    ]
    scores = RDPDetector(window_seconds=30).run(flows)
    assert len(scores) == 1
    score = scores[0]
    assert score.detector == "rdp_detector"
    assert score.protocol == "rdp"
    assert "rdp_remote_access" in score.triggered_signals
    assert "rdp_fanout" in score.triggered_signals
    assert "T1021.001" in score.mitre_tags


def test_rdp_detector_ignores_non_rdp_flows() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    flows = [
        _flow("n1", base + timedelta(seconds=1), "host-a", "host-b", 445),  # SMB, not RDP
        _flow("n2", base + timedelta(seconds=2), "host-a", "host-c", 443),
    ]
    scores = RDPDetector(window_seconds=30).run(flows)
    assert scores == []


def test_rdp_single_target_below_threshold() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    flows = [
        _flow("r1", base + timedelta(seconds=1), "host-a", "host-b", 3389),
    ]
    scores = RDPDetector(window_seconds=30).run(flows)
    # Single target: score = 1/3 ≈ 0.33 -> below min_score_emission (0.35)
    assert scores == []


# ----------------------------------------------------------------- WinRM
def test_winrm_detector_flags_multi_target_winrm_activity() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    flows = [
        _flow("w1", base + timedelta(seconds=1), "host-a", "host-b", 5985),
        _flow("w2", base + timedelta(seconds=2), "host-a", "host-c", 5985),
        _flow("w3", base + timedelta(seconds=3), "host-a", "host-d", 5986),
    ]
    scores = WinRMDetector(window_seconds=30).run(flows)
    assert len(scores) == 1
    score = scores[0]
    assert score.detector == "winrm_detector"
    assert score.protocol == "winrm"
    assert "winrm_remote_access" in score.triggered_signals
    assert "winrm_fanout" in score.triggered_signals
    assert "winrm_tls" in score.triggered_signals  # 5986 observed
    assert "T1021.006" in score.mitre_tags


def test_winrm_detector_ignores_non_winrm_flows() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    flows = [
        _flow("n1", base + timedelta(seconds=1), "host-a", "host-b", 22),
        _flow("n2", base + timedelta(seconds=2), "host-a", "host-c", 80),
    ]
    scores = WinRMDetector(window_seconds=30).run(flows)
    assert scores == []


def test_winrm_no_tls_signal_when_only_5985() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    flows = [
        _flow("w1", base + timedelta(seconds=1), "host-a", "host-b", 5985),
        _flow("w2", base + timedelta(seconds=2), "host-a", "host-c", 5985),
        _flow("w3", base + timedelta(seconds=3), "host-a", "host-d", 5985),
    ]
    scores = WinRMDetector(window_seconds=30).run(flows)
    assert len(scores) == 1
    assert "winrm_tls" not in scores[0].triggered_signals
