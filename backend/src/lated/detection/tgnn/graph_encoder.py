# =============================================================================
# lated.detection.tgnn.graph_encoder — spatial message passing
# =============================================================================
#
# PURPOSE
# -------
# Performs message passing over the current TemporalSnapshot so each host's
# embedding reflects its immediate neighborhood (1-2 hops).
#
# INPUTS
# ------
#   - TemporalSnapshot (nodes, edges, features)
#   - Time-aware embeddings from temporal_encoder
#
# OUTPUTS
# -------
#   - per-host spatial+temporal embedding
#
# CYBERSECURITY REASONING
# -----------------------
# Lateral movement spreads along the graph. Knowing your neighbors' behavior
# helps disambiguate "I am suspicious because I am near other suspicious
# hosts" vs. "I am suspicious in isolation". Both matter, but the former
# is the classic LM signature.
# =============================================================================

from __future__ import annotations


class GraphEncoder:
    """Spatial encoder using GraphAttention from tgnn_layers."""

    def __init__(self, dim: int, layers: int, heads: int):
        ...

    def forward(self, snapshot, node_embeddings):
        raise NotImplementedError("Architecture skeleton.")
