# =============================================================================
# lated.pipelines.offline.compare_training — Compare LM training regimes
# =============================================================================
#
# Trains (or loads) the three LM detection regimes and prints a side-by-side
# eval-set metric table:
#
#     A. SSL only           — pretrain_ssl.py
#                             (the LM signal here is the SSL link-predictor
#                              applied as anomaly score: low link-likelihood
#                              ⇒ anomalous edge. Reported for completeness.)
#     B. Semi-supervised    — pretrain_ssl.py  ➜  finetune_lm.py
#                             (frozen SSL backbone + supervised head, weak
#                              labels from weak_labeler.py)
#     C. Fully supervised   — supervised_lm.py
#                             (TGN + head trained end-to-end on LM labels)
#
# All three regimes share architecture, dataset, label convention, batch
# size, and seed, so the eval-set numbers are directly comparable.
#
# USAGE
# -----
#   # Train every regime and emit the report:
#   python -m lated.pipelines.offline.compare_training --train-all
#
#   # Skip retraining if checkpoints already exist:
#   python -m lated.pipelines.offline.compare_training
#
# OUTPUT
# ------
#   stdout                                — Markdown comparison table
#   backend/data/reports/training_compare.json — Machine-readable metrics
# =============================================================================

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import torch


# --------------------------------------------------------- regime runners

def _run_ssl(train_path: str, out_path: str, epochs: int) -> Path:
    from lated.pipelines.offline.pretrain_ssl import run, SSLConfig
    return run(SSLConfig(
        train_path=train_path, out_path=out_path, n_epochs=epochs,
    ))


def _run_semi(train_path: str, eval_path: str, backbone_path: str,
              out_path: str, epochs: int) -> Path:
    from lated.pipelines.offline.finetune_lm import run, LMConfig
    return run(LMConfig(
        train_path=train_path, eval_path=eval_path,
        backbone_path=backbone_path, out_path=out_path, n_epochs=epochs,
    ))


def _run_supervised(train_path: str, eval_path: str, out_path: str,
                     epochs: int) -> Path:
    from lated.pipelines.offline.supervised_lm import run, SupervisedConfig
    return run(SupervisedConfig(
        train_path=train_path, eval_path=eval_path,
        out_path=out_path, n_epochs=epochs,
    ))


# --------------------------------------------------------- metric extraction

def _eval_metrics_from_ckpt(ckpt_path: Path) -> dict:
    """Pull the final eval-split entry from a checkpoint's training history."""
    blob = torch.load(ckpt_path, weights_only=False, map_location="cpu")
    history = blob.get("history", [])
    for entry in reversed(history):
        if entry.get("split") == "eval":
            return entry
    # SSL checkpoint has no eval split — return train-loss only.
    if history:
        last = history[-1]
        return {"loss": last.get("loss"), "auc_roc": float("nan"),
                "auc_pr": float("nan"),
                "recall_at_1pct_fpr": float("nan"),
                "recall_at_10pct_fpr": float("nan"),
                "n_examples": last.get("n_loss_examples", 0)}
    return {}


def _fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        if x != x:                # NaN
            return "—"
        return f"{x:.3f}"
    return str(x)


def _print_table(rows: list[dict]) -> str:
    cols = ["regime", "auc_roc", "auc_pr",
            "recall_at_1pct_fpr", "recall_at_10pct_fpr", "loss"]
    headers = ["Regime", "AUC-ROC", "AUC-PR", "Rec@1%FPR",
               "Rec@10%FPR", "Eval loss"]
    widths = [max(len(h), max(len(_fmt(r.get(c))) for r in rows))
              for h, c in zip(headers, cols)]
    bar = "| " + " | ".join("-" * w for w in widths) + " |"
    hdr = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    out_lines = [hdr, bar]
    for r in rows:
        cells = [_fmt(r.get(c)).ljust(w) for c, w in zip(cols, widths)]
        out_lines.append("| " + " | ".join(cells) + " |")
    table = "\n".join(out_lines)
    print(table)
    return table


# --------------------------------------------------------- entry

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train",    default="data/datasets/train.pt")
    ap.add_argument("--eval",     default="data/datasets/eval.pt")
    ap.add_argument("--backbone", default="data/models/tgn_backbone.pt")
    ap.add_argument("--head",     default="data/models/tgn_lm_head.pt")
    ap.add_argument("--supervised", default="data/models/tgn_supervised.pt")
    ap.add_argument("--report",   default="data/reports/training_compare.json")
    ap.add_argument("--epochs-ssl",        type=int, default=5)
    ap.add_argument("--epochs-semi",       type=int, default=10)
    ap.add_argument("--epochs-supervised", type=int, default=10)
    ap.add_argument("--train-all", action="store_true",
                    help="Retrain every regime even if checkpoints exist.")
    args = ap.parse_args()

    paths = {
        "backbone":   Path(args.backbone),
        "head":       Path(args.head),
        "supervised": Path(args.supervised),
    }

    # --- A. SSL backbone -------------------------------------------------
    if args.train_all or not paths["backbone"].exists():
        _run_ssl(args.train, str(paths["backbone"]), args.epochs_ssl)

    # --- B. Semi-supervised head ----------------------------------------
    if args.train_all or not paths["head"].exists():
        _run_semi(args.train, args.eval, str(paths["backbone"]),
                  str(paths["head"]), args.epochs_semi)

    # --- C. Fully supervised end-to-end ---------------------------------
    if args.train_all or not paths["supervised"].exists():
        _run_supervised(args.train, args.eval,
                        str(paths["supervised"]), args.epochs_supervised)

    # --- Gather metrics --------------------------------------------------
    rows = [
        {"regime": "A. SSL only (link-pred)",
         **_eval_metrics_from_ckpt(paths["backbone"])},
        {"regime": "B. Semi-supervised (SSL + head)",
         **_eval_metrics_from_ckpt(paths["head"])},
        {"regime": "C. Fully supervised (end-to-end)",
         **_eval_metrics_from_ckpt(paths["supervised"])},
    ]

    print("\n=== LM training-regime comparison (eval split) ===")
    table = _print_table(rows)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(
        {"table": table, "rows": rows}, indent=2, default=str,
    ))
    print(f"\nSaved -> {report_path}")


if __name__ == "__main__":
    main()
