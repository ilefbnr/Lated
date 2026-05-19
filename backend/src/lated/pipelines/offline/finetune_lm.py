# =============================================================================
# lated.pipelines.offline.finetune_lm — Stage 2 supervised LM head
# =============================================================================
#
# OBJECTIVE
# ---------
# Train an LM classifier head on top of the Stage-1 frozen TGN backbone.
# The head takes (z_src, z_dst, edge_feat) and outputs P(edge is LM).
#
# Backbone (memory + embedder + time-enc) is loaded from Stage 1 and frozen.
# Memory is reset at the start of each epoch and streamed forward through
# the chronological event sequence — same protocol as inference time.
#
# LABEL FILTER (per design spec)
# ------------------------------
#   - label 2 (LM_ok)  → target = 1
#   - label 0 (benign) → target = 0
#   - label 1 (recon)  → EXCLUDED (lives in another head)
#   - label 3 (LM_ko)  → would map to 1 — unused in PicoDomain
#   - label 4 (c2)     → out of scope
#
# CLASS IMBALANCE
# ---------------
# PicoDomain train shard: 575 LM_ok vs 191,750 benign ≈ 1:333.
# BCEWithLogitsLoss(pos_weight=≈ratio) handles it without needing focal loss.
#
# OUTPUT
# ------
#   backend/data/models/tgn_lm_head.pt
# =============================================================================

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import torch
from torch import Tensor
from torch.nn import Linear, ReLU, Dropout, Sequential, BCEWithLogitsLoss
from torch_geometric.data import TemporalData
from torch_geometric.loader import TemporalDataLoader
from torch_geometric.nn.models.tgn import (
    TGNMemory, LastNeighborLoader, IdentityMessage, LastAggregator,
)

from lated.pipelines.offline.pretrain_ssl import (
    GraphAttentionEmbedding, LinkPredictor, _make_temporal_data,
)


# ----------------------------------------------------------------- config

@dataclass
class LMConfig:
    train_path:     str   = "data/datasets/train.pt"
    eval_path:      str   = "data/datasets/eval.pt"
    backbone_path:  str   = "data/models/tgn_backbone.pt"
    out_path:       str   = "data/models/tgn_lm_head.pt"
    hidden:         int   = 128
    dropout:        float = 0.2
    batch_size:     int   = 200
    lr:             float = 1e-3
    n_epochs:       int   = 10
    seed:           int   = 42
    device:         str   = "cuda" if torch.cuda.is_available() else "cpu"


# ----------------------------------------------------------------- model

class LMClassifierHead(torch.nn.Module):
    """3-layer MLP scoring P(edge is LM). Returns LOGITS."""

    def __init__(self, embedding_dim: int, edge_feat_dim: int,
                 hidden: int = 128, dropout: float = 0.2):
        super().__init__()
        in_dim = 2 * embedding_dim + edge_feat_dim
        self.net = Sequential(
            Linear(in_dim, hidden), ReLU(), Dropout(dropout),
            Linear(hidden, hidden // 2), ReLU(),
            Linear(hidden // 2, 1),
        )

    def forward(self, z_src: Tensor, z_dst: Tensor, edge_feat: Tensor) -> Tensor:
        x = torch.cat([z_src, z_dst, edge_feat], dim=-1)
        return self.net(x).squeeze(-1)


# ------------------------------------------------------------- backbone loader

def _load_frozen_backbone(ckpt_path: str, n_nodes: int, edge_feat_dim: int,
                           device: torch.device):
    """Rebuild Stage-1 modules from the checkpoint and freeze them."""
    ckpt = torch.load(ckpt_path, weights_only=False, map_location=device)
    cfg  = ckpt["config"]

    memory = TGNMemory(
        num_nodes=n_nodes,
        raw_msg_dim=edge_feat_dim,
        memory_dim=cfg["memory_dim"],
        time_dim=cfg["time_dim"],
        message_module=IdentityMessage(edge_feat_dim, cfg["memory_dim"], cfg["time_dim"]),
        aggregator_module=LastAggregator(),
    ).to(device)
    memory.load_state_dict(ckpt["memory"])

    embedder = GraphAttentionEmbedding(
        in_channels=cfg["memory_dim"],
        out_channels=cfg["embedding_dim"],
        msg_dim=edge_feat_dim,
        time_enc=memory.time_enc,
        n_heads=cfg["n_heads"],
        dropout=cfg["dropout"],
    ).to(device)
    embedder.load_state_dict(ckpt["embedder"])

    # Freeze.
    for m in (memory, embedder):
        for p in m.parameters():
            p.requires_grad = False

    return memory, embedder, cfg


# ----------------------------------------------------------------- training

def _stream_epoch(*, memory, embedder, lm_head, neighbor_loader,
                   data, loader, optimizer, loss_fn, device, assoc,
                   train: bool):
    """One streaming pass: forward through frozen backbone, train LM head."""
    if train:
        lm_head.train()
    else:
        lm_head.eval()
    memory.eval()                     # backbone is frozen
    embedder.eval()
    memory.reset_state()
    neighbor_loader.reset_state()

    total_loss   = 0.0
    total_examples = 0
    all_scores: list[Tensor] = []
    all_labels: list[Tensor] = []

    for batch in loader:
        batch = batch.to(device)
        src, dst, t, msg, y = batch.src, batch.dst, batch.t, batch.msg, batch.y

        # 1) Frozen-backbone forward pass.
        n_id = torch.cat([src, dst]).unique()
        n_id, edge_index, e_id = neighbor_loader(n_id)
        assoc[n_id] = torch.arange(n_id.size(0), device=device)

        with torch.no_grad():
            z, last_update = memory(n_id)
            z = embedder(
                z, last_update, edge_index,
                t=data.t[e_id].to(device),
                msg=data.msg[e_id].to(device),
            )
        z_src = z[assoc[src]]
        z_dst = z[assoc[dst]]

        # 2) LM head prediction.
        logits = lm_head(z_src, z_dst, msg)

        # 3) Mask out recon (label==1) — head is binary LM-vs-benign.
        mask = (y != 1)
        if mask.any():
            target = (y[mask] == 2).float()        # 1 for LM, 0 for benign
            logits_eff = logits[mask]
            if train:
                loss = loss_fn(logits_eff, target)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            else:
                loss = loss_fn(logits_eff, target)
            total_loss += loss.item() * logits_eff.size(0)
            total_examples += logits_eff.size(0)
            all_scores.append(torch.sigmoid(logits_eff).detach().cpu())
            all_labels.append(target.detach().cpu())

        # 4) Stream the backbone state forward (same as inference).
        with torch.no_grad():
            memory.update_state(src, dst, t, msg)
            neighbor_loader.insert(src, dst)

    scores = torch.cat(all_scores) if all_scores else torch.zeros(0)
    labels = torch.cat(all_labels) if all_labels else torch.zeros(0)
    return {
        "loss":      total_loss / max(total_examples, 1),
        "n_examples": total_examples,
        "scores":    scores,
        "labels":    labels,
    }


def _compute_metrics(scores: Tensor, labels: Tensor) -> dict[str, float]:
    """AUC-ROC + AUC-PR + recall@1%/10% FPR. NumPy only, no sklearn import cost."""
    if scores.numel() == 0 or labels.sum() == 0:
        return {"auc_roc": float("nan"), "auc_pr": float("nan"),
                "recall_at_1pct_fpr": 0.0, "recall_at_10pct_fpr": 0.0}
    try:
        from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve
    except ImportError:
        return {"auc_roc": float("nan"), "auc_pr": float("nan")}
    y = labels.numpy(); s = scores.numpy()
    auc = float(roc_auc_score(y, s))
    ap  = float(average_precision_score(y, s))
    fpr, tpr, _ = roc_curve(y, s)
    import numpy as np
    r1  = float(tpr[np.searchsorted(fpr, 0.01, side="right") - 1]) if (fpr <= 0.01).any() else 0.0
    r10 = float(tpr[np.searchsorted(fpr, 0.10, side="right") - 1]) if (fpr <= 0.10).any() else 0.0
    return {"auc_roc": auc, "auc_pr": ap,
            "recall_at_1pct_fpr": r1, "recall_at_10pct_fpr": r10}


# ----------------------------------------------------------------- entry

def run(cfg: LMConfig | None = None) -> Path:
    cfg = cfg or LMConfig()
    torch.manual_seed(cfg.seed)
    device = torch.device(cfg.device)
    print(f"[lm-head] device={device}")

    train_blob = torch.load(cfg.train_path, weights_only=False, map_location="cpu")
    eval_blob  = torch.load(cfg.eval_path,  weights_only=False, map_location="cpu")
    n_nodes       = int(train_blob["n_nodes"])
    edge_feat_dim = int(train_blob["edge_feat_dim"])

    # Class-imbalance pos_weight = (#negatives / #positives) on training set,
    # excluding recon (label 1).
    y = train_blob["labels"]
    pos = int((y == 2).sum())
    neg = int((y == 0).sum())
    pos_weight = max(neg / max(pos, 1), 1.0)
    print(f"[lm-head] train: pos={pos} neg={neg} pos_weight={pos_weight:.1f}")

    train_data = _make_temporal_data(train_blob).to(device)
    eval_data  = _make_temporal_data(eval_blob).to(device)
    train_loader = TemporalDataLoader(train_data, batch_size=cfg.batch_size)
    eval_loader  = TemporalDataLoader(eval_data,  batch_size=cfg.batch_size)

    memory, embedder, bcfg = _load_frozen_backbone(
        cfg.backbone_path, n_nodes, edge_feat_dim, device,
    )
    print(f"[lm-head] loaded backbone: emb_dim={bcfg['embedding_dim']} "
          f"mem_dim={bcfg['memory_dim']}")

    lm_head = LMClassifierHead(
        embedding_dim=bcfg["embedding_dim"],
        edge_feat_dim=edge_feat_dim,
        hidden=cfg.hidden,
        dropout=cfg.dropout,
    ).to(device)

    neighbor_loader = LastNeighborLoader(
        num_nodes=n_nodes, size=bcfg["n_neighbors"], device=device,
    )
    optimizer = torch.optim.Adam(lm_head.parameters(), lr=cfg.lr)
    loss_fn = BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight, device=device))
    assoc = torch.empty(n_nodes, dtype=torch.long, device=device)

    history = []
    t0 = time.time()
    for epoch in range(1, cfg.n_epochs + 1):
        tr = _stream_epoch(
            memory=memory, embedder=embedder, lm_head=lm_head,
            neighbor_loader=neighbor_loader,
            data=train_data, loader=train_loader,
            optimizer=optimizer, loss_fn=loss_fn,
            device=device, assoc=assoc, train=True,
        )
        m_tr = _compute_metrics(tr["scores"], tr["labels"])
        dt = time.time() - t0
        print(f"[lm-head] ep{epoch:2d}/{cfg.n_epochs}  loss={tr['loss']:.4f}  "
              f"AUC={m_tr['auc_roc']:.3f}  AP={m_tr['auc_pr']:.3f}  "
              f"rec@10%fpr={m_tr['recall_at_10pct_fpr']:.3f}  "
              f"({dt:.1f}s)")
        history.append({"epoch": epoch, "split": "train", **m_tr,
                          "loss": tr["loss"], "n_examples": tr["n_examples"]})

    # Final eval pass on day 3.
    ev = _stream_epoch(
        memory=memory, embedder=embedder, lm_head=lm_head,
        neighbor_loader=neighbor_loader,
        data=eval_data, loader=eval_loader,
        optimizer=optimizer, loss_fn=loss_fn,
        device=device, assoc=assoc, train=False,
    )
    m_ev = _compute_metrics(ev["scores"], ev["labels"])
    print(f"[lm-head] EVAL  loss={ev['loss']:.4f}  AUC={m_ev['auc_roc']:.3f}  "
          f"AP={m_ev['auc_pr']:.3f}  "
          f"rec@1%fpr={m_ev['recall_at_1pct_fpr']:.3f}  "
          f"rec@10%fpr={m_ev['recall_at_10pct_fpr']:.3f}")
    history.append({"epoch": cfg.n_epochs, "split": "eval", **m_ev,
                      "loss": ev["loss"], "n_examples": ev["n_examples"]})

    out_path = Path(cfg.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "lm_head":       lm_head.state_dict(),
        "config":        asdict(cfg),
        "backbone_path": cfg.backbone_path,
        "history":       history,
        "n_nodes":       n_nodes,
        "edge_feat_dim": edge_feat_dim,
    }, out_path)
    print(f"[lm-head] saved -> {out_path}  ({out_path.stat().st_size/1e6:.2f} MB)")
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train",    default="data/datasets/train.pt")
    ap.add_argument("--eval",     default="data/datasets/eval.pt")
    ap.add_argument("--backbone", default="data/models/tgn_backbone.pt")
    ap.add_argument("--out",      default="data/models/tgn_lm_head.pt")
    ap.add_argument("--epochs",   type=int, default=10)
    ap.add_argument("--batch",    type=int, default=200)
    ap.add_argument("--lr",       type=float, default=1e-3)
    args = ap.parse_args()
    run(LMConfig(
        train_path=args.train, eval_path=args.eval,
        backbone_path=args.backbone, out_path=args.out,
        n_epochs=args.epochs, batch_size=args.batch, lr=args.lr,
    ))
