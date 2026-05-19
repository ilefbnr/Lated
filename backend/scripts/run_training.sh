#!/usr/bin/env bash
# =============================================================================
# scripts/run_training.sh — offline training entrypoint
# =============================================================================
# Purpose:
#   Run the full offline training pipeline:
#     1. lated-train     (self-supervised pretraining)
#     2. lated-finetune  (LM fine-tuning)
#     3. evaluate + export_model
#
# Run on a dedicated training host with the `train` extras installed.
# =============================================================================
set -euo pipefail
echo "[train] Architecture skeleton."
# pip install -e .[train]
# lated-train
# lated-finetune
# python -m lated.pipelines.offline.evaluate
# python -m lated.pipelines.offline.export_model
