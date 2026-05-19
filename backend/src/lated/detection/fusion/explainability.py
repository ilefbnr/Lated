# =============================================================================
# lated.detection.fusion.explainability — reasoning-trail assembler
# =============================================================================
#
# Produces a stable, JSON-safe dict that travels with every SuspicionScore.
# Shape mirrors `AlertExplainability` in the frontend types so the SOC UI can
# render it without a transform step.
# =============================================================================

from __future__ import annotations

from typing import Any

from lated.common.schemas import LMScore, ReconScore


class Explainability:
    """Builds the explainability payload attached to SuspicionScore."""

    def build(
        self,
        host: str,
        lm_score: LMScore | None,
        recon_score: ReconScore | None,
        history_risk: float,
    ) -> dict[str, Any]:
        lm_section = self._lm_section(lm_score)
        recon_section = self._recon_section(recon_score)
        history_section = {
            "decayed_risk": float(history_risk),
            "last_alert_age_seconds": None,
        }

        return {
            "lm": lm_section,
            "recon": recon_section,
            "history": history_section,
            "detectors": self._detectors_section(lm_score, recon_score),
            "narrative": self._narrative(host, lm_score, recon_score, history_risk),
        }

    @staticmethod
    def _enum_value(value: Any) -> Any:
        return getattr(value, "value", value)

    @staticmethod
    def _lm_section(lm_score: LMScore | None) -> dict[str, Any]:
        if lm_score is None:
            return {"score": 0.0, "top_contributing_edges": [], "model_version": None}
        top = [
            [src, dst, 1.0] for src, dst in lm_score.contributing_edges[:5]
        ]
        return {
            "score": float(lm_score.score),
            "detector": Explainability._enum_value(lm_score.detector),
            "kind": Explainability._enum_value(lm_score.kind),
            "top_contributing_edges": top,
            "target_hosts": list(lm_score.target_hosts),
            "triggered_signals": list(lm_score.triggered_signals),
            "evidence": list(lm_score.evidence),
            "mitre_tags": list(lm_score.mitre_tags),
            "model_version": lm_score.model_version,
        }

    @staticmethod
    def _recon_section(recon_score: ReconScore | None) -> dict[str, Any]:
        if recon_score is None:
            return {
                "score": 0.0,
                "detector": "recon",
                "kind": "reconnaissance",
                "triggered_signals": [],
                "target_hosts": [],
                "evidence": [],
                "mitre_tags": [],
                "unique_destinations": 0,
                "unique_dst_ports": 0,
                "burst_rate": 0.0,
            }
        return {
            "score": float(recon_score.score),
            "detector": Explainability._enum_value(recon_score.detector),
            "kind": Explainability._enum_value(recon_score.kind),
            "triggered_signals": list(recon_score.triggered_signals),
            "target_hosts": list(recon_score.target_hosts),
            "evidence": list(recon_score.evidence),
            "mitre_tags": list(recon_score.mitre_tags),
            "unique_destinations": int(recon_score.unique_destinations),
            "unique_dst_ports": int(recon_score.unique_dst_ports),
            "burst_rate": float(recon_score.burst_rate),
        }

    @staticmethod
    def _detectors_section(
        lm_score: LMScore | None,
        recon_score: ReconScore | None,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for score in (recon_score, lm_score):
            if score is None:
                continue
            out.append(
                {
                    "detector": Explainability._enum_value(score.detector),
                    "kind": Explainability._enum_value(score.kind),
                    "score": float(score.score),
                    "target_hosts": list(getattr(score, "target_hosts", [])),
                    "triggered_signals": list(getattr(score, "triggered_signals", [])),
                    "evidence": list(getattr(score, "evidence", [])),
                    "mitre_tags": list(getattr(score, "mitre_tags", [])),
                }
            )
        return out

    @staticmethod
    def _narrative(
        host: str,
        lm_score: LMScore | None,
        recon_score: ReconScore | None,
        history_risk: float,
    ) -> str:
        bits: list[str] = [f"host {host}"]
        if recon_score is not None and recon_score.triggered_signals:
            bits.append(
                f"recon[{','.join(recon_score.triggered_signals)}]={recon_score.score:.2f}"
            )
        if lm_score is not None:
            bits.append(f"lm={lm_score.score:.2f}")
        if history_risk > 0:
            bits.append(f"history={history_risk:.2f}")
        return " ".join(bits)
