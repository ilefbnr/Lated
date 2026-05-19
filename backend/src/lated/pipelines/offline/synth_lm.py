# =============================================================================
# lated.pipelines.offline.synth_lm — Synthetic LM-positive augmentation
# =============================================================================
#
# PURPOSE
# -------
# PicoDomain has a 1:333 LM-vs-benign imbalance on the train split (575 LM
# positives against 191,750 benigns). The TGN model trains well on this
# imbalance (AUC-ROC 0.94) but recall at strict FPR remains low because the
# positive class is starved of supervision.
#
# This module synthesizes additional LM-positive flows by replicating the
# existing positives with controlled time jitter and feature noise. All
# synthetic events:
#   - reuse a real (src, dst, label) triple from an existing positive,
#   - sit inside the original train time window (no leakage into eval),
#   - perturb only continuous edge-feature channels (one-hot / binary
#     channels are kept verbatim so the LM signature is preserved),
#   - carry label==2 so the rest of the pipeline treats them as LM_ok.
#
# CONTRACT
# --------
# Operates on a materialised train shard (see dataset_builder.py for schema):
#     {src_ids, dst_ids, ts, edge_feat, labels, n_nodes, ip_to_id, edge_feat_dim}
# Returns a new shard with the same schema, sorted chronologically.
#
# SAFETY
# ------
# Must NEVER be applied to the eval shard — that would invalidate every
# metric the comparison report prints.
#
# USAGE
# -----
#   # In-place style (operate on an existing train.pt):
#   python -m lated.pipelines.offline.synth_lm \
#       --in data/datasets/train.pt \
#       --out data/datasets/train_aug.pt \
#       --multiplier 10
#
#   # Programmatic:
#   from lated.pipelines.offline.synth_lm import synthesize, SynthConfig
#   aug_blob = synthesize(train_blob, SynthConfig(multiplier=10))
# =============================================================================

from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import torch


# Continuous-feature column indices in the 47-dim edge_feat vector. Anything
# outside this set is one-hot (port/proto/conn_state) or binary (DCE flags,
# admin_share, ntlm_success) and MUST NOT be perturbed — multiplicative noise
# on a one-hot encoding produces impossible edges.
#   18 = log1p(duration)
#   19 = log1p(orig_bytes)
#   20 = log1p(resp_bytes)
#   21 = log1p(orig_pkts)
#   22 = log1p(resp_pkts)
_CONTINUOUS_COLS: tuple[int, ...] = (18, 19, 20, 21, 22)

LABEL_BENIGN = 0
LABEL_RECON  = 1
LABEL_LM_OK  = 2


# ----------------------------------------------------------------- config

@dataclass
class SynthConfig:
    multiplier:    int   = 5       # copies generated per real positive
    time_jitter_s: float = 300.0    # ± window for ts perturbation (seconds)
    feature_noise: float = 0.15     # std of multiplicative gaussian on cont. cols
    seed:          int   = 42


# ----------------------------------------------------------------- core

def synthesize(blob: dict, cfg: SynthConfig | None = None) -> dict:
    """Return a new shard with `cfg.multiplier` synthetic copies appended
    per real LM positive. All non-tensor metadata is forwarded verbatim."""
    cfg = cfg or SynthConfig()
    if cfg.multiplier <= 0:
        return blob

    rng = np.random.default_rng(cfg.seed)

    labels  = blob["labels"].numpy()
    pos_idx = np.where(labels == LABEL_LM_OK)[0]
    n_pos   = int(pos_idx.size)
    if n_pos == 0:
        return blob

    # 1) Replicate each positive `multiplier` times.
    pick = np.repeat(pos_idx, cfg.multiplier)
    k    = int(pick.size)

    src_new  = blob["src_ids"].numpy()[pick].astype(np.int64)
    dst_new  = blob["dst_ids"].numpy()[pick].astype(np.int64)
    ts_new   = blob["ts"].numpy()[pick].astype(np.float64)
    feat_new = blob["edge_feat"].numpy()[pick].astype(np.float32).copy()

    # 2) Time jitter, clamped to the original train window. The clamp is
    #    what prevents synthetic events from spilling into the eval split's
    #    chronological window when train/eval are concatenated later.
    ts_min = float(blob["ts"].min().item())
    ts_max = float(blob["ts"].max().item())
    delta  = rng.uniform(-cfg.time_jitter_s, cfg.time_jitter_s, size=k)
    ts_new = np.clip(ts_new + delta, ts_min, ts_max)

    # 3) Multiplicative gaussian noise on continuous channels only. Clamped
    #    to non-negative because every continuous channel is a log1p() of
    #    a count or duration — negatives are nonsensical.
    cols  = list(_CONTINUOUS_COLS)
    scale = rng.normal(1.0, cfg.feature_noise, size=(k, len(cols)))
    feat_new[:, cols] = np.maximum(
        feat_new[:, cols] * scale.astype(np.float32), 0.0,
    )

    # 4) Concatenate originals + synthetics.
    src_all  = np.concatenate([blob["src_ids"].numpy(),   src_new])
    dst_all  = np.concatenate([blob["dst_ids"].numpy(),   dst_new])
    ts_all   = np.concatenate([blob["ts"].numpy(),        ts_new])
    feat_all = np.concatenate([blob["edge_feat"].numpy(), feat_new], axis=0)
    lab_all  = np.concatenate(
        [labels, np.full(k, LABEL_LM_OK, dtype=np.int64)],
    )

    # 5) Re-sort chronologically (stable mergesort, matches dataset_builder).
    order = np.argsort(ts_all, kind="stable")

    out = dict(blob)
    out["src_ids"]   = torch.from_numpy(src_all[order])
    out["dst_ids"]   = torch.from_numpy(dst_all[order])
    out["ts"]        = torch.from_numpy(ts_all[order])
    out["edge_feat"] = torch.from_numpy(feat_all[order])
    out["labels"]    = torch.from_numpy(lab_all[order])
    return out


# ----------------------------------------------------------------- reporting

def _stats(blob: dict, name: str) -> dict:
    labels = blob["labels"].numpy()
    pos = int((labels == LABEL_LM_OK).sum())
    rec = int((labels == LABEL_RECON).sum())
    neg = int((labels == LABEL_BENIGN).sum())
    ratio = neg / max(pos, 1)
    print(f"[synth_lm] {name:>6}: n={len(labels):>7}  "
          f"LM_ok={pos:>5}  recon={rec:>5}  benign={neg:>7}  "
          f"neg/pos≈{ratio:.1f}")
    return {"n": len(labels), "lm_ok": pos, "recon": rec,
            "benign": neg, "neg_per_pos": ratio}


# ----------------------------------------------------------------- entry

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="in_path",  default="data/datasets/train.pt")
    ap.add_argument("--out", dest="out_path", default="data/datasets/train_aug.pt")
    ap.add_argument("--multiplier",    type=int,   default=10)
    ap.add_argument("--time-jitter",   type=float, default=300.0)
    ap.add_argument("--feature-noise", type=float, default=0.15)
    ap.add_argument("--seed",          type=int,   default=42)
    args = ap.parse_args()

    in_path = Path(args.in_path)
    if "eval" in in_path.name.lower():
        raise SystemExit(
            f"[synth_lm] refusing to augment {in_path}: eval shards must "
            f"stay untouched. Use --in on the train shard only.")

    blob = torch.load(in_path, weights_only=False, map_location="cpu")
    _stats(blob, "before")

    aug = synthesize(blob, SynthConfig(
        multiplier=args.multiplier,
        time_jitter_s=args.time_jitter,
        feature_noise=args.feature_noise,
        seed=args.seed,
    ))
    _stats(aug, "after")

    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(aug, out_path)
    print(f"[synth_lm] saved -> {out_path}  "
          f"({out_path.stat().st_size/1e6:.1f} MB)  "
          f"cfg={asdict(SynthConfig(multiplier=args.multiplier, time_jitter_s=args.time_jitter, feature_noise=args.feature_noise, seed=args.seed))}")


if __name__ == "__main__":
    main()
