# =============================================================================
# lated.pipelines.offline — Training Pipeline
# =============================================================================
#
# PURPOSE
# -------
# Produces the signed TGNN model artifact (`tgnn_lm.pt` + `tgnn_lm.sig`) from
# the LANL dataset. Strictly separated from online detection — different
# image, different container, different machine in production.
#
# STAGES
# ------
#   lanl_parser       : parses LANL flows + redteam logs
#   weak_labeler      : turns redteam logs into per-edge labels
#   dataset_builder   : builds train/val/test datasets of TemporalSnapshots
#   pretrain_ssl      : self-supervised pretraining (no labels)
#   finetune_lm       : semi-supervised LM fine-tuning (weak labels)
#   evaluate          : produces AUC / PR / calibration metrics
#   export_model      : packages, signs, and writes the final artifact
#
# CYBERSECURITY REASONING
# -----------------------
# - Training runs in an isolated environment (no access to prod telemetry,
#   only to the LANL corpus on disk).
# - The signing key for the artifact NEVER lives on the same host as the
#   training job — signing happens on a separate, hardened host.
# =============================================================================
