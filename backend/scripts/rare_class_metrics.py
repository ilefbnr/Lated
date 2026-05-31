"""
Rare-class / SOC-oriented evaluation for the original 6 supervised
checkpoints. Computes metrics that matter when positives are <1% of
traffic and analyst review bandwidth is limited.

Output: table to stdout + JSON report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

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
MODELS_DIR = Path("data/models")
EVAL_PATH = Path("data/datasets/eval.pt")

CONFIGS = [
    ("1: no-aug",         "tgn_supervised.pt"),
    ("2: aug-default",    "tgn_supervised_aug.pt"),
    ("3: m=2, n=0.15",    "tgn_supervised_m2_n015.pt"),
    ("4: m=2, n=0.30",    "tgn_supervised_m2_n030.pt"),
    ("5: m=5, n=0.15",    "tgn_supervised_m5_n015.pt"),
    ("6: m=5, n=0.30",    "tgn_supervised_m5_n030.pt"),
]


@torch.no_grad()
def _score(ckpt_path: Path, data, loader, n_nodes, edge_feat_dim) -> tuple[np.ndarray, np.ndarray]:
    blob = torch.load(ckpt_path, weights_only=False, map_location=DEVICE)
    cfg = blob["config"]
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
    neighbor_loader = LastNeighborLoader(num_nodes=n_nodes,
                                          size=cfg["n_neighbors"], device=DEVICE)
    assoc = torch.empty(n_nodes, dtype=torch.long, device=DEVICE)
    memory.eval(); embedder.eval(); head.eval()
    memory.reset_state(); neighbor_loader.reset_state()
    all_s, all_y = [], []
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
    return torch.cat(all_s).numpy(), torch.cat(all_y).numpy()


def _rare_class_metrics(scores: np.ndarray, y: np.ndarray) -> dict:
    """Rare-class + SOC-oriented metrics."""
    from sklearn.metrics import (
        matthews_corrcoef, balanced_accuracy_score, precision_recall_curve,
        roc_curve, fbeta_score, brier_score_loss,
    )

    N = len(y)
    P = int(y.sum())
    N_neg = N - P
    base_rate = P / N

    # ---- Family A: imbalance-robust at best-F1 threshold ------------
    p, r, thr = precision_recall_curve(y, scores)
    f1 = 2 * p * r / np.clip(p + r, 1e-12, None)
    best = int(np.nanargmax(f1[:-1])) if len(thr) else 0
    t_best = float(thr[best]) if len(thr) else 0.5
    y_pred = (scores >= t_best).astype(int)

    tp = int(((y_pred == 1) & (y == 1)).sum())
    fp = int(((y_pred == 1) & (y == 0)).sum())
    fn = int(((y_pred == 0) & (y == 1)).sum())
    tn = int(((y_pred == 0) & (y == 0)).sum())
    tpr = tp / max(P, 1)
    tnr = tn / max(N_neg, 1)

    mcc      = float(matthews_corrcoef(y, y_pred))
    g_mean   = float(np.sqrt(tpr * tnr))
    bal_acc  = float(balanced_accuracy_score(y, y_pred))
    f2       = float(fbeta_score(y, y_pred, beta=2.0, zero_division=0))
    brier    = float(brier_score_loss(y, scores))

    # ---- Family B: fixed alert budget --------------------------------
    fpr, tpr_curve, _ = roc_curve(y, scores)
    def tp_at_fpr(target_fpr):
        idx = np.searchsorted(fpr, target_fpr, side="right") - 1
        if idx < 0: return 0
        return int(round(tpr_curve[idx] * P))
    tp_at_01pct = tp_at_fpr(0.001)
    tp_at_1pct  = tp_at_fpr(0.01)
    tp_at_5pct  = tp_at_fpr(0.05)

    # top-k
    order = np.argsort(-scores)
    def topk_metrics(k):
        idx = order[:k]
        tp_k = int(y[idx].sum())
        return tp_k / k, tp_k / max(P, 1), tp_k
    prec100, rec100, tp100 = topk_metrics(100)
    prec500, rec500, tp500 = topk_metrics(500)

    # Lift@1% = (recall@top1%) / base_rate
    k_1pct = max(int(round(N * 0.01)), 1)
    _, rec_1pct, _ = topk_metrics(k_1pct)
    lift_1pct = rec_1pct / max(base_rate, 1e-12)

    # ---- Family C: ranking quality -----------------------------------
    # rank of LM positives in the descending score order (1 = best).
    rank = np.empty(N, dtype=np.int64)
    rank[order] = np.arange(1, N + 1)
    pos_ranks = rank[y == 1]
    mean_rank   = float(pos_ranks.mean()) if pos_ranks.size else float("nan")
    median_rank = float(np.median(pos_ranks)) if pos_ranks.size else float("nan")

    return {
        # Family A
        "mcc": mcc, "g_mean": g_mean, "bal_acc": bal_acc,
        "f2": f2, "brier": brier,
        # Family B
        "tp@0.1%fpr": tp_at_01pct,
        "tp@1%fpr":   tp_at_1pct,
        "tp@5%fpr":   tp_at_5pct,
        "prec@100": prec100, "rec@100": rec100, "tp@100": tp100,
        "prec@500": prec500, "rec@500": rec500, "tp@500": tp500,
        "lift@1%":  lift_1pct,
        # Family C
        "mean_rank":   mean_rank,
        "median_rank": median_rank,
        # bookkeeping
        "n_pos": P, "n_neg": N_neg, "n_total": N,
        "best_f1_threshold": t_best,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def main():
    eval_blob = torch.load(EVAL_PATH, weights_only=False, map_location="cpu")
    n_nodes = int(eval_blob["n_nodes"])
    edge_feat_dim = int(eval_blob["edge_feat_dim"])
    data = _make_temporal_data(eval_blob).to(DEVICE)
    loader = TemporalDataLoader(data, batch_size=200)
    n_pos = int((eval_blob["labels"] == 1).sum())
    n_tot = int(eval_blob["labels"].numel())
    print(f"[eval] {n_tot} flows, {n_pos} LM positives "
          f"({n_pos/n_tot*100:.2f}%), 1:{n_tot/n_pos:.0f} ratio")

    rows = []
    for name, ckpt in CONFIGS:
        s, y = _score(MODELS_DIR / ckpt, data, loader, n_nodes, edge_feat_dim)
        m = _rare_class_metrics(s, y)
        rows.append({"hp": name, **m})
        print(f"\n{name}: MCC={m['mcc']:.3f} G-mean={m['g_mean']:.3f} "
              f"F2={m['f2']:.3f}  TP@1%FPR={m['tp@1%fpr']}/{n_pos}  "
              f"Prec@100={m['prec@100']:.3f}  Lift@1%={m['lift@1%']:.1f}")

    out = Path("data/reports/rare_class_metrics.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()
