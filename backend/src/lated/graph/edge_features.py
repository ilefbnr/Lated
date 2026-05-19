# =============================================================================
# lated.graph.edge_features — per-edge feature engineering
# =============================================================================
#
# Computes EdgeFeatures (see common.schemas) from the list of CanonicalFlow
# records observed on a single (src, dst) edge within one closed window.
#
# Determinism: all aggregations are order-independent sums / set sizes;
# entropy is computed from a sorted port distribution.
#
# Future-leak guard: nothing here reads any data from windows that have not
# yet been finalized. `temporal_delta` is computed against a `last_seen`
# map passed in by the builder — it is only mutated AFTER the snapshot for
# the current window has been emitted.
# =============================================================================

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Iterable

from lated.common.schemas import CanonicalFlow, EdgeFeatures


class EdgeFeatureEngineer:
    """Compute EdgeFeatures from per-edge CanonicalFlow lists."""

    def __init__(self, feature_set: Iterable[str] | None = None):
        # feature_set is accepted for forward compatibility but the MVP always
        # produces the full EdgeFeatures vector (the model has no optional fields).
        self.feature_set = tuple(feature_set) if feature_set else ()

    def compute(
        self,
        flows: list[CanonicalFlow],
        fan_out: int,
        fan_in: int,
        previous_seen_ts: datetime | None,
    ) -> EdgeFeatures:
        bytes_total = float(sum(flow.byte_count for flow in flows))
        packets_total = float(sum(flow.packet_count for flow in flows))
        duration_total = float(sum(flow.duration for flow in flows))
        port_entropy = self._shannon_entropy([flow.dst_port for flow in flows])

        if previous_seen_ts is not None and flows:
            first_ts = min(flow.ts for flow in flows)
            temporal_delta = max(0.0, (first_ts - previous_seen_ts).total_seconds())
        else:
            temporal_delta = 0.0

        return EdgeFeatures(
            bytes=bytes_total,
            packets=packets_total,
            duration=duration_total,
            port_entropy=port_entropy,
            fan_out=float(fan_out),
            fan_in=float(fan_in),
            temporal_delta=temporal_delta,
        )

    @staticmethod
    def _shannon_entropy(values: list[int]) -> float:
        if not values:
            return 0.0
        counts = Counter(values)
        total = float(sum(counts.values()))
        entropy = 0.0
        for count in counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        return entropy
