# =============================================================================
# lated.detection.protocols.rare_edge_detector — first-seen relationship detector
# =============================================================================
#
# The detector maintains a *living* baseline of host-to-host edges. The
# baseline is loaded once from disk at startup (typically built during the
# bootstrap phase). At runtime every observed edge updates its metadata
# in place:
#
#   - first time seen           → emit a `rare_edge` score AND record it.
#   - already known             → increment `count`, refresh `last_seen`.
#
# The in-memory state can be persisted back to the same JSON via `save()`,
# so the baseline grows as the system observes more "normal" traffic.
# =============================================================================

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from lated.common.schemas import CanonicalFlow, DetectorName, DetectionKind, ReconScore
from lated.detection.recon.sliding_window import SlidingWindow


@dataclass(frozen=True)
class RareEdgeThresholds:
    min_score_emission: float = 0.3
    cross_subnet_bonus: float = 0.1
    privileged_port_bonus: float = 0.1


@dataclass
class EdgeStats:
    """Living metadata for a (src, dst) baseline entry."""
    count: int = 0
    first_seen: str | None = None  # ISO 8601
    last_seen: str | None = None
    src_ports: set[int] = field(default_factory=set)
    dst_ports: set[int] = field(default_factory=set)
    protocols: set[str] = field(default_factory=set)


class RareEdgeDetector:
    """Flags host-to-host relationships absent from the known baseline.

    The baseline is a mutable, persistent memory: edges accumulate stats as
    new flows are observed. Call `save(path)` periodically to durable-store
    the evolving state.
    """

    def __init__(
        self,
        window_seconds: int = 60,
        baseline_edges: dict[tuple[str, str], EdgeStats] | set[tuple[str, str]] | None = None,
        thresholds: RareEdgeThresholds | None = None,
        baseline_path: str | Path | None = None,
        original_payload: dict | None = None,
    ):
        self.window = SlidingWindow(size_seconds=window_seconds)
        self.thresholds = thresholds or RareEdgeThresholds()
        self.baseline_path: Path | None = Path(baseline_path) if baseline_path else None
        # Keep the loaded JSON minus its `edges` so we don't lose `nodes`,
        # `subnets`, `created_at`, … when we rewrite the file.
        self._original_payload: dict = dict(original_payload or {})
        self._original_payload.pop("edges", None)

        self._edges: dict[tuple[str, str], EdgeStats] = {}
        if isinstance(baseline_edges, dict):
            self._edges.update(baseline_edges)
        elif baseline_edges is not None:
            # Backward compat: a plain set of tuples becomes empty-stats edges.
            for pair in baseline_edges:
                self._edges[pair] = EdgeStats(count=0)
        self._dirty: bool = False

    # ----------------------------------------------------------------- API

    @classmethod
    def from_baseline_path(
        cls,
        baseline_path: str | Path | None,
        window_seconds: int = 60,
        thresholds: RareEdgeThresholds | None = None,
    ) -> "RareEdgeDetector":
        edges: dict[tuple[str, str], EdgeStats] = {}
        payload: dict = {}
        if baseline_path is not None:
            path = Path(baseline_path)
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    payload = {}
                for edge in payload.get("edges", []):
                    src = edge.get("src")
                    dst = edge.get("dst")
                    if not (isinstance(src, str) and isinstance(dst, str)):
                        continue
                    stats = EdgeStats(
                        count=int(edge.get("communication_count", 0) or 0),
                        first_seen=edge.get("first_seen"),
                        last_seen=edge.get("last_seen"),
                        src_ports=set(int(p) for p in edge.get("src_ports", []) if isinstance(p, (int, str)) and str(p).isdigit()),
                        dst_ports=set(int(p) for p in edge.get("dst_ports", []) if isinstance(p, (int, str)) and str(p).isdigit()),
                        protocols=set(str(p) for p in edge.get("protocols", [])),
                    )
                    edges[(src, dst)] = stats
        return cls(
            window_seconds=window_seconds,
            baseline_edges=edges,
            thresholds=thresholds,
            baseline_path=baseline_path,
            original_payload=payload,
        )

    def score(self, flow_stream: Iterable[CanonicalFlow]) -> Iterator[ReconScore]:
        for flow in flow_stream:
            self.window.add(flow)
            if self.window.tick():
                yield from self._emit_completed_window()
                self.window.consume()
        if self.window.flush():
            yield from self._emit_completed_window()
            self.window.consume()

    def run(self, flow_stream: Iterable[CanonicalFlow]) -> list[ReconScore]:
        return list(self.score(flow_stream))

    def save(self, path: str | Path | None = None) -> Path | None:
        """Persist the current baseline state back to disk (atomic write)."""
        target = Path(path) if path is not None else self.baseline_path
        if target is None:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        edges_serialized = [
            {
                "src": src,
                "dst": dst,
                "communication_count": stats.count,
                "first_seen": stats.first_seen,
                "last_seen": stats.last_seen,
                "src_ports": sorted(stats.src_ports),
                "dst_ports": sorted(stats.dst_ports),
                "protocols": sorted(stats.protocols),
            }
            for (src, dst), stats in sorted(self._edges.items())
        ]
        payload = dict(self._original_payload)
        payload["edges"] = edges_serialized
        payload["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Atomic write: dump to a temp file in the same directory then rename.
        fd, tmp_path = tempfile.mkstemp(
            prefix=target.name + ".", suffix=".tmp", dir=str(target.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, target)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        self._dirty = False
        return target

    def is_dirty(self) -> bool:
        """True when there are unpersisted updates since the last save()."""
        return self._dirty

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    # ------------------------------------------------------------- internals

    def _record_edge(self, flow: CanonicalFlow, ts_iso: str) -> bool:
        """Update stats for this flow's edge. Returns True iff edge was novel."""
        key = (flow.src_host, flow.dst_host)
        stats = self._edges.get(key)
        is_novel = stats is None
        if stats is None:
            stats = EdgeStats(count=0, first_seen=ts_iso, last_seen=ts_iso)
            self._edges[key] = stats
        stats.count += 1
        stats.last_seen = ts_iso
        if flow.src_port:
            stats.src_ports.add(int(flow.src_port))
        if flow.dst_port:
            stats.dst_ports.add(int(flow.dst_port))
        proto = getattr(flow.protocol, "value", None) or str(flow.protocol)
        if proto:
            stats.protocols.add(str(proto))
        self._dirty = True
        return is_novel

    def _emit_completed_window(self) -> Iterator[ReconScore]:
        start = self.window.window_start()
        if start is None:
            return
        start_iso = start.isoformat() if isinstance(start, datetime) else str(start)
        for subject in self.window.subjects():
            subject_flows = self.window.flows_for(subject)
            novel: list[CanonicalFlow] = []
            for flow in subject_flows:
                # Record + check novelty in one pass — the stats are updated
                # regardless of whether the edge was new (so the baseline
                # keeps evolving even when nothing fires).
                if self._record_edge(flow, start_iso):
                    novel.append(flow)

            if not novel:
                continue

            targets = sorted({flow.dst_host for flow in novel})
            score = min(1.0, 0.35 + 0.15 * max(0, len(targets) - 1))
            cross_subnet = any(self._subnet(flow.src_host) != self._subnet(flow.dst_host) for flow in novel)
            if cross_subnet:
                score += self.thresholds.cross_subnet_bonus
            privileged_ports = {53, 88, 135, 389, 445, 636, 3389, 5985, 5986}
            touched_privileged = any(flow.dst_port in privileged_ports for flow in novel)
            if touched_privileged:
                score += self.thresholds.privileged_port_bonus
            score = min(1.0, max(0.0, score))

            if score < self.thresholds.min_score_emission:
                continue

            signals = ["first_seen_edge"]
            if cross_subnet:
                signals.append("cross_subnet_first_seen")
            if touched_privileged:
                signals.append("privileged_service_first_seen")

            yield ReconScore(
                detector=DetectorName.RARE_EDGE,
                kind=DetectionKind.LM,
                window_start=start,
                subject_host=subject,
                score=score,
                unique_destinations=len(targets),
                unique_dst_ports=len({flow.dst_port for flow in novel}),
                burst_rate=0.0,
                target_hosts=targets,
                protocol=(novel[0].protocol if novel else None),
                triggered_signals=signals,
                evidence=[f"{flow.src_host}->{flow.dst_host}:{flow.dst_port}" for flow in novel[:8]],
                confidence=score,
                critical_asset_touched=touched_privileged,
                new_relation=True,
            )

    @staticmethod
    def _subnet(host_id: str) -> str:
        return host_id.split("-")[0] if "-" in host_id else host_id
