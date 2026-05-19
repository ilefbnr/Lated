# =============================================================================
# lated.detection.tgnn.tgnn_model — top-level TGNN model
# =============================================================================
#
# PURPOSE
# -------
# Composes the full TGNN architecture from its building blocks:
#
#     TemporalSnapshot
#         |
#         v
#     [temporal_encoder]   ── encode time-aware embeddings of node/edge histories
#         |
#         v
#     [graph_encoder]      ── spatial message passing over the current snapshot
#         |
#         v
#     [lm_classifier]      ── per-host (or per-edge) lateral-movement score
#         |
#         v
#     LMScore
#
# This file declares the nn.Module skeleton ONLY. No real algorithms.
#
# INPUTS
# ------
#   - TemporalSnapshot (with NodeFeatures + EdgeFeatures + recent history)
#
# OUTPUTS
# -------
#   - LMScore per host or edge
#   - optional embeddings (for explainability + UI visualization)
#
# INTERACTIONS
# ------------
#   - tgnn_inference : runtime user.
#   - pipelines.offline.pretrain_ssl / finetune_lm : training users.
#
# CYBERSECURITY REASONING
# -----------------------
# The architecture is intentionally specialized: lateral movement only.
# Multi-task heads were rejected because:
#   - they tempt operators into trusting an under-trained task,
#   - failure modes blur — analyst cannot tell which task misfired,
#   - LM is the highest-leverage detection target post-compromise.
# =============================================================================

from __future__ import annotations


class TGNNModel:
    """Top-level TGNN composer.

    Real implementation would subclass torch.nn.Module. Skeleton only here.

    Composition
    -----------
      self.temporal_encoder = TemporalEncoder(...)
      self.graph_encoder    = GraphEncoder(...)
      self.lm_classifier    = LMClassifier(...)

    Forward
    -------
      forward(snapshot, history) -> dict:
        emb = temporal_encoder(snapshot, history)
        emb = graph_encoder(snapshot, emb)
        return lm_classifier(emb)
    """

    def __init__(self, config: dict):
        ...

    def forward(self, snapshot, history):
        raise NotImplementedError("Architecture skeleton.")
