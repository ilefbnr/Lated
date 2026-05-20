# =============================================================================
# lated.supervision.api.routes_discovery — passive discovery bootstrap endpoints
# =============================================================================

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from lated.discovery.discovery_service import DiscoveryService
from lated.supervision.auth import AuthUser, get_current_user

router = APIRouter(prefix="/discovery", tags=["discovery"], dependencies=[Depends(get_current_user)])


def _sync_workflow_paths(request: Request) -> None:
    workflow = request.app.state.discovery_workflow
    workflow.backend_root = request.app.state.backend_root
    workflow.baseline_path = request.app.state.baseline_path
    workflow.registry_path = request.app.state.registry_path


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
    _sync_workflow_paths(request)
    config = request.app.state.config
    backend_root: Path = request.app.state.backend_root
    source_path = _resolve_passive_source(config, backend_root)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Passive discovery source not found: {source_path}")
    record = request.app.state.discovery_workflow.run_job(
        config=config,
        source_kind=str(config.ingestion.source),
        source_value=str(source_path),
        actor=user.username,
    )
    request.app.state.graph_repository.baseline_path = request.app.state.baseline_path
    return {"status": "ok", **record}


@router.get("/history")
async def discovery_history(request: Request):
    _sync_workflow_paths(request)
    return request.app.state.discovery_workflow.list_history()


@router.get("/status")
async def discovery_status(request: Request):
    _sync_workflow_paths(request)
    latest = request.app.state.discovery_workflow.latest()
    return {"latest": latest}


@router.post("/run")
async def run_discovery(
    request: Request,
    body: dict,
    user: AuthUser = Depends(get_current_user),
):
    _sync_workflow_paths(request)
    source_kind = str(body.get("source_kind") or request.app.state.config.ingestion.source)
    source_value = str(body.get("source_value") or "")
    if not source_value:
        raise HTTPException(status_code=400, detail="source_value is required")
    record = request.app.state.discovery_workflow.run_job(
        config=request.app.state.config,
        source_kind=source_kind,
        source_value=source_value,
        actor=user.username,
        mode=str(body.get("mode") or "passive"),
    )
    request.app.state.graph_repository.baseline_path = request.app.state.baseline_path
    return {"status": "ok", **record}


@router.post("/upload")
async def upload_discovery_source(request: Request, file: UploadFile):
    _sync_workflow_paths(request)
    payload = await file.read()
    result = request.app.state.discovery_workflow.upload(file.filename or "upload.bin", payload)
    return {"status": "ok", **result}
