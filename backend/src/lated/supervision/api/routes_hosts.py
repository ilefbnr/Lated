# =============================================================================
# lated.supervision.api.routes_hosts — /hosts endpoints
# =============================================================================
#
# PURPOSE
# -------
# Read-only REST view onto the HostRegistry + RiskScorer for the SOC UI.
#
# ENDPOINTS
# ---------
#   GET /hosts                    : paginated host listing
#   GET /hosts/top-risky          : top-N hosts by current risk (decayed)
#   GET /hosts/{host_id}          : profile + recent alerts + risk evolution
#   GET /hosts/{host_id}/heatmap  : per-neighbor communication intensity matrix
#
# CYBERSECURITY REASONING
# -----------------------
# `top-risky` is the analyst's entry point each shift. Performance matters
# here — implementations should cache aggressively (5s TTL is acceptable).
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from lated.supervision.auth import get_current_user

router = APIRouter(prefix="/hosts", tags=["hosts"], dependencies=[Depends(get_current_user)])


@router.get("")
async def list_hosts(request: Request, subnet: str | None = None):
    """List all hosts known to the registry."""
    return request.app.state.hosts_repository.list(subnet=subnet)


@router.get("/top-risky")
async def top_risky(request: Request, limit: int = 25):
    """Top-N risky hosts. Feeds the dashboard's host-risk panel."""
    return request.app.state.hosts_repository.top_risky(limit=limit)


@router.get("/{host_id}")
async def host_profile(host_id: str, request: Request):
    """Full host profile."""
    return request.app.state.hosts_repository.get(host_id)


@router.get("/{host_id}/risk-evolution")
async def host_risk_evolution(host_id: str, request: Request, hours: int = 24):
    """Risk evolution used by the host profile sparkline."""
    return request.app.state.hosts_repository.risk_evolution(host_id, hours=hours)


@router.get("/{host_id}/heatmap")
async def host_heatmap(host_id: str, request: Request, window_minutes: int = 60):
    """Per-neighbor communication intensity matrix for the heatmap viz."""
    return request.app.state.hosts_repository.heatmap(host_id, window_minutes=window_minutes)

# router = APIRouter(prefix="/hosts", tags=["hosts"])


# @router.get("")
# async def list_hosts(subnet=None, page=1):
#     """List all hosts known to the registry."""
#     ...


# @router.get("/top-risky")
# async def top_risky(limit: int = 25):
#     """Top-N risky hosts. Cached 5s. Feeds the dashboard's host-risk panel."""
#     ...


# @router.get("/{host_id}")
# async def host_profile(host_id: str):
#     """Full host profile + recent alerts + 24h risk evolution."""
#     ...


# @router.get("/{host_id}/heatmap")
# async def host_heatmap(host_id: str, window_minutes: int = 60):
#     """Per-neighbor communication intensity matrix for the heatmap viz."""
#     ...
