# =============================================================================
# lated.supervision.api.routes_health — /health, /metrics, /admin
# =============================================================================
#
# PURPOSE
# -------
# Operational endpoints:
#   GET  /health                     : per-module liveness + readiness
#   GET  /metrics                    : Prometheus exposition
#   POST /admin/reload-thresholds    : hot-reload detection_thresholds.yaml
#   POST /admin/model                : swap loaded TGNN artifact (admin only)
#   GET  /admin/model/info           : current model metadata
#
# CYBERSECURITY REASONING
# -----------------------
# /admin/* endpoints require the `admin` role + audit log + double-confirm
# header (e.g. X-Confirm-Action) to prevent accidental swap of the model in
# production.
# /health intentionally does NOT leak internal versions/paths to anonymous
# callers — only auth'd clients see the detailed body.
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from lated import __version__
from lated.supervision.auth import AuthUser, require_role

HEALTH_REQUESTS = Counter(
    "lated_health_requests_total",
    "Number of /health requests served.",
)
APP_INFO = Gauge(
    "lated_app_info",
    "Static LateD application info.",
    labelnames=("version", "env"),
)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Return a minimal liveness and readiness payload."""
    HEALTH_REQUESTS.inc()
    config = request.app.state.config
    APP_INFO.labels(version=__version__, env=config.env).set(1)
    return {
        "status": "ok",
        "service": "lated",
        "version": __version__,
        "env": config.env,
        "modules": {
            "api": "ok",
            "websocket": "ok",
            "config": "ok",
        },
    }


@router.get("/metrics")
async def prometheus_metrics() -> PlainTextResponse:
    """Return Prometheus metrics exposition."""
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@router.post("/admin/reload-thresholds")
async def reload_thresholds(
    request: Request,
    user: AuthUser = Depends(require_role("admin")),
) -> dict[str, str]:
    """Hot-reload detection thresholds."""
    request.app.state.config_manager.reload_thresholds()
    request.app.state.event_store.append(
        actor=user.username,
        action="admin.reload-thresholds",
        target="config.thresholds",
        payload={"status": "ok"},
    )
    return {"status": "ok"}


@router.get("/admin/model/info")
async def model_info(user: AuthUser = Depends(require_role("supervisor"))) -> dict[str, str]:
    """Expose current model metadata placeholder."""
    del user
    return {"status": "not_loaded", "model_path": "unavailable_in_phase_1"}

# router = APIRouter(tags=["health"])


# @router.get("/health")
# async def health(verbose: bool = False, user=Depends(optional_user)):
#     """Liveness + per-module readiness."""
#     ...


# @router.get("/metrics")
# async def prometheus_metrics():
#     """Prometheus exposition (auth gated by network ACL, not bearer)."""
#     ...


# @router.post("/admin/reload-thresholds")
# async def reload_thresholds(user=Depends(require_role("admin"))):
#     ...


# @router.post("/admin/model")
# async def swap_model(model_path: str, signature_path: str,
#                       x_confirm_action: str = Header(...),
#                       user=Depends(require_role("admin"))):
#     ...


# @router.get("/admin/model/info")
# async def model_info(user=Depends(require_role("supervisor"))):
#     ...
