# =============================================================================
# lated.detection.tgnn.tgnn_layers — reusable TGNN building blocks
# =============================================================================
#
# PURPOSE
# -------
# Houses the parameterized layer types used by both the temporal and graph
# encoders. Keeping them in one file allows reuse across training experiments
# without duplicating implementations.
#
# LAYER FAMILIES (skeletons)
# --------------------------
#   TemporalAttention   : self-attention over the history of a host/edge.
#   GraphAttention      : attention-based neighborhood aggregation.
#   GatedUpdate         : GRU-style hidden state update per node.
#   EdgeMLP             : per-edge MLP for feature transformation.
#   TimeEncoding        : sinusoidal / learnable time embedding.
#
# CYBERSECURITY REASONING
# -----------------------
# Attention layers are particularly valuable here: they make the model's
# attention weights inspectable, which feeds explainability metadata. SOC
# analysts can ask "WHY does the model think host X is suspicious?" and the
# attention map points to a small subset of edges + time steps.
# =============================================================================

from __future__ import annotations


# class TemporalAttention(nn.Module):
#     """Self-attention over the sequence of past windows for a single node."""
#     def __init__(self, dim, heads): ...
#     def forward(self, history_embeddings): ...


# class GraphAttention(nn.Module):
#     """Per-node aggregation of neighbor embeddings weighted by attention."""
#     def __init__(self, dim, heads): ...
#     def forward(self, node_emb, edge_emb, adjacency): ...


# class GatedUpdate(nn.Module):
#     """GRU-style update for node hidden state across time steps."""
#     def __init__(self, dim): ...
#     def forward(self, prev_state, new_message): ...


# class EdgeMLP(nn.Module):
#     """MLP transforming raw edge features into edge embeddings."""
#     def __init__(self, in_dim, out_dim): ...
#     def forward(self, edge_features): ...


# class TimeEncoding(nn.Module):
#     """Sinusoidal / learnable embedding of timestamps."""
#     def __init__(self, dim): ...
#     def forward(self, timestamps): ...
