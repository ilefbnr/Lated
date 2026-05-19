# =============================================================================
# lated.correlation.attack_path_builder — path assembly from SuspicionScore
# =============================================================================
#
# Rules (intentionally explicit — no opaque correlation magic):
#   1. Temporal continuity: an event extends a path only if
#         (event.window_start - path.last_ts) <= temporal_continuity_seconds.
#   2. Host continuity: the new host is either already on the path (refresh)
#      or graph-adjacent to the path's tip host.
#   3. Length bound: path length stays <= max_path_length.
#   4. An event matching no candidate seeds a fresh path candidate.
#
# Output is an in-progress `PathCandidate` list. The engine decides when to
# emit final AttackPath objects.
# =============================================================================

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from lated.common.schemas import SuspicionScore


def _normalize(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _stable_path_id(first_host: str, first_ts: datetime) -> str:
    key = f"{first_host}|{_normalize(first_ts).isoformat()}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"path-{digest}"


@dataclass
class PathCandidate:
    """In-progress attack path under assembly."""

    path_id: str
    steps: list[SuspicionScore] = field(default_factory=list)
    hosts: list[str] = field(default_factory=list)

    @property
    def tip_host(self) -> str:
        return self.hosts[-1] if self.hosts else ""

    @property
    def last_ts(self) -> datetime:
        return _normalize(self.steps[-1].window_start)

    @property
    def first_ts(self) -> datetime:
        return _normalize(self.steps[0].window_start)

    @property
    def confidence(self) -> float:
        if not self.steps:
            return 0.0
        return sum(s.score for s in self.steps) / float(len(self.steps))


class AttackPathBuilder:
    """Assembles PathCandidates from SuspicionScore events."""

    def __init__(self, temporal_continuity_seconds: int, max_path_length: int):
        if temporal_continuity_seconds <= 0:
            raise ValueError("temporal_continuity_seconds must be > 0")
        if max_path_length <= 0:
            raise ValueError("max_path_length must be > 0")
        self.continuity = timedelta(seconds=int(temporal_continuity_seconds))
        self.max_path_length = int(max_path_length)

    def extend(
        self,
        event: SuspicionScore,
        in_progress: list[PathCandidate],
        adjacency,
    ) -> list[PathCandidate]:
        when = _normalize(event.window_start)
        host = event.subject_host
        matched = False

        for candidate in in_progress:
            if when - candidate.last_ts > self.continuity:
                continue
            if host in candidate.hosts:
                # refresh — event on an already-known host of this path
                if when >= candidate.last_ts:
                    candidate.steps.append(event)
                matched = True
                continue
            if len(candidate.hosts) >= self.max_path_length:
                continue
            if not adjacency.are_adjacent(candidate.tip_host, host, when):
                continue
            candidate.steps.append(event)
            candidate.hosts.append(host)
            matched = True

        if not matched:
            in_progress.append(
                PathCandidate(
                    path_id=_stable_path_id(host, when),
                    steps=[event],
                    hosts=[host],
                )
            )
        return in_progress

    def evict_stale(
        self,
        in_progress: list[PathCandidate],
        watermark: datetime,
    ) -> tuple[list[PathCandidate], list[PathCandidate]]:
        """Return (still_open, closed) by checking the temporal gap to watermark."""
        watermark = _normalize(watermark)
        open_paths: list[PathCandidate] = []
        closed_paths: list[PathCandidate] = []
        for candidate in in_progress:
            if watermark - candidate.last_ts > self.continuity:
                closed_paths.append(candidate)
            else:
                open_paths.append(candidate)
        return open_paths, closed_paths
