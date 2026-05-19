# =============================================================================
# lated.detection.recon.sliding_window — windowing primitive
# =============================================================================
#
# MVP: tumbling windows aligned to UTC epoch (same math as graph.snapshot
# manager) — a sliding hop equal to the window size is equivalent to tumbling,
# which is enough to surface the recon signatures we score. A sub-second hop
# can be added later behind the same API.
#
# Determinism:
#   - window boundaries are computed from flow.ts via integer epoch math,
#   - aggregations are order-independent (sums, set sizes).
# =============================================================================

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone


def _floor_window(ts: datetime, size_seconds: int) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    epoch = int(ts.timestamp())
    start_epoch = (epoch // size_seconds) * size_seconds
    return datetime.fromtimestamp(start_epoch, tz=timezone.utc)


class SlidingWindow:
    """Per-host flow buffer keyed by UTC-aligned window starts."""

    def __init__(self, size_seconds: int, step_seconds: int | None = None):
        if size_seconds <= 0:
            raise ValueError("size_seconds must be > 0")
        self.size_seconds = int(size_seconds)
        self.step_seconds = int(step_seconds or size_seconds)
        self._current_start: datetime | None = None
        self._pending: dict[str, list] = defaultdict(list)
        self._completed: dict[str, list] | None = None
        self._completed_start: datetime | None = None

    @property
    def window_seconds(self) -> int:
        return self.size_seconds

    def add(self, flow) -> None:
        win_start = _floor_window(flow.ts, self.size_seconds)
        if self._current_start is None:
            self._current_start = win_start
        if win_start > self._current_start:
            # Promote pending -> completed before opening the next window.
            self._completed = self._pending
            self._completed_start = self._current_start
            self._pending = defaultdict(list)
            self._current_start = win_start
        elif win_start < self._current_start:
            # Late flow — drop. Recon must remain deterministic.
            return
        self._pending[flow.src_host].append(flow)

    def tick(self) -> bool:
        """True when a window has just closed and is awaiting consumption."""
        return self._completed is not None

    def consume(self) -> None:
        self._completed = None
        self._completed_start = None

    def flush(self) -> bool:
        """Mark the in-progress window as completed (end-of-stream)."""
        if self._completed is not None:
            return True
        if not self._pending:
            return False
        self._completed = self._pending
        self._completed_start = self._current_start
        self._pending = defaultdict(list)
        return True

    def window_start(self) -> datetime | None:
        return self._completed_start

    def window_end(self) -> datetime | None:
        if self._completed_start is None:
            return None
        return self._completed_start + timedelta(seconds=self.size_seconds)

    def subjects(self) -> list[str]:
        if self._completed is None:
            return []
        return sorted(self._completed.keys())

    def flows_for(self, host: str) -> list:
        if self._completed is None:
            return []
        return list(self._completed.get(host, []))

    def unique_dst(self, host: str) -> set[str]:
        return {flow.dst_host for flow in self.flows_for(host)}

    def unique_dst_ports(self, host: str) -> set[int]:
        return {flow.dst_port for flow in self.flows_for(host)}

    def total_packets(self, host: str) -> int:
        return sum(flow.packet_count for flow in self.flows_for(host))
