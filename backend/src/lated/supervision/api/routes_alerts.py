# =============================================================================
# lated.supervision.api.routes_alerts — /alerts endpoints
# =============================================================================
#
# PURPOSE
# -------
# REST surface for the alert engine. Backed by `alerts.alert_repository`.
#
# ENDPOINTS
# ---------
#   GET  /alerts                 : paginated list, filterable by severity/host/time
#   GET  /alerts/{alert_id}      : full alert + explainability payload
#   POST /alerts/{alert_id}/ack  : acknowledge (RBAC: analyst+)
#   POST /alerts/{alert_id}/close: close with disposition (RBAC: supervisor+)
#
# INPUTS  : query params (filters), path params (alert_id), bodies (disposition)
# OUTPUTS : JSON Alert objects (see common.schemas.Alert)
#
# CYBERSECURITY REASONING
# -----------------------
# Alerts contain analyst-sensitive metadata (target hosts, evidence ids).
# RBAC + audit logging is mandatory on every mutating endpoint.
# =============================================================================

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request

from lated.supervision.auth import AuthUser, get_current_user, require_role

router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(get_current_user)])


@router.get("")
async def list_alerts(
    request: Request,
    severity: list[str] | None = Query(default=None),
    host: str | None = None,
    since: str | None = None,
    until: str | None = None,
    page: int = 1,
):
    """Paginated alert listing. Filters compose with AND semantics."""
    rows, total = request.app.state.alert_repository.list(
        {
            "severity": severity or [],
            "host": host,
            "since": since,
            "until": until,
        },
        page,
    )
    return {"rows": rows, "total": total}


@router.get("/{alert_id}")
async def get_alert(alert_id: str, request: Request):
    """Returns full Alert including explainability + evidence flow ids."""
    return request.app.state.alert_repository.get(alert_id)


@router.post("/{alert_id}/ack")
async def ack_alert(
    alert_id: str,
    request: Request,
    user: AuthUser = Depends(require_role("analyst")),
):
    """Acknowledge an alert. Audit-logged."""
    alert = request.app.state.alert_repository.ack(alert_id, user.username)
    request.app.state.event_store.append(
        actor=user.username,
        action="alert.ack",
        target=alert_id,
        payload={"status": alert.status},
    )
    return alert


@router.post("/{alert_id}/close")
async def close_alert(
    alert_id: str,
    request: Request,
    disposition: Annotated[str, Body(embed=True)],
    user: AuthUser = Depends(require_role("supervisor")),
):
    """Close with disposition (true_positive | false_positive | benign)."""
    alert = request.app.state.alert_repository.close(alert_id, user.username, disposition)
    request.app.state.event_store.append(
        actor=user.username,
        action="alert.close",
        target=alert_id,
        payload={"status": alert.status, "disposition": disposition},
    )
    return alert

# router = APIRouter(prefix="/alerts", tags=["alerts"])


# @router.get("")
# async def list_alerts(severity=None, host=None, since=None, until=None, page=1):
#     """Paginated alert listing. Filters compose with AND semantics."""
#     ...


# @router.get("/{alert_id}")
# async def get_alert(alert_id: str):
#     """Returns full Alert including explainability + evidence flow ids."""
#     ...


# @router.post("/{alert_id}/ack")
# async def ack_alert(alert_id: str, user=Depends(require_role("analyst"))):
#     """Acknowledge an alert. Audit-logged."""
#     ...


# @router.post("/{alert_id}/close")
# async def close_alert(alert_id: str, disposition: str,
#                        user=Depends(require_role("supervisor"))):
#     """Close with disposition (true_positive | false_positive | benign)."""
#     ...
