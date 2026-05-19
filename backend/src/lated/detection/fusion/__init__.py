# =============================================================================
# lated.detection.fusion — Local Suspicion Fusion Engine
# =============================================================================
#
# ROLE
# ----
# Combines the outputs of the two independent detectors (LM + recon) plus
# host history into a single SuspicionScore. Provides explainability metadata
# so the SOC UI can show "why is this host suspicious right now".
#
# FILES
# -----
#   suspicion_fusion   : weighted combination, lightweight + explainable
#   risk_scorer        : per-host historical risk with time decay
#   explainability     : assembles the human-readable reasoning trail
#
# CYBERSECURITY REASONING
# -----------------------
# Fusion is the ONLY module that depends on BOTH detectors. It is deliberately
# simple (weighted sum + bounded contributions) — complex fusion would
# obscure why an alert fired, defeating SOC explainability.
# =============================================================================
