# =============================================================================
# lated.common — cross-cutting primitives
# =============================================================================
# Contains modules that are imported by ALL other packages:
#   - schemas         : canonical Pydantic models (CanonicalFlow, Alert, ...)
#   - constants       : MITRE tags, severity levels, channel names
#   - exceptions      : platform-wide exception hierarchy
#   - logger          : structlog configuration
#   - config_manager  : layered YAML + env configuration loader
#
# These modules MUST NOT import any other lated.* package — they sit at the
# bottom of the dependency graph. Enforced by import-time discipline.
# =============================================================================
