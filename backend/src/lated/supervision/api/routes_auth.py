# =============================================================================
# lated.supervision.api.routes_auth — /auth endpoints
# =============================================================================
#
# Exposes minimal identity surface so the SOC UI can render role-aware
# elements (button visibility, badges, route guards) without having to
# inspect bearer tokens itself.
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, Depends

from lated.supervision.auth import AuthUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def whoami(user: AuthUser = Depends(get_current_user)) -> dict:
    """Return the authenticated user's identity + role."""
    return {"username": user.username, "role": user.role}
