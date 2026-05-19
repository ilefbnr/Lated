# =============================================================================
# lated.supervision.api.routes_attack_paths — /paths endpoints
# =============================================================================
#
# PURPOSE
# -------
# Exposes reconstructed AttackPath objects to the UI.
#
# ENDPOINTS
# ---------
#   GET /paths                   : paginated list, filterable by time/host
#   GET /paths/{path_id}         : full path with timeline + pivots + propagation
#   GET /paths/{path_id}/timeline: structured step-by-step narrative
#   GET /paths/{path_id}/graph   : Cytoscape-shaped subgraph for visualization
#
# CYBERSECURITY REASONING
# -----------------------
# AttackPath responses include `path_confidence`. Filtering on confidence is
# the analyst's primary triage lever — surface it as a query param.
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from lated.supervision.auth import get_current_user

router = APIRouter(prefix="/paths", tags=["paths"], dependencies=[Depends(get_current_user)])


@router.get("")
async def list_paths(
    request: Request,
    min_confidence: float = Query(default=0.0, ge=0, le=1),
    since: str | None = None,
    until: str | None = None,
    page: int = 1,
):
    """Paginated attack-path listing."""
    rows, total = request.app.state.paths_repository.list(
        {
            "min_confidence": min_confidence,
            "since": since,
            "until": until,
        },
        page,
    )
    return {"rows": rows, "total": total}


@router.get("/{path_id}")
async def get_path(path_id: str, request: Request):
    """Return the full attack path with embedded alert timeline."""
    return request.app.state.paths_repository.get(path_id)


@router.get("/{path_id}/timeline")
async def get_path_timeline(path_id: str, request: Request):
    """Chronological alert timeline for the Recon -> LM narrative view."""
    return request.app.state.paths_repository.timeline(path_id)


@router.get("/{path_id}/graph")
async def get_path_graph(path_id: str, request: Request):
    """Cytoscape-shaped subgraph restricted to the hosts on this path."""
    return request.app.state.paths_repository.graph(path_id)
