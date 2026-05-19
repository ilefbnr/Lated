# =============================================================================
# tests/test_recon.py — recon detector coverage
# =============================================================================

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.schemas import CanonicalFlow
from lated.detection.recon.recon_detector import ReconDetector
from lated.detection.recon.sliding_window import SlidingWindow


@dataclass(frozen=True)
class _Thresholds:
    fanout_threshold: int = 5
    port_diversity_threshold: int = 5
    burst_packets_per_sec: int = 50
    low_bytes_per_connection: int = 256
    sequential_probe_min_seq: int = 8


def _flow(
    flow_id: str,
    ts: datetime,
    src: str,
    dst: str,
    src_port: int = 51200,
    dst_port: int = 445,
    packets: int = 10,
    bytes_: int = 1000,
) -> CanonicalFlow:
    return CanonicalFlow(
        flow_id=flow_id,
        ts=ts,
        src_host=src,
        dst_host=dst,
        src_port=src_port,
        dst_port=dst_port,
        protocol="tcp",
        duration=0.5,
        packet_count=packets,
        byte_count=bytes_,
        source_sensor="zeek",
    )


def _scanning_stream() -> list[CanonicalFlow]:
    base = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    flows = []
    # host-attacker probes 10 different destinations on 10 different ports
    for i in range(10):
        flows.append(
            _flow(
                f"f{i}",
                base + timedelta(seconds=1 + i),
                "host-attacker",
                f"host-victim-{i}",
                dst_port=1000 + i,
                packets=500,
                bytes_=200,
            )
        )
    # benign host with light, low-variety traffic
    flows.append(_flow("fb1", base + timedelta(seconds=12), "host-benign", "host-fs", dst_port=445))
    flows.append(_flow("fb2", base + timedelta(seconds=20), "host-benign", "host-fs", dst_port=445))
    return flows


def test_sliding_window_groups_by_host() -> None:
    win = SlidingWindow(size_seconds=60)
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    win.add(_flow("a", base, "host-a", "host-b"))
    win.add(_flow("b", base + timedelta(seconds=2), "host-a", "host-c"))
    # crossing into the next window closes the previous one
    win.add(_flow("c", base + timedelta(seconds=61), "host-a", "host-d"))
    assert win.tick() is True
    assert set(win.subjects()) == {"host-a"}
    assert win.unique_dst("host-a") == {"host-b", "host-c"}


def test_recon_detector_fires_on_scanning_pattern() -> None:
    detector = ReconDetector(_Thresholds(), window_seconds=60)
    scores = detector.run(_scanning_stream())
    attacker = [s for s in scores if s.subject_host == "host-attacker"]
    assert attacker, "Scanning host should be flagged"
    assert "fanout" in attacker[0].triggered_signals
    assert "port_diversity" in attacker[0].triggered_signals
    assert attacker[0].unique_destinations == 10
    assert attacker[0].unique_dst_ports == 10
    assert 0.0 <= attacker[0].score <= 1.0


def test_recon_detector_silent_on_benign_input() -> None:
    detector = ReconDetector(_Thresholds(), window_seconds=60)
    scores = detector.run(_scanning_stream())
    assert all(score.subject_host != "host-benign" for score in scores)


def test_recon_detector_replay_is_deterministic() -> None:
    a = ReconDetector(_Thresholds(), window_seconds=60).run(_scanning_stream())
    b = ReconDetector(_Thresholds(), window_seconds=60).run(_scanning_stream())
    assert [s.model_dump(mode="json") for s in a] == [s.model_dump(mode="json") for s in b]


def test_recon_branch_isolated_from_tgnn_module() -> None:
    import importlib
    recon = importlib.import_module("lated.detection.recon.recon_detector")
    forbidden = ("lated.detection.tgnn",)
    src = Path(recon.__file__).read_text(encoding="utf-8")
    for prefix in forbidden:
        assert prefix not in src, f"recon must not import {prefix}"


def test_burst_signal_uses_packet_rate() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    flows = []
    # 60 flows in 60s window, 100 packets each -> 100pps total
    for i in range(60):
        flows.append(_flow(f"b{i}", base + timedelta(seconds=i), "host-burst", "host-vic", packets=100))
    thresholds = _Thresholds(fanout_threshold=999, port_diversity_threshold=999, burst_packets_per_sec=50)
    scores = ReconDetector(thresholds, window_seconds=60).run(flows)
    assert any("burst" in s.triggered_signals for s in scores)
