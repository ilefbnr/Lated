# =============================================================================
# lated.tools.compare_tgn_models — TGN checkpoint inventory + comparison
# =============================================================================
#
# Prints a table comparing every .pt file in backend/data/models/ using the
# metrics stored in their `history` field at training time (so this is fast,
# no inference needed). Sorted by AUC-ROC descending.
#
# Usage
# -----
#   python -m lated.tools.compare_tgn_models
#   python -m lated.tools.compare_tgn_models --models-dir /custom/path
#   python -m lated.tools.compare_tgn_models --best        # print best path only
#
# Output columns
# --------------
#   model file       AUC-ROC   AUC-PR   R@1%FPR   R@10%FPR   epochs   notes
# =============================================================================

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import torch


@dataclass
class ModelEntry:
    path: Path
    family: str
    n_epochs: int
    auc_roc: float | None
    auc_pr: float | None
    recall_at_1pct_fpr: float | None
    recall_at_10pct_fpr: float | None
    loss: float | None
    notes: str

    def usable(self) -> bool:
        return self.family in {"backbone", "supervised", "lm_head"}


def _classify(ckpt: dict) -> str:
    has_mem = "memory" in ckpt
    has_emb = "embedder" in ckpt
    has_pred = "predictor" in ckpt
    has_lm = "lm_head" in ckpt
    if has_mem and has_emb and has_lm:
        return "supervised"
    if has_mem and has_emb and has_pred:
        return "backbone"
    if has_lm and not has_mem:
        return "lm_head"
    return "unknown"


def _last_eval_metrics(history: list) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    """Find the latest entry that carries eval metrics. Returns (roc, pr, r1, r10, loss)."""
    for entry in reversed(history or []):
        if not isinstance(entry, dict):
            continue
        if "auc_roc" in entry:
            return (
                entry.get("auc_roc"),
                entry.get("auc_pr"),
                entry.get("recall_at_1pct_fpr"),
                entry.get("recall_at_10pct_fpr"),
                entry.get("loss"),
            )
    if history:
        last = history[-1] if isinstance(history[-1], dict) else {}
        return (None, None, None, None, last.get("loss"))
    return (None, None, None, None, None)


def scan_models(models_dir: Path) -> list[ModelEntry]:
    entries: list[ModelEntry] = []
    for path in sorted(models_dir.glob("*.pt")):
        try:
            ckpt = torch.load(path, map_location="cpu", weights_only=False)
        except Exception as exc:
            entries.append(ModelEntry(
                path=path, family="unknown", n_epochs=0,
                auc_roc=None, auc_pr=None,
                recall_at_1pct_fpr=None, recall_at_10pct_fpr=None,
                loss=None, notes=f"load_error: {type(exc).__name__}",
            ))
            continue
        if not isinstance(ckpt, dict):
            continue
        family = _classify(ckpt)
        history = ckpt.get("history", []) or []
        n_epochs = max((e.get("epoch", 0) for e in history if isinstance(e, dict)), default=0)
        roc, pr, r1, r10, loss = _last_eval_metrics(history)
        notes = ""
        if family == "lm_head":
            notes = "needs backbone"
        elif family == "backbone" and roc is None:
            notes = "SSL (no eval metrics, link prediction)"
        entries.append(ModelEntry(
            path=path, family=family, n_epochs=int(n_epochs),
            auc_roc=roc, auc_pr=pr,
            recall_at_1pct_fpr=r1, recall_at_10pct_fpr=r10,
            loss=loss, notes=notes,
        ))
    return entries


def rank(entries: list[ModelEntry]) -> list[ModelEntry]:
    """Sort by (has AUC-ROC desc, AUC-ROC desc, AUC-PR desc, family preference)."""
    family_pref = {"supervised": 0, "lm_head": 1, "backbone": 2, "unknown": 3}
    return sorted(
        entries,
        key=lambda e: (
            0 if e.auc_roc is not None else 1,
            -(e.auc_roc or 0.0),
            -(e.auc_pr or 0.0),
            family_pref.get(e.family, 9),
            e.path.name,
        ),
    )


def _fmt(value: float | None, places: int = 3) -> str:
    return f"{value:.{places}f}" if isinstance(value, (int, float)) else "—"


def print_table(entries: list[ModelEntry]) -> None:
    header = f"{'model':38} {'family':11} {'epochs':>6} {'AUC-ROC':>8} {'AUC-PR':>8} {'R@1%':>6} {'R@10%':>6}  notes"
    print(header)
    print("-" * len(header))
    for e in rank(entries):
        print(
            f"{e.path.name:38} {e.family:11} {e.n_epochs:>6} "
            f"{_fmt(e.auc_roc):>8} {_fmt(e.auc_pr):>8} "
            f"{_fmt(e.recall_at_1pct_fpr, 2):>6} {_fmt(e.recall_at_10pct_fpr, 2):>6}  {e.notes}"
        )


def best_entry(entries: list[ModelEntry]) -> ModelEntry | None:
    ranked = rank([e for e in entries if e.usable() and e.auc_roc is not None])
    return ranked[0] if ranked else None


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare TGN checkpoints.")
    ap.add_argument(
        "--models-dir",
        default=str(Path(__file__).resolve().parents[4] / "data" / "models"),
        help="Directory containing .pt checkpoints",
    )
    ap.add_argument("--best", action="store_true", help="Print only the best model's path.")
    args = ap.parse_args()

    models_dir = Path(args.models_dir)
    if not models_dir.is_dir():
        raise SystemExit(f"Not a directory: {models_dir}")
    entries = scan_models(models_dir)
    if not entries:
        raise SystemExit(f"No .pt files under {models_dir}")

    if args.best:
        best = best_entry(entries)
        if best is None:
            raise SystemExit("No model with eval metrics found.")
        print(best.path)
        return

    print_table(entries)
    best = best_entry(entries)
    if best is not None:
        print()
        print(f"Best by AUC-ROC: {best.path.name}  ({best.family}, AUC-ROC={best.auc_roc:.3f})")
        print()
        print("To use it:")
        print(f"  export LATED_TGN_MODEL={best.path}")
        print(f"  export LATED_DEV_MODE=1")
        print()
        print("Or set in backend/config/settings.yaml:")
        print("  detection:")
        print("    tgnn:")
        rel = best.path.relative_to(best.path.parents[2]) if best.path.parents[2] in best.path.parents else best.path
        print(f"      model_path: {rel}")


if __name__ == "__main__":
    main()
