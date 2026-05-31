# =============================================================================
# lated.supervision.api.routes_baseline — rare-edge baseline learn/freeze control
# =============================================================================
#
# PURPOSE
# -------
# Operator control over the rare-edge baseline lifecycle from the SOC UI:
#
#   GET  /baseline/status   : current mode + edge count
#   POST /baseline/mode     : switch learning <-> frozen (freeze persists to disk)
#   POST /baseline/reset    : clear the baseline to relearn an environment
#
# WORKFLOW
# --------
# 1. Learning  : the detector records observed edges as "normal" and stays
#                silent (no alerts) — used to fingerprint a network.
# 2. Frozen    : the baseline stops growing; any edge absent from it is flagged
#                on every occurrence, so a replayed attack keeps firing.
#
# CYBERSECURITY REASONING
# -----------------------
# Freezing before an investigation is what prevents an attacker's lateral
# edges from being silently absorbed into the "normal" baseline. The action is
# audit-logged and gated to supervisor+.
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lated.supervision.auth import AuthUser, get_current_user, require_role

router = APIRouter(prefix="/baseline", tags=["baseline"])


class ModeBody(BaseModel):
    mode: str  # "learning" | "frozen"


def _detector(request: Request):
    components = getattr(request.app.state, "detection_components", None)
    detector = getattr(components, "rare_edge_detector", None) if components else None
    if detector is None:
        raise HTTPException(
            status_code=503,
            detail="Rare-edge baseline unavailable (detection pipeline not wired).",
        )
    return detector


@router.get("/status", dependencies=[Depends(get_current_user)])
async def baseline_status(request: Request) -> dict:
    """Current baseline mode + edge count for the UI control."""
    return _detector(request).status()


@router.post("/mode")
async def baseline_mode(
    body: ModeBody,
    request: Request,
    user: AuthUser = Depends(require_role("supervisor")),
) -> dict:
    """Switch the baseline between learning and frozen. Freezing persists the
    current baseline to disk so the reference is durable."""
    mode = body.mode.strip().lower()
    if mode not in {"learning", "frozen"}:
        raise HTTPException(status_code=400, detail="mode must be 'learning' or 'frozen'")

    detector = _detector(request)
    detector.set_learning(mode == "learning")

    saved: str | None = None
    if mode == "frozen":
        try:
            target = detector.save()
            saved = str(target) if target else None
        except Exception as exc:  # pragma: no cover - disk failure
            raise HTTPException(status_code=500, detail=f"freeze save failed: {exc}")

    try:
        request.app.state.event_store.append(
            actor=user.username,
            action="baseline.mode",
            target="rare_edge",
            payload={"mode": mode, "saved": saved},
        )
    except Exception:
        pass

    return {**detector.status(), "saved": saved}


@router.post("/reset")
async def baseline_reset(
    request: Request,
    user: AuthUser = Depends(require_role("supervisor")),
) -> dict:
    """Drop every baseline edge so the detector can relearn from scratch."""
    detector = _detector(request)
    detector.reset()
    try:
        request.app.state.event_store.append(
            actor=user.username,
            action="baseline.reset",
            target="rare_edge",
            payload={},
        )
    except Exception:
        pass
    return detector.status()
