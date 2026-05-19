# =============================================================================
# lated.detection.tgnn.lm_classifier — LM scoring head
# =============================================================================
#
# PURPOSE
# -------
# The final head producing an LM score in [0, 1] per host (or per edge).
# Trained with semi-supervised loss against LANL redteam labels.
#
# INPUTS  : final per-host embedding
# OUTPUTS : LMScore (with explainability metadata)
#
# CYBERSECURITY REASONING
# -----------------------
# Calibration matters more than raw accuracy in SOC: a 0.91 score must mean
# something stable to the analyst. The head's training loss therefore
# includes a calibration term (temperature scaling) and the validation
# pipeline reports Brier / ECE alongside AUC.
# =============================================================================

from __future__ import annotations


class LMClassifier:
    """LM scoring head.

    Forward output (skeleton)
    -------------------------
      {
        "score": float in [0, 1],
        "contributing_edges": list[(src, dst)],
        "attention_map": dict[(src, dst)] -> float,
      }
    """

    def __init__(self, dim: int):
        ...

    def forward(self, embeddings):
        raise NotImplementedError("Architecture skeleton.")
