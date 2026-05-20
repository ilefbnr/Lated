from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
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

JWT_SECRET = os.environ.get("LATED_AUTH_JWT_SECRET", "")


def _b64url_decode(value: str) -> bytes:
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _jwt_user(token: str) -> AuthUser | None:
    if not JWT_SECRET:
        return None
    parts = token.split('.')
    if len(parts) != 3:
        return None
    signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
    expected_sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(parts[2])
    if not hmac.compare_digest(expected_sig, actual_sig):
        return None
    try:
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except Exception:
        return None
    username = payload.get("sub") or payload.get("username")
    role = payload.get("role")
    if not isinstance(username, str) or not isinstance(role, str):
        return None
    if role not in ROLE_ORDER:
        return None
    return AuthUser(username=username, role=role)


def _resolve_user(token: str) -> AuthUser | None:
    user = TOKENS.get(token)
    if user is not None:
        return user
    return _jwt_user(token)


def _parse_bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return token


def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    token = _parse_bearer_token(authorization)
    user = _resolve_user(token)
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

    user = _resolve_user(token)
    if user is None:
        await websocket.close(code=1008, reason="Unauthorized")
        return None
    return user
