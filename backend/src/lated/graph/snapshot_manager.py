# =============================================================================
# lated.graph.snapshot_manager — non-overlapping window state machine
# =============================================================================
#
# Windows are aligned to UTC epoch boundaries:
#     window_start = floor(ts_epoch / window_seconds) * window_seconds
#     window_end   = window_start + window_seconds
# The interval is half-open [start, end), so every flow belongs to exactly
# one window — no overlap, no gap.
#
# The MVP is driven by flow timestamps (replay-first). A wall-clock variant
# can wrap this later for live mode; the math is identical.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lated.common.exceptions import SnapshotError


class SnapshotManager:
    """Computes UTC-aligned, non-overlapping window boundaries."""

    def __init__(self, window_seconds: int, tolerance_seconds: int = 5):
        if window_seconds <= 0:
            raise SnapshotError("window_seconds must be > 0")
        self.window_seconds = int(window_seconds)
        self.tolerance = timedelta(seconds=int(tolerance_seconds))

    def window_for(self, ts: datetime) -> tuple[datetime, datetime]:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        epoch = int(ts.timestamp())
        start_epoch = (epoch // self.window_seconds) * self.window_seconds
        start = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
        end = start + timedelta(seconds=self.window_seconds)
        return start, end

    def is_window_complete(self, current_start: datetime, watermark_ts: datetime) -> bool:
        """True when the watermark has passed the end of `current_start`'s window."""
        _, end = self.window_for(current_start)
        if watermark_ts.tzinfo is None:
            watermark_ts = watermark_ts.replace(tzinfo=timezone.utc)
        return watermark_ts >= end

    def is_late(self, current_start: datetime, candidate_ts: datetime) -> bool:
        """True when candidate_ts falls before current_start (out-of-order beyond tolerance)."""
        if candidate_ts.tzinfo is None:
            candidate_ts = candidate_ts.replace(tzinfo=timezone.utc)
        return candidate_ts + self.tolerance < current_start

    @staticmethod
    def snapshot_id(window_start: datetime) -> str:
        # Use a Z-suffixed compact ISO so the id is filename-safe and stable.
        return "snap-" + window_start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
