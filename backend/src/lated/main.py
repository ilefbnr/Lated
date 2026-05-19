# =============================================================================
# lated.main — process entrypoints
# =============================================================================
#
# PURPOSE
# -------
# Provides the small number of "main" functions wired to the console_scripts
# entry points declared in pyproject.toml. This module is intentionally thin —
# it owns process bootstrapping ONLY:
#
#   - load configuration
#   - configure logging
#   - construct the appropriate top-level service
#   - delegate to its run() method
#
# It does NOT contain detection logic, route handlers, or model code.
#
# ENTRY POINTS
# ------------
#   lated-api        -> run_api()       — supervision (FastAPI + WebSocket)
#   lated-online     -> see pipelines.online.pipeline_runner
#   lated-train      -> see pipelines.offline.pretrain_ssl
#   lated-finetune   -> see pipelines.offline.finetune_lm
#
# DEPLOYMENT ROLE
# ---------------
# This is the file invoked by the container `CMD` (Dockerfile) and by SOC
# operators when running services manually for debugging.
#
# INTERACTIONS
# ------------
# - `common.config_manager`  : loads settings.yaml + env overrides
# - `common.logger`          : configures structlog
# - `supervision.api.app`    : the ASGI application
#
# CYBERSECURITY REASONING
# -----------------------
# Centralizing bootstrap in one file lets us audit, in a single place:
#   - WHICH env the process is running in,
#   - WHICH model artifact is loaded,
#   - WHICH thresholds are active.
# A single audit log line covers the entire startup posture of the process.
# =============================================================================

from __future__ import annotations

from pathlib import Path

import uvicorn

from lated.common.config_manager import ConfigManager
from lated.common.logger import configure_logging, get_logger
from lated.supervision.api.app import create_app


def _config_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2]
    config_dir = root / "config"
    return config_dir / "settings.yaml", config_dir / "detection_thresholds.yaml"


def run_api() -> None:
    """Start the FastAPI + WebSocket supervision service.

    Steps (no implementation here — see linked modules):
      1. Load configuration via ConfigManager.
      2. Configure structured logging.
      3. Build the ASGI app from `supervision.api.app:create_app`.
      4. Hand off to uvicorn.

    This function is the target of the `lated-api` console script.
    """
    settings_path, thresholds_path = _config_paths()
    config = ConfigManager.load(str(settings_path), str(thresholds_path))
    configure_logging({"level": config.logging.level, "format": config.logging.format})
    log = get_logger(__name__)
    app = create_app(config)
    log.info(
        "api.starting",
        env=config.env,
        host=config.api.host,
        port=config.api.port,
        heartbeat_seconds=config.supervision.ws_heartbeat_seconds,
    )
    uvicorn.run(app, host=config.api.host, port=config.api.port)


def run_online() -> None:
    """Start the online detection pipeline orchestrator.

    See `lated.pipelines.online.pipeline_runner`.
    """
    raise NotImplementedError("Architecture skeleton.")
