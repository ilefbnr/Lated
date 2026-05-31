# =============================================================================
# lated.detection.tgnn.tgnn_inference — runtime LM scoring
# =============================================================================
#
# Real TGN inference only — no structural fallback. If the trained checkpoint
# fails to load, `score_flows` returns an empty list and the supervision layer
# treats LM as silent for that window. There is intentionally no heuristic
# substitute: degraded scoring would be indistinguishable from real model
# output downstream.
#
# INPUTS
# ------
#   - CanonicalFlow stream
#
# OUTPUTS
# -------
#   - LMScore objects (one per (subject_host, window) bucket above threshold)
#
# Per-event errors are isolated: a single bad flow increments
# `inference_errors` and is skipped, never poisoning the stream.
# =============================================================================

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from lated.common.schemas import CanonicalFlow, LMScore

from lated.detection.tgnn.model_loader import ModelArtifact


@dataclass
class TGNNInferenceMetrics:
    hosts_scored: int = 0
    inference_errors: int = 0


class TGNNInference:
    """TGN scorer over a CanonicalFlow stream.

    Construction is non-fatal: if `artifact` is None or the checkpoint cannot
    be loaded, `_tgn_runtime` stays None and `score_flows` will return [].
    Callers should check `has_runtime` before relying on LM scores.
    """

    def __init__(
        self,
        artifact: ModelArtifact | None = None,
        min_score_emission: float = 0.05,
        window_seconds: int = 60,
    ):
        self.artifact = artifact
        self.model_version = artifact.model_version if artifact is not None else None
        self.min_score_emission = float(min_score_emission)
        self.window_seconds = int(window_seconds)
        self.metrics = TGNNInferenceMetrics()
        self._tgn_runtime = self._try_load_tgn_runtime()

    @property
    def has_runtime(self) -> bool:
        return self._tgn_runtime is not None

    def _try_load_tgn_runtime(self):
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

    def score_flows(self, flow_stream: Iterable[CanonicalFlow]) -> list[LMScore]:
        """TGN inference over an event stream. Empty list when runtime absent."""
        if self._tgn_runtime is None:
            return []
        from lated.detection.tgnn.runtime_featurizer import featurize_flow

        runtime = self._tgn_runtime
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
                model_version=self.model_version or "tgn",
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
