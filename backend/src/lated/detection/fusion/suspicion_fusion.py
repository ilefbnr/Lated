# =============================================================================
# lated.detection.fusion.suspicion_fusion — weighted score combiner
# =============================================================================
#
# Joins LMScore and ReconScore streams by (subject_host, window_start) and
# produces SuspicionScore. A missing branch is imputed to zero — fail safe:
# absent data must NOT inflate suspicion artificially.
#
# Contributions:
#   lm_contribution      = w_lm   * lm_score
#   recon_contribution   = w_rec  * recon_score
#   history_contribution = w_hist * history_risk
#   total                = clamp(sum, 0, 1)
#
# After emission, the RiskScorer is updated with the new total + window_start
# so the host's history reflects the most recent suspicion.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator

from lated.common.schemas import LMScore, ReconScore, SuspicionScore

from lated.detection.fusion.explainability import Explainability
from lated.detection.fusion.risk_scorer import RiskScorer


@dataclass(frozen=True)
class FusionWeights:
    lm: float
    recon: float
    history: float


class SuspicionFusion:
    """Weighted fusion of LM, recon, and historical-risk signals."""

    def __init__(
        self,
        config,
        risk_scorer: RiskScorer,
        explainability: Explainability | None = None,
    ):
        self.weights = self._coerce_weights(config)
        self.risk_scorer = risk_scorer
        self.explainability = explainability or Explainability()

    def fuse(
        self,
        lm_scores: Iterable[LMScore],
        recon_scores: Iterable[ReconScore],
    ) -> Iterator[SuspicionScore]:
        lm_index: dict[tuple[str, datetime], LMScore] = {}
        for item in lm_scores:
            lm_index[(item.subject_host, _normalize(item.window_start))] = item

        recon_index: dict[tuple[str, datetime], ReconScore] = {}
        for item in recon_scores:
            recon_index[(item.subject_host, _normalize(item.window_start))] = item

        keys = sorted(set(lm_index) | set(recon_index))
        for host, window_start in keys:
            lm = lm_index.get((host, window_start))
            recon = recon_index.get((host, window_start))
            history = self.risk_scorer.read(host, window_start)

            lm_contrib = self.weights.lm * (lm.score if lm is not None else 0.0)
            recon_contrib = self.weights.recon * (recon.score if recon is not None else 0.0)
            history_contrib = self.weights.history * history

            total = self._clamp(lm_contrib + recon_contrib + history_contrib)

            explain = self.explainability.build(host, lm, recon, history)

            suspicion = SuspicionScore(
                window_start=window_start,
                subject_host=host,
                score=total,
                lm_contribution=lm_contrib,
                recon_contribution=recon_contrib,
                history_contribution=history_contrib,
                explainability=explain,
            )
            self.risk_scorer.update(host, total, window_start)
            yield suspicion

    def run(
        self,
        lm_scores: Iterable[LMScore],
        recon_scores: Iterable[ReconScore],
    ) -> list[SuspicionScore]:
        return list(self.fuse(lm_scores, recon_scores))

    @staticmethod
    def _coerce_weights(config) -> FusionWeights:
        lm = getattr(config, "weight_lm", None)
        recon = getattr(config, "weight_recon", None)
        history = getattr(config, "weight_history", None)
        if lm is None and isinstance(config, dict):
            lm = config.get("weight_lm")
            recon = config.get("weight_recon")
            history = config.get("weight_history")
        if lm is None or recon is None or history is None:
            raise ValueError("FusionWeights require weight_lm/weight_recon/weight_history")
        return FusionWeights(float(lm), float(recon), float(history))

    @staticmethod
    def _clamp(value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return float(value)


def _normalize(ts: datetime) -> datetime:
    from datetime import timezone
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)
