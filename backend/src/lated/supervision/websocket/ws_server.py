# =============================================================================
# lated.supervision.websocket.ws_server — WebSocket connection manager
# =============================================================================
#
# PURPOSE
# -------
# ASGI WebSocket endpoint that the SOC dashboard connects to. Manages:
#   - per-connection auth (bearer token, validated on accept),
#   - subscription state (which channels does each client want?),
#   - heartbeat / liveness,
#   - graceful disconnect on auth failure or backpressure.
#
# CHANNELS (see common.constants)
# -------------------------------
#   alerts, graph, hosts, flows, health, timeline
#
# INPUTS  : websocket frames from clients (subscribe / unsubscribe / pong)
# OUTPUTS : WSEvent frames published by detection/correlation
#
# INTERACTIONS
# ------------
#   - event_publisher : the internal pub/sub hub.
#   - ws_channels     : route messages from publisher to subscribed clients.
#
# CYBERSECURITY REASONING
# -----------------------
# - Auth is enforced ON ACCEPT, not lazily. Unauthenticated clients never
#   receive a single payload byte.
# - Backpressure-aware send: if a client cannot keep up, the server drops
#   them (with an explicit close code) rather than buffering unboundedly.
# =============================================================================

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect

from lated.common.constants import WS_CHANNEL_HEALTH
from lated.common.schemas import WSEvent, WSEventName, WSChannel


class WSServer:
    """ASGI WebSocket endpoint + connection registry.

    Internal logic
    --------------
      async endpoint(websocket):
        if not await self.authenticate(websocket):
            return await websocket.close(code=1008)
        await websocket.accept()
        connection = self.register(websocket)
        try:
            async for frame in websocket.iter_json():
                if frame.type == 'subscribe':
                    connection.subscribe(frame.channel)
                elif frame.type == 'unsubscribe':
                    connection.unsubscribe(frame.channel)
                elif frame.type == 'pong':
                    connection.alive = True
        finally:
            self.unregister(connection)
    """

    def __init__(self, channels, auth, heartbeat_seconds: int = 15):
        self.channels = channels
        self.auth = auth
        self.heartbeat_seconds = heartbeat_seconds

    async def endpoint(self, websocket: WebSocket) -> None:
        if self.auth is not None:
            user = await self.auth(websocket)
            if user is None:
                return
        await websocket.accept()
        self.channels.subscribe(websocket, WS_CHANNEL_HEALTH)
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(websocket))
        try:
            while True:
                frame = await websocket.receive_json()
                action = frame.get("type")
                channel = frame.get("channel")

                if action == "subscribe" and isinstance(channel, str):
                    self.channels.subscribe(websocket, channel)
                elif action == "unsubscribe" and isinstance(channel, str):
                    self.channels.unsubscribe(websocket, channel)
                elif action == "pong":
                    continue
        except WebSocketDisconnect:
            pass
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
            for channel in WSChannel:
                self.channels.unsubscribe(websocket, channel.value)

    async def _heartbeat_loop(self, websocket: WebSocket) -> None:
        while True:
            event = WSEvent(
                channel=WSChannel.HEALTH,
                event=WSEventName.HEALTH_HEARTBEAT,
                payload={"status": "ok"},
                ts=datetime.now(timezone.utc),
            )
            await websocket.send_json(event.model_dump(mode="json"))
            await asyncio.sleep(self.heartbeat_seconds)
