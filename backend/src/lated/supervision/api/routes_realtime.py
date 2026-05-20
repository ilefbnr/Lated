# =============================================================================
# lated.supervision.api.routes_realtime — flow-by-flow realtime demo surface
# =============================================================================

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from lated.common.schemas import CanonicalFlow, Protocol
from lated.supervision.auth import get_current_user

router = APIRouter(prefix="/realtime", tags=["realtime"], dependencies=[Depends(get_current_user)])


@router.get("/graph")
async def realtime_graph_snapshot(request: Request):
    return request.app.state.realtime_graph.snapshot()


@router.post("/flow")
async def ingest_single_flow(request: Request, body: dict):
    protocol = str(body.get("protocol", "tcp")).lower()
    flow = CanonicalFlow(
        flow_id=str(body.get("flow_id") or f"live-{int(datetime.now(timezone.utc).timestamp())}"),
        ts=datetime.fromisoformat(str(body.get("ts")).replace("Z", "+00:00")) if body.get("ts") else datetime.now(timezone.utc),
        src_host=str(body["src_host"]),
        dst_host=str(body["dst_host"]),
        src_port=int(body.get("src_port", 0)),
        dst_port=int(body.get("dst_port", 0)),
        protocol=Protocol(protocol if protocol in {"tcp", "udp", "icmp", "other"} else "other"),
        duration=float(body.get("duration", 0.0)),
        packet_count=int(body.get("packet_count", 1)),
        byte_count=int(body.get("byte_count", 0)),
        source_sensor=str(body.get("source_sensor", "live")),
    )
    payload = request.app.state.realtime_graph.ingest(flow)
    return {"status": "ok", "graph": payload}
