# =============================================================================
# lated.graph — Temporal Graph Modeling Module
# =============================================================================
#
# ROLE IN ARCHITECTURE
# --------------------
# Transforms a stream of CanonicalFlow records into a sequence of
# TemporalSnapshot objects ready for AI inference.
#
# SUBMODULES
# ----------
#   graph_builder      : top-level orchestrator
#   temporal_graph     : in-memory representation across snapshots
#   snapshot_manager   : time-window control + invariants
#   edge_features      : per-edge feature engineering
#   node_features      : per-node feature engineering
#   graph_store        : persistence + retrieval
#   graph_statistics   : runtime metrics (fan-in/out, density, churn)
#
# CYBERSECURITY REASONING
# -----------------------
# The temporal graph is the only data structure the TGNN sees. Its quality
# directly determines detection quality. Therefore:
#   - snapshots must NOT overlap (architectural invariant -> reproducibility),
#   - features must be deterministic for forensic replay,
#   - the BaselineGraph seeds initial node attributes (helps anomaly scoring).
# =============================================================================
