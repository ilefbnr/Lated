# =============================================================================
# lated.correlation — Correlation Module
# =============================================================================
#
# ROLE
# ----
# Reconstructs MULTI-STEP attack paths from the SuspicionScore stream.
# Single alerts are useful — but a SOC analyst really needs the CHAIN:
#
#   "Host A scanned subnet B at 10:01, then pivoted into host C at 10:04,
#    then C reached the file server at 10:08."
#
# This is the module that produces that chain.
#
# FILES
# -----
#   correlation_engine     : top-level coordinator
#   attack_path_builder    : assembles paths from suspicion events
#   pivot_identifier       : flags hosts that are mid-path bridges
#   timeline_reconstructor : builds chronological narratives
#   propagation_analyzer   : analyzes how suspicion propagates over the graph
#
# CYBERSECURITY REASONING
# -----------------------
# Lateral movement is, by definition, a sequence. Detecting individual hops
# without their chain produces noise; producing the full chain produces a
# single high-confidence incident that an analyst can act on immediately.
# =============================================================================
