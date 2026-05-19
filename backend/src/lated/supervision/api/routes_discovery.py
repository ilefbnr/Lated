# =============================================================================
# lated.supervision.api.routes_discovery — passive discovery bootstrap endpoints
# =============================================================================

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from lated.discovery.discovery_service import DiscoveryService
from lated.supervision.auth import AuthUser, get_current_user

router = APIRouter(prefix="/discovery", tags=["discovery"], dependencies=[Depends(get_current_user)])


def _resolve_passive_source(config, backend_root: Path) -> Path:
    if str(config.ingestion.source) == "zeek":
        candidate = Path(config.ingestion.zeek_log_dir)
        fallback = backend_root / "data" / "demo_zeek"
    elif str(config.ingestion.source) == "pcap":
        candidate = Path(config.ingestion.pcap_path)
        fallback = backend_root / "data" / "demo.pcap"
    else:
        raise HTTPException(status_code=400, detail="Passive discovery bootstrap supports zeek or pcap ingestion sources only")

    resolved = candidate if candidate.is_absolute() else backend_root / candidate
    if resolved.exists():
        return resolved
    if str(config.env) == "development" and fallback.exists():
        return fallback
    return resolved


@router.post("/bootstrap")
async def bootstrap_discovery(request: Request, user: AuthUser = Depends(get_current_user)):
    del user
    config = request.app.state.config
    backend_root: Path = request.app.state.backend_root
    source_path = _resolve_passive_source(config, backend_root)

    if not source_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Passive discovery source not found: {source_path}",
        )

    service = DiscoveryService(
        config.discovery,
        source_path=source_path,
        baseline_path=request.app.state.baseline_path,
        registry_path=request.app.state.registry_path,
        env=str(config.env),
    )
    baseline = service.run()
    request.app.state.graph_repository.baseline_path = request.app.state.baseline_path

    return {
        "status": "ok",
        "source_path": str(source_path),
        "baseline_path": str(request.app.state.baseline_path),
        "registry_path": str(request.app.state.registry_path),
        "generated_at": baseline.created_at,
        "host_count": len(baseline.nodes),
        "edge_count": len(baseline.edges),
        "subnet_count": len(baseline.subnets),
        "gateway_count": len(baseline.gateways),
        "service_count": len(baseline.services),
    }
