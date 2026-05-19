# =============================================================================
# lated.pipelines.offline.export_model — package + sign the artifact
# =============================================================================
#
# PURPOSE
# -------
# Final stage. Packages the trained model with metadata, signs it with the
# SOC's private key, and writes the artifact pair (.pt + .sig) to /data/models.
#
# METADATA EMBEDDED
# -----------------
#   - schema_version  : matches common.schemas.SCHEMA_VERSION
#   - feature_set     : edge + node feature names actually used
#   - training_set_hash : SHA-256 of LANL files used
#   - hyperparameters
#   - evaluation_metrics (from evaluate.py)
#   - train_job_id (CI run id, traceable)
#
# CYBERSECURITY REASONING
# -----------------------
# The signing key must NOT live on the training host. The standard flow is:
#   1. Training host produces unsigned .pt + manifest.json.
#   2. Manifest is transferred to a hardened signing host (via approval workflow).
#   3. Signing host produces .sig and ships the pair back.
# This ensures a compromise of the training host alone cannot produce a
# valid signed artifact.
# =============================================================================

from __future__ import annotations


def export(model, metadata: dict, output_dir: str) -> str:
    """Package + write the model. Returns the path to the .pt file.

    Signing is delegated to an external service (see SECURITY.md §4).
    """
    raise NotImplementedError("Architecture skeleton.")
