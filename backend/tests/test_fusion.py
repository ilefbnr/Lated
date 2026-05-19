# =============================================================================
# tests/test_fusion.py — risk + explainability + suspicion fusion coverage
# =============================================================================

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.schemas import LMScore, ReconScore
from lated.detection.fusion.explainability import Explainability
from lated.detection.fusion.risk_scorer import RiskScorer
from lated.detection.fusion.suspicion_fusion import SuspicionFusion


@dataclass(frozen=True)
class _FusionCfg:
    weight_lm: float = 0.6
    weight_recon: float = 0.3
    weight_history: float = 0.1


def _lm(host: str, ts: datetime, score: float = 0.8) -> LMScore:
    return LMScore(
        window_start=ts,
        subject_host=host,
        score=score,
        contributing_edges=[(host, "host-x"), (host, "host-y")],
        model_version="placeholder-1",
        explainability={"fan_out": 3.0},
    )


def _recon(host: str, ts: datetime, score: float = 0.5, signals: list[str] | None = None) -> ReconScore:
    return ReconScore(
        window_start=ts,
        subject_host=host,
        score=score,
        unique_destinations=12,
        unique_dst_ports=8,
        burst_rate=33.0,
        triggered_signals=signals or ["fanout"],
    )


def test_risk_scorer_decays_linearly() -> None:
    scorer = RiskScorer(decay_per_hour=0.1)
    t0 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    scorer.update("host-a", 0.8, t0)

    later = t0 + timedelta(hours=2)
    decayed = scorer.read("host-a", later)
    assert abs(decayed - 0.6) < 1e-9

    much_later = t0 + timedelta(hours=20)
    assert scorer.read("host-a", much_later) == 0.0


def test_risk_scorer_keeps_max_over_new_update() -> None:
    scorer = RiskScorer(decay_per_hour=0.0)
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    scorer.update("host-a", 0.4, t0)
    scorer.update("host-a", 0.2, t0 + timedelta(hours=1))
    assert scorer.read("host-a", t0 + timedelta(hours=1)) == 0.4
    scorer.update("host-a", 0.9, t0 + timedelta(hours=2))
    assert scorer.read("host-a", t0 + timedelta(hours=2)) == 0.9


def test_risk_scorer_bounded_to_unit_interval() -> None:
    scorer = RiskScorer(decay_per_hour=0.5)
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    scorer.update("host-a", 5.0, t0)  # over 1.0 — must clamp
    assert scorer.read("host-a", t0) == 1.0


def test_explainability_payload_structure() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    payload = Explainability().build("host-a", _lm("host-a", ts), _recon("host-a", ts), history_risk=0.2)
    assert set(payload.keys()) == {"lm", "recon", "history", "detectors", "narrative"}
    assert payload["lm"]["score"] == 0.8
    assert payload["recon"]["triggered_signals"] == ["fanout"]
    assert payload["history"]["decayed_risk"] == 0.2
    assert payload["detectors"][0]["detector"] == "recon"
    assert "host-a" in payload["narrative"]


def test_fusion_combines_with_explicit_contributions() -> None:
    cfg = _FusionCfg()
    scorer = RiskScorer(decay_per_hour=0.0)
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    suspicions = SuspicionFusion(cfg, scorer).run(
        lm_scores=[_lm("host-a", ts, score=1.0)],
        recon_scores=[_recon("host-a", ts, score=1.0)],
    )
    assert len(suspicions) == 1
    susp = suspicions[0]
    assert abs(susp.lm_contribution - 0.6) < 1e-9
    assert abs(susp.recon_contribution - 0.3) < 1e-9
    assert susp.history_contribution == 0.0  # no prior history
    assert abs(susp.score - 0.9) < 1e-9


def test_fusion_imputes_zero_for_missing_lm_branch() -> None:
    cfg = _FusionCfg()
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    suspicions = SuspicionFusion(cfg, RiskScorer(decay_per_hour=0.0)).run(
        lm_scores=[],
        recon_scores=[_recon("host-a", ts, score=0.8)],
    )
    assert len(suspicions) == 1
    assert suspicions[0].lm_contribution == 0.0
    assert abs(suspicions[0].recon_contribution - 0.3 * 0.8) < 1e-9


def test_fusion_imputes_zero_for_missing_recon_branch() -> None:
    cfg = _FusionCfg()
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    suspicions = SuspicionFusion(cfg, RiskScorer(decay_per_hour=0.0)).run(
        lm_scores=[_lm("host-a", ts, score=0.9)],
        recon_scores=[],
    )
    assert len(suspicions) == 1
    assert suspicions[0].recon_contribution == 0.0
    assert abs(suspicions[0].lm_contribution - 0.6 * 0.9) < 1e-9


def test_fusion_updates_risk_scorer_after_emission() -> None:
    cfg = _FusionCfg()
    scorer = RiskScorer(decay_per_hour=0.0)
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    SuspicionFusion(cfg, scorer).run(
        lm_scores=[_lm("host-a", ts, score=1.0)],
        recon_scores=[_recon("host-a", ts, score=1.0)],
    )
    # post-fusion history reflects the latest suspicion (0.9 from previous test config)
    assert scorer.read("host-a", ts) > 0.0


def test_fusion_score_bounded_to_unit_interval() -> None:
    # Force overshoot by inflating history
    cfg = _FusionCfg(weight_lm=1.0, weight_recon=1.0, weight_history=1.0)
    scorer = RiskScorer(decay_per_hour=0.0)
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    scorer.update("host-a", 1.0, ts)
    suspicions = SuspicionFusion(cfg, scorer).run(
        lm_scores=[_lm("host-a", ts, score=1.0)],
        recon_scores=[_recon("host-a", ts, score=1.0)],
    )
    assert suspicions[0].score == 1.0


def test_fusion_replay_is_deterministic() -> None:
    cfg = _FusionCfg()
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    a = SuspicionFusion(cfg, RiskScorer(decay_per_hour=0.0)).run(
        [_lm("host-a", ts, 0.7)], [_recon("host-a", ts, 0.5)]
    )
    b = SuspicionFusion(cfg, RiskScorer(decay_per_hour=0.0)).run(
        [_lm("host-a", ts, 0.7)], [_recon("host-a", ts, 0.5)]
    )
    assert [s.model_dump(mode="json") for s in a] == [s.model_dump(mode="json") for s in b]
