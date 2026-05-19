# =============================================================================
# lated — top-level package
# =============================================================================
#
# PURPOSE
# -------
# Marks `lated` as a Python package and exposes the package version.
# The version string is consumed by:
#   - the /health endpoint (so SOC operators can verify the deployed build),
#   - the model loader (compatibility check against tgnn_lm.pt metadata),
#   - structured log lines (`service.version` field).
#
# IMPORTANT
# ---------
# No business logic. No side-effectful imports. Importing this package must
# never trigger I/O, model loading, or network calls — that property is what
# allows the test suite to import any submodule cheaply.
# =============================================================================

__version__ = "0.1.0"
