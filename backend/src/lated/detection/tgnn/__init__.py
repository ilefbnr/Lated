# =============================================================================
# lated.detection.tgnn — Temporal Graph Neural Network LM Detector
# =============================================================================
#
# SPECIALIZATION
# --------------
# This submodule is EXCLUSIVELY responsible for lateral movement detection.
# It MUST NOT contain heuristics for reconnaissance, exfiltration, or any
# other tactic. Specialization yields:
#   - smaller hypothesis class -> better generalization on LANL,
#   - cleaner explainability ("the TGNN said this is LM"),
#   - decoupled retraining cycles.
#
# FILES
# -----
#   tgnn_model         : top-level nn.Module composing the architecture
#   tgnn_layers        : reusable building blocks (graph + temporal)
#   temporal_encoder   : time-aware embedding of edge/node history
#   graph_encoder      : spatial message passing over the snapshot
#   lm_classifier      : final head producing the LM score
#   tgnn_inference     : runtime inference wrapper (online pipeline)
#   model_loader       : signed-artifact loading + version check
#
# LEARNING STRATEGY
# -----------------
#   1. Self-supervised pretraining   (pipelines/offline/pretrain_ssl)
#   2. Semi-supervised LM fine-tuning (pipelines/offline/finetune_lm)
#   3. Evaluation                    (pipelines/offline/evaluate)
#
# CYBERSECURITY REASONING
# -----------------------
# Model artifacts are signed (see SECURITY.md §4). model_loader refuses to
# load an unsigned or mismatched artifact at startup — a sealed-model
# property critical for SOC-grade deployments.
# =============================================================================
