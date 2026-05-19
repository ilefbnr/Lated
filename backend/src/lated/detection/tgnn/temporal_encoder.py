# =============================================================================
# lated.detection.tgnn.temporal_encoder — time-aware host history encoder
# =============================================================================
#
# PURPOSE
# -------
# Builds, per host, an embedding that captures its behavior across the recent
# sequence of windows (e.g. last K snapshots). This is what makes the model
# "Temporal" — not just spatial.
#
# INPUTS
# ------
#   - Current TemporalSnapshot
#   - History buffer of past embeddings (per host)
#
# OUTPUTS
# -------
#   - per-host history-aware embedding tensor
#
# INTERACTIONS
# ------------
#   - tgnn_model : composes this with graph_encoder.
#
# CYBERSECURITY REASONING
# -----------------------
# Lateral movement is a TEMPORAL phenomenon — a single suspicious flow is
# rarely conclusive. Patterns over time (a host suddenly connecting to many
# admin services it never touched before) carry the real signal. The
# temporal encoder is therefore the heart of LM detection.
# =============================================================================

from __future__ import annotations


class TemporalEncoder:
    """Encodes per-host history into time-aware embeddings.

    Real implementation would use TemporalAttention + TimeEncoding from
    tgnn_layers. Skeleton only.
    """

    def __init__(self, dim: int, heads: int, history_window: int):
        ...

    def forward(self, snapshot, history):
        raise NotImplementedError("Architecture skeleton.")
