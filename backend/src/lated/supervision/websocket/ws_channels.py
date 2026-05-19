# =============================================================================
# lated.supervision.websocket.ws_channels — channel routing
# =============================================================================
#
# PURPOSE
# -------
# Maintains the mapping channel -> set[Connection] and dispatches WSEvent
# objects published via event_publisher to all subscribed clients.
#
# INPUTS  : WSEvent objects from event_publisher
# OUTPUTS : JSON frames written to each subscribed websocket
#
# CYBERSECURITY REASONING
# -----------------------
# Per-channel ACLs apply: e.g. only `supervisor+` roles may subscribe to
# `flows` (which carries L4 metadata). Lower-privilege analysts can still
# receive `alerts` / `graph` / `health`.
# =============================================================================

from __future__ import annotations

from collections import defaultdict

from lated.common.schemas import WSEvent


class WSChannels:
    """Channel registry + fanout dispatcher.

    Methods
    -------
      subscribe(connection, channel)
      unsubscribe(connection, channel)
      publish(event: WSEvent) -> int   # returns count of clients written
    """

    def __init__(self):
        self._subscriptions: dict[str, set[object]] = defaultdict(set)

    def subscribe(self, connection, channel: str) -> None:
        self._subscriptions[channel].add(connection)

    def unsubscribe(self, connection, channel: str) -> None:
        self._subscriptions[channel].discard(connection)

    async def publish(self, event: WSEvent) -> int:
        delivered = 0
        for connection in list(self._subscriptions[event.channel]):
            await connection.send_json(event.model_dump(mode="json"))
            delivered += 1
        return delivered
