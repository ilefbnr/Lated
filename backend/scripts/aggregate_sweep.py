"""
Aggregate the multi-seed sweep results into a paper-style table:
one row per HP set, columns = Max/Avg AUC-ROC, Max/Avg AP (across seeds),
plus PR-AUC, F1, FPR, FNR (mean ± std across seeds).

Usage:
    python scripts/aggregate_sweep.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np


REPORT = Path("data/reports/sweep_results.json")


def fmt(x, n=4):
    if x is None: return "  —   "
    if isinstance(x, float) and x != x: return "  —   "
    return f"{x:.{n}f}"


def fmt_mean_std(vals, n=3):
    arr = np.array([v for v in vals if v == v])
    if arr.size == 0: return "    —    "
    if arr.size == 1: return f"{arr[0]:.{n}f}"
    return f"{arr.mean():.{n}f}±{arr.std(ddof=0):.{n}f}"


def main():
    rows = json.loads(REPORT.read_text())

    # group by hp_id
    by_hp = defaultdict(list)
    for r in rows:
        by_hp[r["hp_id"]].append(r)

    cols = ["HP set", "Max AUC-ROC", "Avg AUC-ROC", "Max AP", "Avg AP",
            "PR-AUC", "F1", "FPR", "FNR"]

    table = []
    for hp_id in sorted(by_hp):
        runs = by_hp[hp_id]
        name = runs[0]["hp_name"]
        aucs = [r["auc_roc"] for r in runs]
        aps  = [r["auc_pr"]  for r in runs]
        f1s  = [r["f1"]      for r in runs]
        fprs = [r["fpr"]     for r in runs]
        fnrs = [r["fnr"]     for r in runs]
        row = [
            f"{hp_id}: {name}",
            fmt(max(aucs)),
            fmt_mean_std(aucs),
            fmt(max(aps)),
            fmt_mean_std(aps),
            fmt_mean_std(aps),         # PR-AUC ≡ AP on eval set
            fmt_mean_std(f1s),
            fmt_mean_std(fprs),
            fmt_mean_std(fnrs),
        ]
        table.append(row)

    # star the best cell per column (best = max except FPR/FNR which is min)
    metric_cols = [1, 2, 3, 4, 5, 6, 7, 8]
    lower_better = {7, 8}
    def parse(s):
        s = s.strip().split("±")[0].strip("*")
        try: return float(s)
        except: return None

    for j in metric_cols:
        vals = [parse(r[j]) for r in table]
        idx_valid = [i for i,v in enumerate(vals) if v is not None]
        if not idx_valid: continue
        if j in lower_better:
            best = min(idx_valid, key=lambda i: vals[i])
        else:
            best = max(idx_valid, key=lambda i: vals[i])
        table[best][j] = table[best][j].rstrip() + "*"

    widths = [max(len(c), max(len(r[i]) for r in table)) for i,c in enumerate(cols)]
    print("| " + " | ".join(c.ljust(w) for c,w in zip(cols, widths)) + " |")
    print("|" + "|".join("-"*(w+2) for w in widths) + "|")
    for r in table:
        print("| " + " | ".join(c.ljust(w) for c,w in zip(r, widths)) + " |")

    print(f"\n{len(rows)} runs total, {len(by_hp)} HP sets, "
          f"{len(rows)//len(by_hp)} seeds/set")


if __name__ == "__main__":
    main()
