# =============================================================================
# tests/test_correlation.py — correlation MVP coverage
# =============================================================================

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.schemas import SuspicionScore
from lated.correlation.correlation_engine import CorrelationEngine
from lated.correlation.correlation_store import CorrelationStore, session_factory_for
from lated.correlation.graph_adjacency import StaticAdjacency
from lated.correlation.pivot_identifier import PivotIdentifier
from lated.correlation.timeline_reconstructor import TimelineReconstructor


@dataclass(frozen=True)
class _Cfg:
    temporal_continuity_seconds: int = 300
    max_path_length: int = 8
    enable_mitre_tags: bool = True
    min_path_confidence: float = 0.5
    pivot_min_neighbors: int = 1


BASE = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _suspicion(
    host: str,
    offset_seconds: int,
    score: float = 0.8,
    recon_signals: list[str] | None = None,
    lm_contribution: float = 0.0,
    recon_contribution: float = 0.8,
) -> SuspicionScore:
    explain = {
        "lm": {"score": 0.0, "top_contributing_edges": []},
        "recon": {
            "score": recon_contribution,
            "triggered_signals": recon_signals or ["fanout"],
            "unique_destinations": 12,
            "unique_dst_ports": 8,
            "burst_rate": 33.0,
        },
        "history": {"decayed_risk": 0.0, "last_alert_age_seconds": None},
        "narrative": f"recon on {host}",
    }
    return SuspicionScore(
        window_start=BASE + timedelta(seconds=offset_seconds),
        subject_host=host,
        score=score,
        lm_contribution=lm_contribution,
        recon_contribution=recon_contribution,
        history_contribution=0.0,
        explainability=explain,
    )


def _adjacency_chain() -> StaticAdjacency:
    return StaticAdjacency(
        edges=[
            ("host-a", "host-b"),
            ("host-b", "host-c"),
            ("host-c", "host-d"),
        ]
    )


def test_correlation_emits_path_on_connected_temporal_sequence() -> None:
    events = [
        _suspicion("host-a", 0),
        _suspicion("host-b", 60),
        _suspicion("host-c", 120),
    ]
    results = CorrelationEngine(_Cfg(), _adjacency_chain()).run(events)
    assert len(results) == 1
    path = results[0].path
    assert path.hosts == ["host-a", "host-b", "host-c"]
    assert abs(path.path_confidence - 0.8) < 1e-9


def test_correlation_skips_gap_beyond_continuity_window() -> None:
    cfg = _Cfg(temporal_continuity_seconds=60)
    events = [
        _suspicion("host-a", 0),
        _suspicion("host-b", 600),  # too late — gap of 10 minutes
    ]
    results = CorrelationEngine(cfg, _adjacency_chain()).run(events)
    # Two separate single-host candidates -> nothing emitted (need >=2 hosts)
    assert results == []


def test_correlation_does_not_merge_unconnected_hosts() -> None:
    # host-x and host-y are not graph-adjacent
    adjacency = StaticAdjacency(edges=[("host-a", "host-b")])
    events = [
        _suspicion("host-a", 0),
        _suspicion("host-x", 60),  # not adjacent to host-a -> separate path
    ]
    results = CorrelationEngine(_Cfg(), adjacency).run(events)
    # Both candidates have single hosts -> nothing emitted
    assert results == []


def test_correlation_replay_is_deterministic() -> None:
    events = [
        _suspicion("host-a", 0),
        _suspicion("host-b", 60),
        _suspicion("host-c", 120),
    ]
    a = CorrelationEngine(_Cfg(), _adjacency_chain()).run(events)
    b = CorrelationEngine(_Cfg(), _adjacency_chain()).run(events)
    assert [r.path.model_dump(mode="json") for r in a] == [
        r.path.model_dump(mode="json") for r in b
    ]


def test_correlation_filters_below_confidence_threshold() -> None:
    cfg = _Cfg(min_path_confidence=0.85)
    events = [
        _suspicion("host-a", 0, score=0.6),
        _suspicion("host-b", 60, score=0.6),
    ]
    assert CorrelationEngine(cfg, _adjacency_chain()).run(events) == []


def test_pivot_identifier_tags_mid_path_host() -> None:
    events = [
        _suspicion("host-a", 0),
        _suspicion("host-b", 60),
        _suspicion("host-c", 120),
        _suspicion("host-d", 180),
    ]
    results = CorrelationEngine(_Cfg(), _adjacency_chain()).run(events)
    assert len(results) == 1
    path = results[0].path
    assert "host-b" in path.pivot_hosts
    assert "host-c" in path.pivot_hosts
    assert "host-a" not in path.pivot_hosts
    assert "host-d" not in path.pivot_hosts


def test_pivot_identifier_returns_empty_for_short_paths() -> None:
    adjacency = StaticAdjacency(edges=[("host-a", "host-b")])
    events = [_suspicion("host-a", 0), _suspicion("host-b", 30)]
    results = CorrelationEngine(_Cfg(), adjacency).run(events)
    assert len(results) == 1
    assert results[0].path.pivot_hosts == []


def test_timeline_reconstructor_orders_steps_chronologically() -> None:
    events = [
        _suspicion("host-a", 0, recon_signals=["fanout"]),
        _suspicion("host-b", 60, recon_signals=["port_diversity"]),
        _suspicion("host-c", 120, recon_signals=["burst"]),
    ]
    [result] = CorrelationEngine(_Cfg(), _adjacency_chain()).run(events)
    timeline = result.timeline
    assert [step["subject_host"] for step in timeline] == ["host-a", "host-b", "host-c"]
    assert [step["step"] for step in timeline] == [1, 2, 3]
    assert timeline[0]["mitre_tags"] == ["T1018"]
    assert timeline[1]["mitre_tags"] == ["T1046"]
    assert timeline[2]["mitre_tags"] == ["T1595"]
    assert timeline[0]["target_hosts"] == ["host-b"]


def test_propagation_metadata_reflects_graph_support() -> None:
    events = [
        _suspicion("host-a", 0),
        _suspicion("host-b", 60),
        _suspicion("host-c", 120),
    ]
    [result] = CorrelationEngine(_Cfg(), _adjacency_chain()).run(events)
    assert result.propagation["host_count"] == 3
    assert result.propagation["graph_supported_steps"] == 2
    assert result.propagation["propagation_ratio"] == 1.0


def test_correlation_store_persists_into_supervision_tables(tmp_path) -> None:
    events = [
        _suspicion("host-a", 0),
        _suspicion("host-b", 60),
        _suspicion("host-c", 120),
    ]
    [result] = CorrelationEngine(_Cfg(), _adjacency_chain()).run(events)

    db_path = tmp_path / "supervision.sqlite3"
    factory = session_factory_for(db_path)
    store = CorrelationStore(factory)
    store.save(result)

    with factory() as connection:
        paths = connection.execute("SELECT * FROM attack_paths").fetchall()
        alerts = connection.execute("SELECT * FROM alerts").fetchall()

    assert len(paths) == 1
    assert paths[0]["path_id"] == result.path.path_id
    assert len(alerts) == len(result.path.timeline)


def test_pivot_identifier_unit_returns_only_real_pivots() -> None:
    # Direct unit test bypassing the engine.
    adjacency = StaticAdjacency(edges=[("host-a", "host-b"), ("host-b", "host-c")])
    from lated.correlation.attack_path_builder import PathCandidate

    candidate = PathCandidate(
        path_id="path-test",
        steps=[
            _suspicion("host-a", 0),
            _suspicion("host-b", 30),
            _suspicion("host-c", 60),
        ],
        hosts=["host-a", "host-b", "host-c"],
    )
    pivots = PivotIdentifier(min_neighbors=1).identify(candidate, adjacency)
    assert pivots == ["host-b"]
