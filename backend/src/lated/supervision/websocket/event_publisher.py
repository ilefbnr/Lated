# =============================================================================
# lated.supervision.websocket.event_publisher — internal pub/sub
# =============================================================================
#
# Two surfaces share the same in-process registry:
#   - async `publish` / `subscribe` — used by the live FastAPI + WS path,
#   - sync  `publish_sync`          — used by the replay orchestrator, which
#                                     does not run inside an event loop.
#
# A small ring buffer keeps the last N events so tests (and the admin UI)
# can introspect what was published during replay without subscribing.
# =============================================================================

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator

from lated.common.schemas import WSEvent


DEFAULT_HISTORY_SIZE = 1024


class EventPublisher:
    """In-process WSEvent publisher with sync + async fanout surfaces."""

    def __init__(self, redis_url: str | None = None, history_size: int = DEFAULT_HISTORY_SIZE):
        self.redis_url = redis_url
        self._queues: dict[str, list[asyncio.Queue[WSEvent]]] = defaultdict(list)
        self._history: deque[WSEvent] = deque(maxlen=int(history_size))

    async def publish(self, event: WSEvent) -> None:
        self._history.append(event)
        for queue in list(self._queues[event.channel]):
            await queue.put(event)

    def publish_sync(self, event: WSEvent) -> None:
        """Synchronous publish — usable from replay/non-async callers."""
        self._history.append(event)
        for queue in list(self._queues[event.channel]):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Async subscriber is back-pressured; ring buffer still records it.
                continue

    async def subscribe(self, channel: str) -> AsyncIterator[WSEvent]:
        queue: asyncio.Queue[WSEvent] = asyncio.Queue()
        self._queues[channel].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._queues[channel].remove(queue)

    def history(self, channel: str | None = None) -> list[WSEvent]:
        if channel is None:
            return list(self._history)
        return [event for event in self._history if event.channel == channel]

    def reset_history(self) -> None:
        self._history.clear()
