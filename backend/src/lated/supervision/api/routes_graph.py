# =============================================================================
# lated.supervision.api.routes_graph — /graph endpoints
# =============================================================================
#
# PURPOSE
# -------
# Exposes the temporal graph for the SOC UI's attack-graph visualization.
#
# ENDPOINTS
# ---------
#   GET /graph/baseline           : the baseline graph (static)
#   GET /graph/snapshot/latest    : the most recent TemporalSnapshot
#   GET /graph/snapshot/{ts}      : a specific historical snapshot
#   GET /graph/host/{host_id}     : ego-network around a single host
#
# CYBERSECURITY REASONING
# -----------------------
# Full snapshots can be very large (100k+ edges in enterprises). Endpoints
# implement server-side pruning (top-K most active edges) and shape the
# payload for Cytoscape consumption. Memory budget on the API tier is
# enforced (max payload size).
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from lated.supervision.auth import get_current_user

router = APIRouter(prefix="/graph", tags=["graph"], dependencies=[Depends(get_current_user)])


@router.get("/baseline")
async def get_baseline(request: Request):
    """Return the baseline graph payload shaped for Cytoscape."""
    return request.app.state.graph_repository.baseline()


@router.get("/snapshot/latest")
async def get_latest_snapshot(request: Request):
    """Return the most recent temporal snapshot."""
    return request.app.state.graph_repository.latest_snapshot()


@router.get("/snapshot/{ts}")
async def get_snapshot_at(ts: str, request: Request):
    """Return the snapshot at the given timestamp."""
    return request.app.state.graph_repository.snapshot_at(ts)


@router.get("/host/{host_id}")
async def get_host_ego(host_id: str, request: Request, hops: int = 1):
    """Return the k-hop ego-network around a host."""
    return request.app.state.graph_repository.host_ego(host_id, hops=hops)
