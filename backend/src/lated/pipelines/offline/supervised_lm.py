# =============================================================================
# lated.pipelines.offline.supervised_lm — Fully supervised LM training baseline
# =============================================================================
#
# OBJECTIVE
# ---------
# Train the entire TGN stack (memory + embedder + LM head) END-TO-END with a
# supervised BCE loss directly on the LM labels. No SSL pretraining is used —
# the backbone is randomly initialised and learns jointly with the head.
#
# This file serves as the *third* training regime alongside:
#
#     pretrain_ssl.py   →  Stage A : self-supervised link-prediction backbone
#     finetune_lm.py    →  Stage B : semi-supervised head on a frozen SSL
#                                    backbone (uses weak labels via
#                                    weak_labeler.py for the supervised target)
#     supervised_lm.py  →  Stage C : fully supervised end-to-end (this file)
#
# The three regimes share the same architecture, dataset, label convention,
# and metric protocol so their results can be compared apples-to-apples by
# `compare_training.py`.
#
# LABEL FILTER (identical to finetune_lm.py)
# ------------------------------------------
#   - label 2 (LM_ok)  → target = 1
#   - label 0 (benign) → target = 0
#   - label 1 (recon)  → EXCLUDED from the loss (recon is a separate head)
#
# CLASS IMBALANCE
# ---------------
# Same imbalance as finetune_lm.py (≈1:333 on PicoDomain train). Handled by
# BCEWithLogitsLoss(pos_weight = #neg / #pos).
#
# WHY THIS MATTERS
# ----------------
# A fully supervised baseline answers the question: *does the SSL pretraining
# actually help?* If the supervised-only run matches the semi-supervised run,
# the SSL stage is dead weight. If it underperforms, SSL is doing real work.
#
# OUTPUT
# ------
#   backend/data/models/tgn_supervised.pt
# =============================================================================

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import torch
from torch import Tensor
from torch.nn import BCEWithLogitsLoss
from torch_geometric.data import TemporalData
from torch_geometric.loader import TemporalDataLoader
from torch_geometric.nn.models.tgn import (
    TGNMemory, LastNeighborLoader, IdentityMessage, LastAggregator,
)

from lated.pipelines.offline.pretrain_ssl import (
    GraphAttentionEmbedding, _make_temporal_data,
)
from lated.pipelines.offline.finetune_lm import (
    LMClassifierHead, _compute_metrics,
)


# ----------------------------------------------------------------- config

@dataclass
class SupervisedConfig:
    train_path:     str   = "data/datasets/train.pt"
    eval_path:      str   = "data/datasets/eval.pt"
    out_path:       str   = "data/models/tgn_supervised.pt"

    # Backbone hyper-params (match SSLConfig defaults so the comparison is
    # against an architecturally identical model).
    memory_dim:     int   = 100
    time_dim:       int   = 100
    embedding_dim:  int   = 100
    n_neighbors:    int   = 10
    n_heads:        int   = 2
    dropout:        float = 0.1

    # Head hyper-params (match LMConfig).
    head_hidden:    int   = 128
    head_dropout:   float = 0.2

    # Optimisation.
    batch_size:     int   = 200
    lr:             float = 1e-4
    n_epochs:       int   = 10
    seed:           int   = 42
    device:         str   = "cuda" if torch.cuda.is_available() else "cpu"


# ----------------------------------------------------------------- training

def _stream_epoch(*, memory, embedder, lm_head, neighbor_loader,
                   data: TemporalData, loader: TemporalDataLoader,
                   optimizer, loss_fn, device, assoc: Tensor,
                   train: bool):
    """One streaming epoch with backbone+head jointly trained (or eval'd).

    Mirrors the protocol used by pretrain_ssl/finetune_lm so the metric
    output is comparable. The key difference: gradients flow through the
    backbone here.
    """
    if train:
        memory.train(); embedder.train(); lm_head.train()
    else:
        memory.eval(); embedder.eval(); lm_head.eval()
    memory.reset_state()
    neighbor_loader.reset_state()

    total_loss      = 0.0
    total_examples  = 0
    all_scores: list[Tensor] = []
    all_labels: list[Tensor] = []

    for batch in loader:
        batch = batch.to(device)
        src, dst, t, msg, y = batch.src, batch.dst, batch.t, batch.msg, batch.y

        # 1) Gather historical neighborhood for (src ∪ dst).
        n_id = torch.cat([src, dst]).unique()
        n_id, edge_index, e_id = neighbor_loader(n_id)
        assoc[n_id] = torch.arange(n_id.size(0), device=device)

        # 2) Backbone forward — gradients flow through here in train mode.
        z, last_update = memory(n_id)
        z = embedder(
            z, last_update, edge_index,
            t=data.t[e_id].to(device),
            msg=data.msg[e_id].to(device),
        )
        z_src = z[assoc[src]]
        z_dst = z[assoc[dst]]

        # 3) Head prediction.
        logits = lm_head(z_src, z_dst, msg)

        # 4) Supervised BCE on LM-vs-benign (mask recon).
        mask = (y != 1)
        if mask.any():
            target = (y[mask] == 2).float()
            logits_eff = logits[mask]
            loss = loss_fn(logits_eff, target)
            if train:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            total_loss += loss.item() * logits_eff.size(0)
            total_examples += logits_eff.size(0)
            all_scores.append(torch.sigmoid(logits_eff).detach().cpu())
            all_labels.append(target.detach().cpu())

        # 5) Stream memory state forward on ALL events — must match the
        #    inference-time protocol regardless of label.
        #    Detach before the next batch's autograd graph (BPTT not used).
        with torch.no_grad():
            memory.update_state(src, dst, t, msg)
            neighbor_loader.insert(src, dst)
        memory.detach()

    scores = torch.cat(all_scores) if all_scores else torch.zeros(0)
    labels = torch.cat(all_labels) if all_labels else torch.zeros(0)
    return {
        "loss":       total_loss / max(total_examples, 1),
        "n_examples": total_examples,
        "scores":     scores,
        "labels":     labels,
    }


# ----------------------------------------------------------------- entry

def run(cfg: SupervisedConfig | None = None) -> Path:
    cfg = cfg or SupervisedConfig()
    torch.manual_seed(cfg.seed)
    device = torch.device(cfg.device)
    print(f"[supervised] device={device}")

    train_blob = torch.load(cfg.train_path, weights_only=False, map_location="cpu")
    eval_blob  = torch.load(cfg.eval_path,  weights_only=False, map_location="cpu")
    n_nodes       = int(train_blob["n_nodes"])
    edge_feat_dim = int(train_blob["edge_feat_dim"])
    n_events      = int(train_blob["src_ids"].numel())
    print(f"[supervised] data: {n_events} events, {n_nodes} nodes, "
          f"edge_feat_dim={edge_feat_dim}")

    # Class-imbalance weight (same convention as finetune_lm.py).
    y = train_blob["labels"]
    pos = int((y == 2).sum())
    neg = int((y == 0).sum())
    pos_weight = max(neg / max(pos, 1), 1.0)
    print(f"[supervised] train: pos={pos} neg={neg} pos_weight={pos_weight:.1f}")

    train_data = _make_temporal_data(train_blob).to(device)
    eval_data  = _make_temporal_data(eval_blob).to(device)
    train_loader = TemporalDataLoader(train_data, batch_size=cfg.batch_size)
    eval_loader  = TemporalDataLoader(eval_data,  batch_size=cfg.batch_size)

    # --- backbone from scratch (no SSL checkpoint) ---
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
        time_enc=memory.time_enc,
        n_heads=cfg.n_heads,
        dropout=cfg.dropout,
    ).to(device)
    lm_head = LMClassifierHead(
        embedding_dim=cfg.embedding_dim,
        edge_feat_dim=edge_feat_dim,
        hidden=cfg.head_hidden,
        dropout=cfg.head_dropout,
    ).to(device)

    neighbor_loader = LastNeighborLoader(
        num_nodes=n_nodes, size=cfg.n_neighbors, device=device,
    )

    # De-duplicate parameters (memory.time_enc is reused by embedder).
    seen: set[int] = set()
    params: list = []
    for m in (memory, embedder, lm_head):
        for p in m.parameters():
            if id(p) in seen:
                continue
            seen.add(id(p))
            params.append(p)
    optimizer = torch.optim.Adam(params, lr=cfg.lr)
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
        print(f"[supervised] ep{epoch:2d}/{cfg.n_epochs}  "
              f"loss={tr['loss']:.4f}  AUC={m_tr['auc_roc']:.3f}  "
              f"AP={m_tr['auc_pr']:.3f}  "
              f"rec@10%fpr={m_tr['recall_at_10pct_fpr']:.3f}  "
              f"({dt:.1f}s)")
        history.append({"epoch": epoch, "split": "train", **m_tr,
                        "loss": tr["loss"], "n_examples": tr["n_examples"]})

    # Final eval pass.
    ev = _stream_epoch(
        memory=memory, embedder=embedder, lm_head=lm_head,
        neighbor_loader=neighbor_loader,
        data=eval_data, loader=eval_loader,
        optimizer=optimizer, loss_fn=loss_fn,
        device=device, assoc=assoc, train=False,
    )
    m_ev = _compute_metrics(ev["scores"], ev["labels"])
    print(f"[supervised] EVAL  loss={ev['loss']:.4f}  "
          f"AUC={m_ev['auc_roc']:.3f}  AP={m_ev['auc_pr']:.3f}  "
          f"rec@1%fpr={m_ev['recall_at_1pct_fpr']:.3f}  "
          f"rec@10%fpr={m_ev['recall_at_10pct_fpr']:.3f}")
    history.append({"epoch": cfg.n_epochs, "split": "eval", **m_ev,
                    "loss": ev["loss"], "n_examples": ev["n_examples"]})

    out_path = Path(cfg.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "memory":        memory.state_dict(),
        "embedder":      embedder.state_dict(),
        "lm_head":       lm_head.state_dict(),
        "config":        asdict(cfg),
        "history":       history,
        "n_nodes":       n_nodes,
        "edge_feat_dim": edge_feat_dim,
        "regime":        "fully_supervised",
    }, out_path)
    print(f"[supervised] saved -> {out_path}  "
          f"({out_path.stat().st_size/1e6:.2f} MB)")
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train",  default="data/datasets/train.pt")
    ap.add_argument("--eval",   default="data/datasets/eval.pt")
    ap.add_argument("--out",    default="data/models/tgn_supervised.pt")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch",  type=int, default=200)
    ap.add_argument("--lr",     type=float, default=1e-4)
    args = ap.parse_args()
    run(SupervisedConfig(
        train_path=args.train, eval_path=args.eval, out_path=args.out,
        n_epochs=args.epochs, batch_size=args.batch, lr=args.lr,
    ))
