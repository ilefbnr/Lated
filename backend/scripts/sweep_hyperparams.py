"""
Multi-seed hyperparameter sweep for the fully-supervised TGN regime.

Runs N seeds per HP set, computes the full metric suite, and writes a
JSON report with per-run results that the aggregation script consumes.

Existing checkpoints (sets 1-6 at seed=42) are reused.

Usage:
    python scripts/sweep_hyperparams.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch_geometric.loader import TemporalDataLoader
from torch_geometric.nn.models.tgn import (
    TGNMemory, LastNeighborLoader, IdentityMessage, LastAggregator,
)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from lated.pipelines.offline.supervised_lm import run as run_supervised, SupervisedConfig
from lated.pipelines.offline.pretrain_ssl import (
    GraphAttentionEmbedding, _make_temporal_data,
)
from lated.pipelines.offline.finetune_lm import LMClassifierHead

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODELS_DIR = Path("data/models")
SHARDS = {
    "no-aug":  ("data/datasets/train.pt",        "data/datasets/eval.pt"),
    "aug":     ("data/datasets/train_aug.pt",    "data/datasets/eval.pt"),
    "m2n015":  ("data/datasets/train_m2_n015.pt","data/datasets/eval.pt"),
    "m2n030":  ("data/datasets/train_m2_n030.pt","data/datasets/eval.pt"),
    "m5n015":  ("data/datasets/train_m5_n015.pt","data/datasets/eval.pt"),
    "m5n030":  ("data/datasets/train_m5_n030.pt","data/datasets/eval.pt"),
}

# HP set definitions: (id, display name, shard_key, override dict)
HP_SETS = [
    (1, "no-aug",        "no-aug", {}),
    (2, "aug-default",   "aug",    {}),
    (3, "m=2, n=0.15",   "m2n015", {}),
    (4, "m=2, n=0.30",   "m2n030", {}),
    (5, "m=5, n=0.15",   "m5n015", {}),
    (6, "m=5, n=0.30",   "m5n030", {}),
    # --- new variants, share aug=m2n015 (best from sets 1-6 on eval PR-AUC) ---
    (7, "wide-head",     "m2n015", {"head_hidden": 256, "head_dropout": 0.3}),
    (8, "agg-lr",        "m2n015", {"lr": 1e-3, "n_epochs": 20}),
    (9, "deep-backbone", "m2n015", {"memory_dim": 200, "n_neighbors": 20,
                                     "embedding_dim": 200}),
]

SEEDS = [42, 7, 123]

# Existing checkpoints to reuse: only sets 1-6 at seed=42 with default params.
EXISTING = {
    (1, 42): "tgn_supervised.pt",
    (2, 42): "tgn_supervised_aug.pt",
    (3, 42): "tgn_supervised_m2_n015.pt",
    (4, 42): "tgn_supervised_m2_n030.pt",
    (5, 42): "tgn_supervised_m5_n015.pt",
    (6, 42): "tgn_supervised_m5_n030.pt",
}


# ----------------------------------------------------------- eval / metrics

def _load_and_eval(ckpt_path: Path, eval_path: Path) -> dict:
    """Load checkpoint, run one eval pass, compute full metric suite."""
    blob = torch.load(ckpt_path, weights_only=False, map_location=DEVICE)
    cfg = blob["config"]
    n_nodes = int(blob["n_nodes"])
    edge_feat_dim = int(blob["edge_feat_dim"])

    memory = TGNMemory(
        num_nodes=n_nodes, raw_msg_dim=edge_feat_dim,
        memory_dim=cfg["memory_dim"], time_dim=cfg["time_dim"],
        message_module=IdentityMessage(edge_feat_dim, cfg["memory_dim"], cfg["time_dim"]),
        aggregator_module=LastAggregator(),
    ).to(DEVICE)
    memory.load_state_dict(blob["memory"])
    embedder = GraphAttentionEmbedding(
        in_channels=cfg["memory_dim"], out_channels=cfg["embedding_dim"],
        msg_dim=edge_feat_dim, time_enc=memory.time_enc,
        n_heads=cfg["n_heads"], dropout=cfg["dropout"],
    ).to(DEVICE)
    embedder.load_state_dict(blob["embedder"])
    head = LMClassifierHead(
        embedding_dim=cfg["embedding_dim"], edge_feat_dim=edge_feat_dim,
        hidden=cfg["head_hidden"], dropout=cfg["head_dropout"],
    ).to(DEVICE)
    head.load_state_dict(blob["lm_head"])

    eval_blob = torch.load(eval_path, weights_only=False, map_location="cpu")
    data = _make_temporal_data(eval_blob).to(DEVICE)
    loader = TemporalDataLoader(data, batch_size=200)
    neighbor_loader = LastNeighborLoader(num_nodes=n_nodes,
                                          size=cfg["n_neighbors"], device=DEVICE)
    assoc = torch.empty(n_nodes, dtype=torch.long, device=DEVICE)

    memory.eval(); embedder.eval(); head.eval()
    memory.reset_state(); neighbor_loader.reset_state()
    all_s, all_y = [], []
    with torch.no_grad():
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
            all_s.append(torch.sigmoid(logits).cpu())
            all_y.append(y.float().cpu())
            memory.update_state(src, dst, t, msg)
            neighbor_loader.insert(src, dst)
    s = torch.cat(all_s).numpy()
    y = torch.cat(all_y).numpy()

    from sklearn.metrics import (roc_auc_score, average_precision_score,
                                  precision_recall_curve, confusion_matrix)
    auc = float(roc_auc_score(y, s))
    ap  = float(average_precision_score(y, s))
    p, r, thr = precision_recall_curve(y, s)
    f1 = 2 * p * r / np.clip(p + r, 1e-12, None)
    best = int(np.nanargmax(f1[:-1])) if len(thr) else 0
    t_best = float(thr[best]) if len(thr) else 0.5
    y_pred = (s >= t_best).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, y_pred, labels=[0,1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else float("nan")
    fnr = fn / (fn + tp) if (fn + tp) > 0 else float("nan")

    # Train-epoch max/avg (for the "Max" / "Avg" cols in the paper-style table).
    train_hist = [e for e in blob["history"] if e.get("split") == "train"]
    train_aucs = [e["auc_roc"] for e in train_hist if e["auc_roc"] == e["auc_roc"]]
    train_aps  = [e["auc_pr"]  for e in train_hist if e["auc_pr"]  == e["auc_pr"]]

    return {
        "auc_roc":  auc,
        "auc_pr":   ap,
        "f1":       float(f1[best]),
        "fpr":      float(fpr),
        "fnr":      float(fnr),
        "thr":      t_best,
        "train_max_auc": max(train_aucs) if train_aucs else float("nan"),
        "train_avg_auc": float(np.mean(train_aucs)) if train_aucs else float("nan"),
        "train_max_ap":  max(train_aps) if train_aps else float("nan"),
        "train_avg_ap":  float(np.mean(train_aps)) if train_aps else float("nan"),
    }


# ----------------------------------------------------------- main

def main():
    results = []
    t_global = time.time()
    for hp_id, hp_name, shard_key, override in HP_SETS:
        train_path, eval_path = SHARDS[shard_key]
        for seed in SEEDS:
            tag = f"hp{hp_id}_seed{seed}"
            out_ckpt = MODELS_DIR / f"sweep_{tag}.pt"

            # Reuse existing seed=42 checkpoints for sets 1-6 (no overrides).
            existing = EXISTING.get((hp_id, seed))
            if existing and not override:
                ckpt = MODELS_DIR / existing
                print(f"\n[sweep] {tag} ({hp_name}): REUSE {existing}")
            else:
                if out_ckpt.exists():
                    print(f"\n[sweep] {tag} ({hp_name}): cached {out_ckpt.name}")
                else:
                    print(f"\n[sweep] {tag} ({hp_name}) training, override={override}")
                    cfg = SupervisedConfig(
                        train_path=train_path, eval_path=eval_path,
                        out_path=str(out_ckpt), seed=seed, **override,
                    )
                    t0 = time.time()
                    run_supervised(cfg)
                    print(f"[sweep] {tag}: training done ({time.time()-t0:.1f}s)")
                ckpt = out_ckpt

            m = _load_and_eval(ckpt, Path(eval_path))
            print(f"[sweep] {tag}: AUC={m['auc_roc']:.3f} AP={m['auc_pr']:.3f} "
                  f"F1={m['f1']:.3f} FPR={m['fpr']:.3f} FNR={m['fnr']:.3f}")
            results.append({
                "hp_id": hp_id, "hp_name": hp_name, "seed": seed,
                "shard_key": shard_key, "override": override,
                **m,
            })

    out_path = Path("data/reports/sweep_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\n[sweep] done in {time.time()-t_global:.1f}s -> {out_path}")


if __name__ == "__main__":
    main()
