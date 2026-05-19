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
from dataclasses import dataclass
from typing import Iterable, Iterator

from lated.common.exceptions import InferenceError
from lated.common.schemas import LMScore, TemporalSnapshot

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
    ):
        self.artifact = artifact
        self.model_version = artifact.model_version if artifact is not None else PLACEHOLDER_MODEL_VERSION
        self.min_fan_out = float(min_fan_out)
        self.min_score_emission = float(min_score_emission)
        self.metrics = TGNNInferenceMetrics()

    def score(self, snapshot_stream: Iterable[TemporalSnapshot]) -> Iterator[LMScore]:
        for snapshot in snapshot_stream:
            try:
                yield from self._score_snapshot(snapshot)
            except Exception:  # isolation: never poison the stream
                self.metrics.inference_errors += 1
                continue

    def run(self, snapshot_stream: Iterable[TemporalSnapshot]) -> list[LMScore]:
        return list(self.score(snapshot_stream))

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
