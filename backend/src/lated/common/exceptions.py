# =============================================================================
# lated.common.exceptions — platform-wide exception hierarchy
# =============================================================================
#
# PURPOSE
# -------
# Defines a single, organized exception tree so:
#   - logs/alerts can carry a stable `error.code`,
#   - upstream handlers (FastAPI exception handlers) can map exceptions to
#     HTTP status codes without branching on string messages,
#   - tests can match on the exception class, not the wording.
#
# DESIGN
# ------
# - `LatedError` is the base; never raise it directly — always a subclass.
# - Each subclass groups errors of the same KIND (parsing, model, security).
# - Every subclass sets a unique `code` class attribute for log correlation.
# =============================================================================

from __future__ import annotations


class LatedError(Exception):
    """Base for every exception raised inside LateD."""
    code: str = "LATED_ERR"


# -----------------------------------------------------------------------------
# Configuration / bootstrap
# -----------------------------------------------------------------------------
class ConfigError(LatedError):
    """Configuration is missing, malformed, or out of allowed range."""
    code = "CONFIG_ERR"


# -----------------------------------------------------------------------------
# Ingestion — failures at the untrusted/trusted boundary
# -----------------------------------------------------------------------------
class IngestionError(LatedError):
    code = "INGEST_ERR"


class ParserError(IngestionError):
    """Source telemetry could not be parsed (corrupted / unknown format)."""
    code = "INGEST_PARSE_ERR"


class FlowValidationError(IngestionError):
    """Parsed flow failed schema validation — never propagated downstream."""
    code = "INGEST_VALIDATION_ERR"


# -----------------------------------------------------------------------------
# Graph
# -----------------------------------------------------------------------------
class GraphError(LatedError):
    code = "GRAPH_ERR"


class SnapshotError(GraphError):
    """Snapshot construction or invariant violation (e.g. overlap)."""
    code = "GRAPH_SNAPSHOT_ERR"


# -----------------------------------------------------------------------------
# Detection
# -----------------------------------------------------------------------------
class DetectionError(LatedError):
    code = "DETECT_ERR"


class ModelLoadError(DetectionError):
    """TGNN model artifact missing, unreadable, or signature mismatch."""
    code = "DETECT_MODEL_LOAD_ERR"


class InferenceError(DetectionError):
    """Inference failed for a specific snapshot. Logged, not crashing."""
    code = "DETECT_INFERENCE_ERR"


# -----------------------------------------------------------------------------
# Correlation
# -----------------------------------------------------------------------------
class CorrelationError(LatedError):
    code = "CORR_ERR"


# -----------------------------------------------------------------------------
# Supervision / API
# -----------------------------------------------------------------------------
class SupervisionError(LatedError):
    code = "SUP_ERR"


class AuthError(SupervisionError):
    """REST or WebSocket authentication / authorization failure."""
    code = "SUP_AUTH_ERR"


class AlertEmissionError(SupervisionError):
    """Alert could not be persisted or fanned out."""
    code = "SUP_ALERT_ERR"
