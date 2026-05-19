# =============================================================================
# lated.supervision.api.routes_flows — /flows endpoints
# =============================================================================
#
# PURPOSE
# -------
# Powers the SOC UI's "Suspicious Flows" table.
#
# ENDPOINTS
# ---------
#   GET /flows                   : paginated, searchable, sortable
#   GET /flows/{flow_id}         : full canonical flow with detection metadata
#   GET /flows/by-host/{host_id} : flows where host_id appears as src or dst
#
# CYBERSECURITY REASONING
# -----------------------
# Flows table is the lowest-level forensic surface — analysts drill INTO
# flows after triaging an alert. Endpoints MUST authenticate, since the
# data is sensitive (full L4 metadata).
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from lated.supervision.auth import get_current_user

router = APIRouter(prefix="/flows", tags=["flows"], dependencies=[Depends(get_current_user)])


@router.get("")
async def list_flows(
    request: Request,
    q: str | None = None,
    min_suspicion: float | None = Query(default=None, ge=0, le=1),
    since: str | None = None,
    until: str | None = None,
    sort: str = "ts",
    page: int = 1,
):
    """Paginated suspicious-flows listing. Filters compose with AND semantics."""
    rows, total = request.app.state.flows_repository.list(
        {
            "q": q,
            "min_suspicion": min_suspicion,
            "since": since,
            "until": until,
            "sort": sort,
        },
        page,
    )
    return {"rows": rows, "total": total}


@router.get("/by-host/{host_id}")
async def flows_by_host(
    host_id: str,
    request: Request,
    since: str | None = None,
    until: str | None = None,
):
    """Return flows where the host appears as src or dst."""
    return request.app.state.flows_repository.by_host(host_id, since=since, until=until)


@router.get("/{flow_id}")
async def get_flow(flow_id: str, request: Request):
    """Return a single flow with its detection metadata."""
    return request.app.state.flows_repository.get(flow_id)
