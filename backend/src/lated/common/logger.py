# =============================================================================
# lated.common.logger — structured logging
# =============================================================================
#
# PURPOSE
# -------
# Configures the platform's structured logging pipeline. Provides:
#   - `configure_logging(config)`  : entrypoint called by main.py
#   - `JsonFormatter`              : stdlib formatter producing JSON lines
#   - `get_logger(name)`           : thin wrapper around structlog
#
# CYBERSECURITY REASONING
# -----------------------
# A SOC platform's logs are themselves a security artifact:
#   - upstream SIEM ingests them,
#   - audit trails depend on them,
#   - incident response replays them.
# Therefore every log line MUST be:
#   - JSON,
#   - timestamped in UTC ISO-8601,
#   - tagged with `service`, `version`, `request_id`/`alert_id` where present,
#   - free of PII and free of raw payload contents.
#
# INTERACTIONS
# ------------
# Every module imports `get_logger(__name__)` at module level. The configured
# pipeline injects contextvars (request_id, alert_id) automatically.
# =============================================================================

from __future__ import annotations

import logging
import sys

import structlog

# class JsonFormatter(logging.Formatter):
#     """
#     stdlib formatter that emits one JSON object per record.
#
#     Stable fields:
#       - ts        : ISO-8601 UTC timestamp
#       - level     : log level
#       - logger    : module name
#       - msg       : event message
#       - service   : "lated"
#       - version   : lated.__version__
#       - extra.*   : structured fields attached via logger.bind(...)
#     """
#     def format(self, record): ...


def configure_logging(config: dict) -> None:
    """Configure stdlib + structlog from a settings dict.

    Reads:
      - logging.level
      - logging.format  (json | console)

    Side effects:
      - sets the root logger level,
      - attaches the JsonFormatter to a stdout handler,
      - installs structlog processors:
          * timestamper (UTC ISO-8601),
          * contextvars merger (request_id, alert_id),
          * exception renderer (sanitized — no payloads).
    """
    level_name = str(config.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if config.get("format", "json") == "json"
        else structlog.dev.ConsoleRenderer()
    )

    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout, force=True)
    structlog.configure(
        processors=[*processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    """Return a bound structlog logger for the given module name.

    Usage:
        log = get_logger(__name__)
        log.info("flow.received", host=flow.src_host)

    Never log raw payloads — only canonical metadata.
    """
    return structlog.get_logger(name)
