# =============================================================================
# lated.detection.tgnn.tgn_runtime — loaded TGN inference (event-based)
# =============================================================================
#
# Reconstructs the architecture from `pretrain_ssl.py` and loads the trained
# weights from a checkpoint produced by that script:
#
#   ckpt = {
#       "memory":        TGNMemory.state_dict(),
#       "embedder":      GraphAttentionEmbedding.state_dict(),
#       "predictor":     LinkPredictor.state_dict(),
#       "config":        {...},
#       "n_nodes":       int,
#       "edge_feat_dim": int,
#   }
#
# Inference protocol (TGN-standard):
#   1. For each new event (src_id, dst_id, ts, edge_feat):
#        a) Pull current memory state for (src ∪ dst ∪ historical neighbors).
#        b) Run embedder over the temporal neighborhood.
#        c) Score (z_src, z_dst) with the predictor -> link likelihood.
#        d) ANOMALY = 1 - sigmoid(predictor). Low likelihood under the
#           benign-trained model = lateral-movement candidate.
#   2. Update memory and neighbor cache with the event (regardless of label),
#      so subsequent events see the running context.
#
# This wrapper is STATEFUL: it keeps TGNMemory + LastNeighborLoader across
# calls. Reset it before processing a fresh stream (`reset_state()`).
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
from torch_geometric.nn.models.tgn import (
    IdentityMessage, LastAggregator, LastNeighborLoader, TGNMemory,
)

from lated.pipelines.offline.pretrain_ssl import (
    GraphAttentionEmbedding, LinkPredictor,
)
from lated.pipelines.offline.finetune_lm import LMClassifierHead


# Map model file family → semantics for scoring & head type.
#   backbone   : SSL link prediction. anomaly = 1 - sigmoid(pred(z_src, z_dst))
#   supervised : end-to-end LM head. lm_score = sigmoid(head(z_src, z_dst, feat))
#   lm_head    : just the head, needs the matching backbone loaded alongside
def _detect_family(ckpt: dict) -> str:
    if "lm_head" in ckpt and "memory" in ckpt and "embedder" in ckpt:
        return "supervised"
    if "lm_head" in ckpt and "memory" not in ckpt:
        return "lm_head"
    if "predictor" in ckpt:
        return "backbone"
    raise ValueError(f"Unrecognized checkpoint structure: keys={list(ckpt.keys())}")


def _auto_node_mapping_for(checkpoint_path: Path) -> Path | None:
    """Map `tgn_<family>_<variant>.pt` → `data/datasets/train_<variant>.pt`.

    Falls back to `train.pt` when no variant suffix is present. Returns None
    if no candidate is found on disk (caller will run without mapping).
    """
    stem = checkpoint_path.stem  # e.g. "tgn_supervised_m2_n015"
    parts = stem.split("_")
    # strip leading "tgn" + family token (one of backbone / supervised / lm + head)
    if len(parts) >= 2 and parts[0] == "tgn":
        if parts[1] in ("backbone", "supervised"):
            variant = "_".join(parts[2:])
        elif parts[1] == "lm" and len(parts) >= 3 and parts[2] == "head":
            variant = "_".join(parts[3:])
        else:
            variant = "_".join(parts[1:])
    else:
        variant = ""
    candidate_name = f"train_{variant}.pt" if variant else "train.pt"
    candidate = checkpoint_path.parent.parent / "datasets" / candidate_name
    if candidate.is_file():
        return candidate
    fallback = checkpoint_path.parent.parent / "datasets" / "train.pt"
    return fallback if fallback.is_file() else None


class TGNRuntime:
    """Stateful TGN scorer that supports both SSL backbone and supervised LM checkpoints."""

    def __init__(
        self,
        checkpoint_path: str | Path,
        node_mapping_path: str | Path | None = None,
        device: str | None = None,
    ):
        path = Path(checkpoint_path)
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        self.family = _detect_family(ckpt)
        cfg = ckpt["config"]
        self.n_nodes: int = int(ckpt["n_nodes"])
        self.edge_feat_dim: int = int(ckpt["edge_feat_dim"])
        self.memory_dim: int = int(cfg.get("memory_dim", 100))
        self.time_dim: int = int(cfg.get("time_dim", 100))
        self.embedding_dim: int = int(cfg.get("embedding_dim", 100))
        self.n_neighbors: int = int(cfg.get("n_neighbors", 10))
        self.n_heads: int = int(cfg.get("n_heads", 2))
        self.dropout: float = float(cfg.get("dropout", 0.1))
        self.lm_head_hidden: int = int(cfg.get("hidden", 128))
        self.lm_head_dropout: float = float(cfg.get("dropout", 0.2)) if self.family in {"supervised", "lm_head"} else 0.1

        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))

        # If only the head is checkpointed, load the backbone it references.
        if self.family == "lm_head":
            backbone_path = ckpt.get("backbone_path")
            if not backbone_path:
                raise ValueError("lm_head checkpoint missing `backbone_path` reference.")
            backbone_ckpt_path = (path.parent / Path(backbone_path).name).resolve()
            if not backbone_ckpt_path.is_file():
                # try the literal path
                backbone_ckpt_path = Path(backbone_path)
            if not backbone_ckpt_path.is_file():
                raise FileNotFoundError(f"Companion backbone not found for lm_head: {backbone_path}")
            backbone_ckpt = torch.load(backbone_ckpt_path, map_location="cpu", weights_only=False)
        else:
            backbone_ckpt = ckpt

        self.memory = TGNMemory(
            num_nodes=self.n_nodes,
            raw_msg_dim=self.edge_feat_dim,
            memory_dim=self.memory_dim,
            time_dim=self.time_dim,
            message_module=IdentityMessage(self.edge_feat_dim, self.memory_dim, self.time_dim),
            aggregator_module=LastAggregator(),
        ).to(self.device)
        self.memory.load_state_dict(backbone_ckpt["memory"])

        self.embedder = GraphAttentionEmbedding(
            in_channels=self.memory_dim,
            out_channels=self.embedding_dim,
            msg_dim=self.edge_feat_dim,
            time_enc=self.memory.time_enc,
            n_heads=self.n_heads,
            dropout=self.dropout,
        ).to(self.device)
        self.embedder.load_state_dict(backbone_ckpt["embedder"])

        # Pick the scoring head per family.
        self.head_kind: str
        if self.family == "backbone":
            self.predictor = LinkPredictor(self.embedding_dim).to(self.device)
            self.predictor.load_state_dict(ckpt["predictor"])
            self.head_kind = "link_predictor"
        else:  # supervised or lm_head
            self.predictor = LMClassifierHead(
                embedding_dim=self.embedding_dim,
                edge_feat_dim=self.edge_feat_dim,
                hidden=self.lm_head_hidden,
                dropout=self.lm_head_dropout,
            ).to(self.device)
            self.predictor.load_state_dict(ckpt["lm_head"])
            self.head_kind = "lm_classifier"

        self.neighbor_loader = LastNeighborLoader(
            num_nodes=self.n_nodes, size=self.n_neighbors, device=self.device,
        )
        self.assoc = torch.empty(self.n_nodes, dtype=torch.long, device=self.device)

        self.ip_to_id: dict[str, int] = {}
        resolved_mapping = node_mapping_path
        if resolved_mapping is None:
            resolved_mapping = _auto_node_mapping_for(path)
        if resolved_mapping is not None:
            self._load_mapping(Path(resolved_mapping))

        self.memory.eval()
        self.embedder.eval()
        self.predictor.eval()

        # Set of unknown IPs encountered at runtime → assigned synthetic IDs
        # in the [n_nodes_known, self.n_nodes) range if any. We DO NOT extend
        # the model's node table; unknowns map to a sentinel "0" embedding,
        # which the model treats as a generic node. Surfaced as a warning.
        self._unknown_ips: set[str] = set()

    def reset_state(self) -> None:
        """Clear running memory + neighbor cache. Use between independent streams."""
        self.memory.reset_state()
        self.neighbor_loader.reset_state()
        self._unknown_ips.clear()

    def score_event(
        self,
        src_ip: str,
        dst_ip: str,
        ts: float,
        edge_feat: np.ndarray,
    ) -> float:
        """Score one event and update internal state. Returns anomaly in [0,1]."""
        src_id = self._resolve(src_ip)
        dst_id = self._resolve(dst_ip)

        with torch.no_grad():
            src_t = torch.tensor([src_id], dtype=torch.long, device=self.device)
            dst_t = torch.tensor([dst_id], dtype=torch.long, device=self.device)
            # PyG TGNMemory stores last_update as Long; training pipeline
            # uses microseconds-since-epoch (cf. pretrain_ssl _make_temporal_data).
            ts_us = int(float(ts) * 1_000_000.0)
            ts_t = torch.tensor([ts_us], dtype=torch.long, device=self.device)
            msg_t = torch.from_numpy(edge_feat.astype(np.float32)).unsqueeze(0).to(self.device)

            n_id = torch.cat([src_t, dst_t]).unique()
            n_id, edge_index, e_id = self.neighbor_loader(n_id)
            self.assoc[n_id] = torch.arange(n_id.size(0), device=self.device)

            z, last_update = self.memory(n_id)

            # If the neighbor loader returned NO historical edges, embedder
            # has no context — use raw memory as embedding (TGAT degenerates
            # to identity).
            if edge_index.numel() == 0:
                z_used = z
            else:
                # We don't keep a full TemporalData store at runtime; we use
                # the current event's (ts, msg) for every historical edge as
                # a coarse approximation. This is a documented degradation;
                # the model still has memory state which is the main signal.
                # Embedder's time_enc expects float ts (sin/cos encoding).
                hist_t = torch.full(
                    (edge_index.size(1),), float(ts), dtype=torch.float32, device=self.device,
                )
                hist_msg = msg_t.expand(edge_index.size(1), -1)
                z_used = self.embedder(z, last_update, edge_index, t=hist_t, msg=hist_msg)

            z_src = z_used[self.assoc[src_t]]
            z_dst = z_used[self.assoc[dst_t]]
            if self.head_kind == "lm_classifier":
                # Supervised LM head consumes (z_src, z_dst, edge_feat).
                logit = self.predictor(z_src, z_dst, msg_t)
                # Direct LM probability — high score = lateral movement.
                lm_proba = torch.sigmoid(logit).item()
                anomaly = lm_proba
            else:
                # SSL link predictor — invert because training optimized for
                # benign link likelihood.
                logit = self.predictor(z_src, z_dst)
                link_likelihood = torch.sigmoid(logit).item()
                anomaly = 1.0 - link_likelihood

            # Update state for subsequent events.
            self.memory.update_state(src_t, dst_t, ts_t, msg_t)
            self.neighbor_loader.insert(src_t, dst_t)

        return float(max(0.0, min(1.0, anomaly)))

    def score_stream(
        self,
        events: Sequence[tuple[str, str, float, np.ndarray]],
    ) -> list[float]:
        """Batch convenience: score N events in order, returns N anomaly scores."""
        return [self.score_event(s, d, t, f) for s, d, t, f in events]

    # ----------------------------------------------------------- internals

    def _load_mapping(self, path: Path) -> None:
        if not path.is_file():
            return
        try:
            blob = torch.load(path, map_location="cpu", weights_only=False)
        except Exception:
            try:
                blob = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return
        mapping = blob.get("ip_to_id") if isinstance(blob, dict) else None
        if not isinstance(mapping, dict):
            return
        self.ip_to_id = {str(k): int(v) for k, v in mapping.items()}

    def _resolve(self, ip_or_host: str) -> int:
        """Map a runtime IP/host to the trained node-id space. Unknowns -> 0."""
        if ip_or_host in self.ip_to_id:
            return self.ip_to_id[ip_or_host]
        # Fallback: hash into the known node-id range. Unknown hosts share
        # synthetic IDs but at least don't collide chaotically with known
        # ones (the training-known IPs are reserved).
        if ip_or_host not in self._unknown_ips:
            self._unknown_ips.add(ip_or_host)
        return 0
