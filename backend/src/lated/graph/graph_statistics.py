# =============================================================================
# lated.graph.graph_statistics — runtime graph metrics
# =============================================================================
#
# PURPOSE
# -------
# Computes high-level statistics about the temporal graph for:
#   - operational monitoring (graph density, edge churn rate),
#   - explainability (per-host fan-in/out for alert context),
#   - capacity planning (size growth over time).
#
# INPUTS  : TemporalGraph or TemporalSnapshot
# OUTPUTS : dict of named metrics (Prometheus-friendly)
#
# CYBERSECURITY REASONING
# -----------------------
# Graph metrics are themselves a detection signal:
#   - sudden density jump can indicate a worm,
#   - sustained edge churn rate spike can indicate active scanning.
# These are not used for alerting directly (kept simple here) but the
# correlation engine consumes them for context.
# =============================================================================

from __future__ import annotations


class GraphStatistics:
    """Computes named graph metrics.

    Metrics produced
    ----------------
      node_count, edge_count, density, mean_degree, max_degree,
      edge_churn_per_window, isolated_node_count
    """

    def __init__(self):
        ...

    def compute(self, snapshot) -> dict:
        raise NotImplementedError("Architecture skeleton.")
