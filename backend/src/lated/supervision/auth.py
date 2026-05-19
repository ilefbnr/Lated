from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, WebSocket


ROLE_ORDER = {"analyst": 1, "supervisor": 2, "admin": 3}


@dataclass(frozen=True)
class AuthUser:
    username: str
    role: str


TOKENS = {
    "analyst-token": AuthUser(username="analyst.local", role="analyst"),
    "supervisor-token": AuthUser(username="supervisor.local", role="supervisor"),
    "admin-token": AuthUser(username="admin.local", role="admin"),
}


def _parse_bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return token


def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    token = _parse_bearer_token(authorization)
    user = TOKENS.get(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


def require_role(min_role: str):
    def dependency(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if ROLE_ORDER[user.role] < ROLE_ORDER[min_role]:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return dependency


async def authenticate_websocket(websocket: WebSocket, required: bool = True) -> AuthUser | None:
    authorization = websocket.headers.get("authorization")
    token: str | None = None
    if authorization is not None:
        try:
            token = _parse_bearer_token(authorization)
        except HTTPException as exc:
            await websocket.close(code=1008, reason=str(exc.detail))
            return None
    else:
        # Browsers cannot set custom headers on the WebSocket handshake. Allow
        # the bearer token via ?token=... as a dev-friendly fallback.
        query_token = websocket.query_params.get("token")
        if isinstance(query_token, str) and query_token:
            token = query_token

    if token is None:
        if not required:
            return None
        await websocket.close(code=1008, reason="Missing Authorization header")
        return None

    user = TOKENS.get(token)
    if user is None:
        await websocket.close(code=1008, reason="Unauthorized")
        return None
    return user
