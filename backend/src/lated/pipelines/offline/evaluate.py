# =============================================================================
# lated.pipelines.offline.evaluate — held-out evaluation
# =============================================================================
#
# PURPOSE
# -------
# Computes the metrics reported with every model release:
#
#   - AUC-ROC  : ranking quality
#   - AUC-PR   : ranking quality on imbalanced data (more honest than ROC)
#   - Precision @ K  : what fraction of top-K alerts were true positives
#   - Recall @ K     : what fraction of true positives appear in top-K
#   - Brier score    : calibration
#   - ECE            : expected calibration error
#
# Also produces:
#   - Per-subnet breakdown
#   - Confusion vs. attack stage (recon vs. LM only)
#
# OUTPUTS
# -------
#   - evaluation_report.json (embedded in model metadata)
#   - figures (PNG) for the release notes
#
# CYBERSECURITY REASONING
# -----------------------
# AUC-PR + calibration metrics matter MORE than raw accuracy in SOC:
#   - accuracy looks great when 99.99% of traffic is benign,
#   - what matters is "of my top-50 alerts today, how many were real?"
# =============================================================================

from __future__ import annotations


def evaluate(model, test_dataset) -> dict:
    """Run held-out evaluation and return the metrics dict."""
    raise NotImplementedError("Architecture skeleton.")
