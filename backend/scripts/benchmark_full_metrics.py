"""
Re-runs eval on every existing LM checkpoint and dumps the full metric
suite (AUC-ROC, AUC-PR, F1, FPR, FNR at best-F1 threshold) for both
the semi-supervised (frozen-SSL + head) and the fully-supervised regime.

Usage:
    python scripts/benchmark_full_metrics.py
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import torch
from torch_geometric.loader import TemporalDataLoader
from torch_geometric.nn.models.tgn import (
    TGNMemory, LastNeighborLoader, IdentityMessage, LastAggregator,
)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from lated.pipelines.offline.pretrain_ssl import (
    GraphAttentionEmbedding, _make_temporal_data,
)
from lated.pipelines.offline.finetune_lm import LMClassifierHead

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

CONFIGS = [
    ("1: no-aug (default)",   "tgn_lm_head.pt",        "tgn_supervised.pt",        "tgn_backbone.pt"),
    ("2: aug (default cfg)",  "tgn_lm_head_aug.pt",    "tgn_supervised_aug.pt",    "tgn_backbone_aug.pt"),
    ("3: mult=2, noise=0.15", "tgn_lm_head_m2_n015.pt","tgn_supervised_m2_n015.pt","tgn_backbone_m2_n015.pt"),
    ("4: mult=2, noise=0.30", "tgn_lm_head_m2_n030.pt","tgn_supervised_m2_n030.pt","tgn_backbone_m2_n030.pt"),
    ("5: mult=5, noise=0.15", "tgn_lm_head_m5_n015.pt","tgn_supervised_m5_n015.pt","tgn_backbone_m5_n015.pt"),
    ("6: mult=5, noise=0.30", "tgn_lm_head_m5_n030.pt","tgn_supervised_m5_n030.pt","tgn_backbone_m5_n030.pt"),
]

MODELS_DIR = Path("data/models")
EVAL_PATH  = Path("data/datasets/eval.pt")


def _load_backbone(ckpt_path: Path, n_nodes: int, edge_feat_dim: int):
    ckpt = torch.load(ckpt_path, weights_only=False, map_location=DEVICE)
    cfg  = ckpt["config"]
    memory = TGNMemory(
        num_nodes=n_nodes, raw_msg_dim=edge_feat_dim,
        memory_dim=cfg["memory_dim"], time_dim=cfg["time_dim"],
        message_module=IdentityMessage(edge_feat_dim, cfg["memory_dim"], cfg["time_dim"]),
        aggregator_module=LastAggregator(),
    ).to(DEVICE)
    memory.load_state_dict(ckpt["memory"])
    embedder = GraphAttentionEmbedding(
        in_channels=cfg["memory_dim"], out_channels=cfg["embedding_dim"],
        msg_dim=edge_feat_dim, time_enc=memory.time_enc,
        n_heads=cfg["n_heads"], dropout=cfg["dropout"],
    ).to(DEVICE)
    embedder.load_state_dict(ckpt["embedder"])
    return memory, embedder, cfg


def _build_supervised(ckpt_path: Path, n_nodes: int, edge_feat_dim: int):
    """Supervised checkpoint contains memory+embedder+head in one blob."""
    ckpt = torch.load(ckpt_path, weights_only=False, map_location=DEVICE)
    cfg = ckpt["config"]
    memory = TGNMemory(
        num_nodes=n_nodes, raw_msg_dim=edge_feat_dim,
        memory_dim=cfg["memory_dim"], time_dim=cfg["time_dim"],
        message_module=IdentityMessage(edge_feat_dim, cfg["memory_dim"], cfg["time_dim"]),
        aggregator_module=LastAggregator(),
    ).to(DEVICE)
    memory.load_state_dict(ckpt["memory"])
    embedder = GraphAttentionEmbedding(
        in_channels=cfg["memory_dim"], out_channels=cfg["embedding_dim"],
        msg_dim=edge_feat_dim, time_enc=memory.time_enc,
        n_heads=cfg["n_heads"], dropout=cfg["dropout"],
    ).to(DEVICE)
    embedder.load_state_dict(ckpt["embedder"])
    head = LMClassifierHead(
        embedding_dim=cfg["embedding_dim"], edge_feat_dim=edge_feat_dim,
        hidden=cfg["head_hidden"], dropout=cfg["head_dropout"],
    ).to(DEVICE)
    head.load_state_dict(ckpt["lm_head"])
    return memory, embedder, head, cfg


def _build_semi(head_ckpt_path: Path, backbone_ckpt_path: Path,
                n_nodes: int, edge_feat_dim: int):
    """Semi-supervised: load SSL backbone + LM head separately."""
    memory, embedder, bcfg = _load_backbone(backbone_ckpt_path, n_nodes, edge_feat_dim)
    head_ckpt = torch.load(head_ckpt_path, weights_only=False, map_location=DEVICE)
    hcfg = head_ckpt["config"]
    head = LMClassifierHead(
        embedding_dim=bcfg["embedding_dim"], edge_feat_dim=edge_feat_dim,
        hidden=hcfg["hidden"], dropout=hcfg["dropout"],
    ).to(DEVICE)
    head.load_state_dict(head_ckpt["lm_head"])
    return memory, embedder, head, bcfg


@torch.no_grad()
def _stream_eval(memory, embedder, head, data, loader, n_nodes, n_neighbors):
    neighbor_loader = LastNeighborLoader(num_nodes=n_nodes, size=n_neighbors, device=DEVICE)
    assoc = torch.empty(n_nodes, dtype=torch.long, device=DEVICE)
    memory.eval(); embedder.eval(); head.eval()
    memory.reset_state(); neighbor_loader.reset_state()
    all_scores, all_labels = [], []
    for batch in loader:
        batch = batch.to(DEVICE)
        src, dst, t, msg, y = batch.src, batch.dst, batch.t, batch.msg, batch.y
        n_id = torch.cat([src, dst]).unique()
        n_id, edge_index, e_id = neighbor_loader(n_id)
        assoc[n_id] = torch.arange(n_id.size(0), device=DEVICE)
        z, last_update = memory(n_id)
        z = embedder(z, last_update, edge_index,
                     t=data.t[e_id].to(DEVICE), msg=data.msg[e_id].to(DEVICE))
        logits = head(z[assoc[src]], z[assoc[dst]], msg)
        # Binarise labels: shards on disk are still 3-class {0,1,2};
        # treat label==2 (LM) as the positive, everything else negative.
        y_bin = (y == 2).float()
        all_scores.append(torch.sigmoid(logits).cpu())
        all_labels.append(y_bin.cpu())
        memory.update_state(src, dst, t, msg)
        neighbor_loader.insert(src, dst)
    return torch.cat(all_scores).numpy(), torch.cat(all_labels).numpy()


def _metrics(scores: np.ndarray, labels: np.ndarray) -> dict:
    """Full metric set: AUC-ROC, AUC-PR, F1*, FPR*, FNR* at best-F1 threshold."""
    from sklearn.metrics import (
        roc_auc_score, average_precision_score, precision_recall_curve,
        roc_curve, confusion_matrix,
    )
    if labels.sum() == 0 or labels.sum() == len(labels):
        return {k: float("nan") for k in
                ["auc_roc","auc_pr","f1","fpr","fnr","prec","rec","thr"]}
    auc = float(roc_auc_score(labels, scores))
    ap  = float(average_precision_score(labels, scores))
    # Best-F1 threshold from PR curve.
    p, r, thr = precision_recall_curve(labels, scores)
    f1 = 2 * p * r / np.clip(p + r, 1e-12, None)
    best = int(np.nanargmax(f1[:-1])) if len(thr) else 0
    t_best = float(thr[best]) if len(thr) else 0.5
    y_pred = (scores >= t_best).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, y_pred, labels=[0,1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else float("nan")
    fnr = fn / (fn + tp) if (fn + tp) > 0 else float("nan")
    return {"auc_roc": auc, "auc_pr": ap, "f1": float(f1[best]),
            "fpr": float(fpr), "fnr": float(fnr),
            "prec": float(p[best]), "rec": float(r[best]),
            "thr": t_best}


def main():
    eval_blob = torch.load(EVAL_PATH, weights_only=False, map_location="cpu")
    n_nodes = int(eval_blob["n_nodes"])
    edge_feat_dim = int(eval_blob["edge_feat_dim"])
    data = _make_temporal_data(eval_blob).to(DEVICE)
    loader = TemporalDataLoader(data, batch_size=200)
    print(f"[bench] device={DEVICE}  eval flows={int(eval_blob['ts'].numel())}  "
          f"positives={int((eval_blob['labels']==2).sum())}")

    rows_b, rows_c = [], []
    for name, head_ck, sup_ck, ssl_ck in CONFIGS:
        # B. Semi-supervised
        try:
            mem, emb, head, bcfg = _build_semi(MODELS_DIR/head_ck, MODELS_DIR/ssl_ck,
                                                n_nodes, edge_feat_dim)
            s, y = _stream_eval(mem, emb, head, data, loader, n_nodes, bcfg["n_neighbors"])
            m = _metrics(s, y)
            print(f"[B] {name}: AUC={m['auc_roc']:.3f} AP={m['auc_pr']:.3f} "
                  f"F1={m['f1']:.3f} FPR={m['fpr']:.3f} FNR={m['fnr']:.3f}")
            rows_b.append({"hp": name, **m})
        except Exception as e:
            print(f"[B] {name}: FAILED ({e})")
            rows_b.append({"hp": name, "error": str(e)})

        # C. Fully supervised
        try:
            mem, emb, head, scfg = _build_supervised(MODELS_DIR/sup_ck, n_nodes, edge_feat_dim)
            s, y = _stream_eval(mem, emb, head, data, loader, n_nodes, scfg["n_neighbors"])
            m = _metrics(s, y)
            print(f"[C] {name}: AUC={m['auc_roc']:.3f} AP={m['auc_pr']:.3f} "
                  f"F1={m['f1']:.3f} FPR={m['fpr']:.3f} FNR={m['fnr']:.3f}")
            rows_c.append({"hp": name, **m})
        except Exception as e:
            print(f"[C] {name}: FAILED ({e})")
            rows_c.append({"hp": name, "error": str(e)})

    out = Path("data/reports/benchmark_full_metrics.json")
    out.write_text(json.dumps({"semi_supervised": rows_b,
                                "fully_supervised": rows_c}, indent=2))
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()
