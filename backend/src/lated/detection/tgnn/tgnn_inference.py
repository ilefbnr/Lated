# =============================================================================
# lated.detection.tgnn.tgnn_inference — runtime LM scoring (MVP placeholder)
# =============================================================================
#
# Real trained TGNN weights are out of scope for this phase. The runtime
# wrapper below preserves the architectural contract:
#
#   - consumes a TemporalSnapshot stream,
#   - emits LMScore objects with the canonical schema,
#   - isolates failures per-snapshot (one bad snapshot must not poison the
#     stream),
#   - exposes a stable interface that a future torch-backed scorer can drop
#     into.
#
# Scoring is a deterministic structural heuristic on the snapshot:
#
#   raw = 0.6 * tanh(fan_out / 5) + 0.4 * tanh(frequency * 3)
#   score = clamp(raw, 0, 1)
#
# It surfaces high-fan-out + high-frequency hosts inside a window — a coarse
# but real proxy for lateral-movement-style activity. Documented limitation:
# this is NOT a trained model; production deployments must swap it in.
# =============================================================================

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Iterator

from lated.common.exceptions import InferenceError
from lated.common.schemas import CanonicalFlow, LMScore, TemporalSnapshot

from lated.detection.tgnn.model_loader import ModelArtifact


PLACEHOLDER_MODEL_VERSION = "placeholder-structural-1.0.0"


@dataclass
class TGNNInferenceMetrics:
    snapshots_scored: int = 0
    hosts_scored: int = 0
    inference_errors: int = 0


class TGNNInference:
    """Deterministic LM scorer over TemporalSnapshot streams (MVP)."""

    def __init__(
        self,
        artifact: ModelArtifact | None = None,
        min_fan_out: float = 1.0,
        min_score_emission: float = 0.05,
        window_seconds: int = 60,
    ):
        self.artifact = artifact
        self.model_version = artifact.model_version if artifact is not None else PLACEHOLDER_MODEL_VERSION
        self.min_fan_out = float(min_fan_out)
        self.min_score_emission = float(min_score_emission)
        self.window_seconds = int(window_seconds)
        self.metrics = TGNNInferenceMetrics()
        self._tgn_runtime = self._try_load_tgn_runtime()

    def _try_load_tgn_runtime(self):
        """Attempt to load the real TGN backbone if artifact path is set.

        Returns a TGNRuntime instance on success, None on any failure. The
        placeholder structural scorer is used when this returns None.
        """
        if self.artifact is None:
            return None
        try:
            from lated.detection.tgnn.tgn_runtime import TGNRuntime
            return TGNRuntime(
                checkpoint_path=self.artifact.path,
                node_mapping_path=self.artifact.node_mapping_path,
                device="cpu",
            )
        except Exception:
            return None

    def score(self, snapshot_stream: Iterable[TemporalSnapshot]) -> Iterator[LMScore]:
        for snapshot in snapshot_stream:
            try:
                yield from self._score_snapshot(snapshot)
            except Exception:  # isolation: never poison the stream
                self.metrics.inference_errors += 1
                continue

    def run(self, snapshot_stream: Iterable[TemporalSnapshot]) -> list[LMScore]:
        return list(self.score(snapshot_stream))

    def score_flows(self, flow_stream: Iterable[CanonicalFlow]) -> list[LMScore]:
        """Real TGN inference path over an event stream.

        Falls back to an empty list if the TGN runtime failed to load — the
        caller should still call `.run(snapshots)` in that case to keep the
        placeholder structural signal alive (used by tests + offline pipeline).
        """
        if self._tgn_runtime is None:
            return []
        from lated.detection.tgnn.runtime_featurizer import featurize_flow

        runtime = self._tgn_runtime
        # bucket per (subject_host, window_start) — we accumulate per-edge
        # anomalies into a single LMScore per host per window (max score,
        # union of contributing edges).
        buckets: dict[tuple[str, datetime], _HostBucket] = {}

        ordered = sorted(flow_stream, key=lambda f: f.ts)
        for flow in ordered:
            ts_utc = flow.ts if flow.ts.tzinfo else flow.ts.replace(tzinfo=timezone.utc)
            window_start = self._window_start(ts_utc)
            try:
                feat = featurize_flow(flow)
                anomaly = runtime.score_event(
                    src_ip=flow.src_host,
                    dst_ip=flow.dst_host,
                    ts=ts_utc.timestamp(),
                    edge_feat=feat,
                )
            except Exception:
                self.metrics.inference_errors += 1
                continue

            key = (flow.src_host, window_start)
            bucket = buckets.get(key)
            if bucket is None:
                bucket = _HostBucket()
                buckets[key] = bucket
            bucket.update(anomaly, flow.src_host, flow.dst_host)

        scores: list[LMScore] = []
        for (host, window_start), bucket in sorted(buckets.items()):
            if bucket.max_score < self.min_score_emission:
                continue
            self.metrics.hosts_scored += 1
            scores.append(LMScore(
                window_start=window_start,
                subject_host=host,
                score=bucket.max_score,
                contributing_edges=bucket.top_edges(5),
                model_version=self.model_version,
                target_hosts=sorted(bucket.targets),
                evidence=[f"{s}->{d}" for s, d in bucket.top_edges(5)],
                confidence=bucket.max_score,
                explainability={
                    "edge_count": bucket.edge_count,
                    "mean_anomaly": bucket.mean_score,
                    "max_anomaly": bucket.max_score,
                },
            ))
        return scores

    def _window_start(self, ts: datetime) -> datetime:
        epoch = int(ts.timestamp())
        bucket = epoch - (epoch % self.window_seconds)
        return datetime.fromtimestamp(bucket, tz=timezone.utc)

    def _score_snapshot(self, snapshot: TemporalSnapshot) -> Iterator[LMScore]:
        self.metrics.snapshots_scored += 1
        edges_by_src: dict[str, list[tuple[str, float]]] = {}
        for src, dst in snapshot.edges:
            weight = float(snapshot.edge_features.get(f"{src}->{dst}").bytes) if f"{src}->{dst}" in snapshot.edge_features else 0.0
            edges_by_src.setdefault(src, []).append((dst, weight))

        for host_id in snapshot.nodes:
            node_feats = snapshot.node_features.get(host_id)
            if node_feats is None:
                continue
            if node_feats.fan_out < self.min_fan_out:
                continue
            raw = (
                0.6 * math.tanh(node_feats.fan_out / 5.0)
                + 0.4 * math.tanh(node_feats.communication_frequency * 3.0)
            )
            score = self._clamp(raw)
            if score < self.min_score_emission:
                continue
            contributing = self._top_edges_for_host(host_id, edges_by_src.get(host_id, []), top_k=5)
            self.metrics.hosts_scored += 1
            yield LMScore(
                window_start=snapshot.window_start,
                subject_host=host_id,
                score=score,
                contributing_edges=contributing,
                model_version=self.model_version,
                target_hosts=sorted({dst for _src, dst in contributing}),
                evidence=[f"{src}->{dst}" for src, dst in contributing],
                confidence=score,
                explainability={
                    "fan_out": node_feats.fan_out,
                    "communication_frequency": node_feats.communication_frequency,
                    "unique_neighbors": node_feats.unique_neighbors,
                },
            )

    @staticmethod
    def _top_edges_for_host(
        src: str, edges: list[tuple[str, float]], top_k: int
    ) -> list[tuple[str, str]]:
        if not edges:
            return []
        ordered = sorted(edges, key=lambda item: (-item[1], item[0]))[:top_k]
        return [(src, dst) for dst, _weight in ordered]

    def _ensure_model_loaded_if_required(self) -> None:
        # Hook for future torch wiring; current MVP doesn't fail if absent.
        if self.artifact is None:
            return
        if not self.artifact.path.exists():
            raise InferenceError("Model artifact path no longer exists.")

    @staticmethod
    def _clamp(value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return float(value)


class _HostBucket:
    """Per (host, window) accumulator for TGN edge-level anomalies."""

    __slots__ = ("max_score", "sum_score", "edge_count", "targets", "_scored_edges")

    def __init__(self) -> None:
        self.max_score: float = 0.0
        self.sum_score: float = 0.0
        self.edge_count: int = 0
        self.targets: set[str] = set()
        self._scored_edges: list[tuple[str, str, float]] = []

    def update(self, anomaly: float, src: str, dst: str) -> None:
        self.max_score = max(self.max_score, anomaly)
        self.sum_score += anomaly
        self.edge_count += 1
        self.targets.add(dst)
        self._scored_edges.append((src, dst, anomaly))

    @property
    def mean_score(self) -> float:
        return self.sum_score / self.edge_count if self.edge_count else 0.0

    def top_edges(self, top_k: int) -> list[tuple[str, str]]:
        ordered = sorted(self._scored_edges, key=lambda item: -item[2])[:top_k]
        return [(s, d) for s, d, _a in ordered]
