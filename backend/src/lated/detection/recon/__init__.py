# =============================================================================
# lated.detection.recon — Reconnaissance Detector
# =============================================================================
#
# SCOPE
# -----
# Heuristic + behavioral detector for INTERNAL RECONNAISSANCE: scanning,
# probing, host/service enumeration BY hosts already inside the network.
#
# STRICT SEPARATION
# -----------------
# This submodule is INDEPENDENT from detection.tgnn:
#   - no shared imports,
#   - no shared state,
#   - no shared model artifacts.
# The two detectors can fail / be disabled / be retrained independently.
#
# FILES
# -----
#   recon_detector     : top-level coordinator
#   fanout_analyzer    : detects unusual destination-count behavior
#   port_diversity     : detects unusual destination-port diversity
#   burst_detector     : detects high packet-rate bursts
#   sliding_window     : reusable sliding-window primitive
#
# CYBERSECURITY REASONING
# -----------------------
# Reconnaissance is typically NOISY in feature space — heuristics work well.
# Using a small set of well-understood signals also gives analysts maximum
# explainability: every alert points to a concrete signal that fired.
# =============================================================================
