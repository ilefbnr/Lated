# =============================================================================
# lated.pipelines.offline.pretrain_ssl — Stage 1 SSL TGN backbone training
# =============================================================================
#
# OBJECTIVE
# ---------
# Self-supervised link-prediction pretraining of a TGN backbone over the
# PicoDomain flow stream. Backbone components (PyG):
#
#   TGNMemory(num_nodes, raw_msg_dim, memory_dim, time_dim, …)
#     ├── IdentityMessage(raw_msg_dim, memory_dim, time_dim)
#     └── LastAggregator()
#   GraphAttentionEmbedding(in=memory_dim, out=emb_dim, msg=edge_feat_dim,
#                            time_enc=TimeEncoder)
#   LinkPredictor(2 * emb_dim → 1)
#
# Training is chronological (no shuffling). The loss is computed ONLY on
# benign edges (label == 0); the memory is still updated on all edges so
# the representation reflects observed traffic.
#
# OUTPUT
# ------
#   backend/data/models/tgn_backbone.pt
# =============================================================================

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import torch
from torch import Tensor
from torch.nn import Linear, ReLU, Sequential, BCEWithLogitsLoss
from torch_geometric.data import TemporalData
from torch_geometric.loader import TemporalDataLoader
from torch_geometric.nn import TransformerConv
from torch_geometric.nn.models.tgn import (
    TGNMemory, LastNeighborLoader, IdentityMessage, LastAggregator, TimeEncoder,
)


# ----------------------------------------------------------------- config

@dataclass
class SSLConfig:
    train_path:     str   = "data/datasets/train.pt"
    out_path:       str   = "data/models/tgn_backbone.pt"
    memory_dim:     int   = 100
    time_dim:       int   = 100
    embedding_dim:  int   = 100
    n_neighbors:    int   = 10
    n_heads:        int   = 2
    dropout:        float = 0.1
    batch_size:     int   = 200
    lr:             float = 1e-4
    n_epochs:       int   = 5
    seed:           int   = 42
    device:         str   = "cuda" if torch.cuda.is_available() else "cpu"
    benign_only_loss: bool = True


# ------------------------------------------------------------ embedder

class GraphAttentionEmbedding(torch.nn.Module):
    """TGAT-style temporal attention embedder (same shape as PyG example)."""

    def __init__(self, in_channels: int, out_channels: int,
                 msg_dim: int, time_enc: TimeEncoder,
                 n_heads: int = 2, dropout: float = 0.1):
        super().__init__()
        self.time_enc = time_enc
        edge_dim = msg_dim + time_enc.out_channels
        self.conv = TransformerConv(
            in_channels, out_channels // n_heads,
            heads=n_heads, dropout=dropout, edge_dim=edge_dim,
        )

    def forward(self, x: Tensor, last_update: Tensor,
                 edge_index: Tensor, t: Tensor, msg: Tensor) -> Tensor:
        # rel_t = neighbor's last memory-update time minus the historical
        # edge time, encoded sinusoidally and concatenated with the raw msg.
        rel_t = last_update[edge_index[0]] - t
        rel_t_enc = self.time_enc(rel_t.to(x.dtype))
        edge_attr = torch.cat([rel_t_enc, msg], dim=-1)
        return self.conv(x, edge_index, edge_attr)


class LinkPredictor(torch.nn.Module):
    """2-layer MLP scoring a (z_src, z_dst) pair. Returns logits."""

    def __init__(self, in_channels: int, hidden: int = 80):
        super().__init__()
        self.net = Sequential(
            Linear(2 * in_channels, hidden), ReLU(),
            Linear(hidden, 1),
        )

    def forward(self, z_src: Tensor, z_dst: Tensor) -> Tensor:
        return self.net(torch.cat([z_src, z_dst], dim=-1)).squeeze(-1)


# ------------------------------------------------------------ data

def _make_temporal_data(blob: dict) -> TemporalData:
    """Wrap a shard's tensors as PyG TemporalData. `t` is in microseconds."""
    # PicoDomain timestamps are sub-second; preserve precision via µs ints.
    t_us = (blob["ts"].double() * 1_000_000.0).long()
    return TemporalData(
        src=blob["src_ids"].long(),
        dst=blob["dst_ids"].long(),
        t=t_us,
        msg=blob["edge_feat"].float(),
        y=blob["labels"].long(),
    )


# ------------------------------------------------------------ training

def _train_one_epoch(
    *, memory, embedder, predictor, neighbor_loader,
    data: TemporalData, loader: TemporalDataLoader,
    optimizer, loss_fn, device, n_nodes: int, assoc: Tensor,
    benign_only_loss: bool,
) -> dict:
    memory.train(); embedder.train(); predictor.train()
    memory.reset_state()
    neighbor_loader.reset_state()

    total_loss = 0.0
    total_examples = 0
    total_events = 0
    skipped_no_benign = 0

    for batch in loader:
        batch = batch.to(device)
        src, dst, t, msg, y = batch.src, batch.dst, batch.t, batch.msg, batch.y

        # 1) Negative sampling.
        neg_dst = torch.randint(0, n_nodes, (src.size(0),),
                                 dtype=torch.long, device=device)

        # 2) Gather historical neighborhood for (src ∪ dst ∪ neg_dst).
        n_id = torch.cat([src, dst, neg_dst]).unique()
        n_id, edge_index, e_id = neighbor_loader(n_id)
        assoc[n_id] = torch.arange(n_id.size(0), device=device)

        # 3) Memory state for the involved nodes.
        z, last_update = memory(n_id)

        # 4) Temporal-graph embedding. `data.t[e_id]`, `data.msg[e_id]` give
        #    the actual time/message of each historical edge.
        z = embedder(
            z, last_update, edge_index,
            t=data.t[e_id].to(device),
            msg=data.msg[e_id].to(device),
        )

        # 5) Score pos / neg pairs.
        pos = predictor(z[assoc[src]], z[assoc[dst]])
        neg = predictor(z[assoc[src]], z[assoc[neg_dst]])

        # 6) Optionally mask the loss to benign-only events.
        if benign_only_loss:
            mask = (y == 0)
            if not mask.any():
                skipped_no_benign += 1
                pos_eff = pos[:0]; neg_eff = neg[:0]
            else:
                pos_eff = pos[mask]; neg_eff = neg[mask]
        else:
            pos_eff = pos; neg_eff = neg

        if pos_eff.numel() > 0:
            loss = (loss_fn(pos_eff, torch.ones_like(pos_eff)) +
                    loss_fn(neg_eff, torch.zeros_like(neg_eff)))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * pos_eff.size(0)
            total_examples += pos_eff.size(0)

        # 7) Update memory + neighbor cache with ALL events (regardless of
        #    label — must match the inference-time stream).
        memory.update_state(src, dst, t, msg)
        neighbor_loader.insert(src, dst)
        memory.detach()
        total_events += src.size(0)

    return {
        "loss":            total_loss / max(total_examples, 1),
        "n_events":        total_events,
        "n_loss_examples": total_examples,
        "skipped_no_benign_batches": skipped_no_benign,
    }


# ------------------------------------------------------------ entry point

def run(cfg: SSLConfig | None = None) -> Path:
    cfg = cfg or SSLConfig()
    torch.manual_seed(cfg.seed)
    device = torch.device(cfg.device)
    print(f"[ssl] device={device}")

    blob = torch.load(cfg.train_path, weights_only=False, map_location="cpu")
    n_nodes       = int(blob["n_nodes"])
    edge_feat_dim = int(blob["edge_feat_dim"])
    n_events      = int(blob["src_ids"].numel())
    print(f"[ssl] data: {n_events} events, {n_nodes} nodes, "
          f"edge_feat_dim={edge_feat_dim}")

    data = _make_temporal_data(blob).to(device)
    loader = TemporalDataLoader(data, batch_size=cfg.batch_size)

    # --- module wiring (mirrors PyG's TGN example) ---
    memory = TGNMemory(
        num_nodes=n_nodes,
        raw_msg_dim=edge_feat_dim,
        memory_dim=cfg.memory_dim,
        time_dim=cfg.time_dim,
        message_module=IdentityMessage(edge_feat_dim, cfg.memory_dim, cfg.time_dim),
        aggregator_module=LastAggregator(),
    ).to(device)
    embedder = GraphAttentionEmbedding(
        in_channels=cfg.memory_dim,
        out_channels=cfg.embedding_dim,
        msg_dim=edge_feat_dim,
        time_enc=memory.time_enc,            # reuse TGNMemory's TimeEncoder
        n_heads=cfg.n_heads,
        dropout=cfg.dropout,
    ).to(device)
    predictor = LinkPredictor(cfg.embedding_dim).to(device)
    neighbor_loader = LastNeighborLoader(
        num_nodes=n_nodes, size=cfg.n_neighbors, device=device,
    )

    # De-duplicate parameters (memory.time_enc is reused by embedder).
    seen: set[int] = set()
    params: list = []
    for m in (memory, embedder, predictor):
        for p in m.parameters():
            if id(p) in seen:
                continue
            seen.add(id(p))
            params.append(p)
    optimizer = torch.optim.Adam(params, lr=cfg.lr)
    loss_fn = BCEWithLogitsLoss(reduction="mean")
    assoc = torch.empty(n_nodes, dtype=torch.long, device=device)

    history = []
    t0 = time.time()
    for epoch in range(1, cfg.n_epochs + 1):
        stats = _train_one_epoch(
            memory=memory, embedder=embedder, predictor=predictor,
            neighbor_loader=neighbor_loader,
            data=data, loader=loader,
            optimizer=optimizer, loss_fn=loss_fn,
            device=device, n_nodes=n_nodes, assoc=assoc,
            benign_only_loss=cfg.benign_only_loss,
        )
        dt = time.time() - t0
        print(f"[ssl] epoch {epoch:2d}/{cfg.n_epochs}  loss={stats['loss']:.4f}  "
              f"events={stats['n_events']}  examples={stats['n_loss_examples']}  "
              f"elapsed={dt:.1f}s")
        history.append({"epoch": epoch, **stats})

    out_path = Path(cfg.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "memory":        memory.state_dict(),
        "embedder":      embedder.state_dict(),
        "predictor":     predictor.state_dict(),
        "config":        asdict(cfg),
        "history":       history,
        "n_nodes":       n_nodes,
        "edge_feat_dim": edge_feat_dim,
    }, out_path)
    print(f"[ssl] saved checkpoint -> {out_path}  "
          f"({out_path.stat().st_size/1e6:.1f} MB)")
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train",  default="data/datasets/train.pt")
    ap.add_argument("--out",    default="data/models/tgn_backbone.pt")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch",  type=int, default=200)
    ap.add_argument("--lr",     type=float, default=1e-4)
    args = ap.parse_args()
    run(SSLConfig(
        train_path=args.train, out_path=args.out,
        n_epochs=args.epochs, batch_size=args.batch, lr=args.lr,
    ))
