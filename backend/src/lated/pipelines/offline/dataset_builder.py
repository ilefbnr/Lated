# =============================================================================
# lated.pipelines.offline.dataset_builder — train/eval shard materialization
# =============================================================================
#
# PURPOSE
# -------
# Materializes on-disk training shards from the full PicoDomain pipeline:
#
#   parser → enricher → weak_labeler → edge_featurizer → torch tensors
#
# OUTPUT (one .pt file per split)
# -------------------------------
#   {
#     "src_ids":    LongTensor [N]      node IDs (0..n_nodes-1)
#     "dst_ids":    LongTensor [N]
#     "ts":         FloatTensor [N]     UNIX seconds (kept as float for memory)
#     "edge_feat":  FloatTensor [N, F]  F = EDGE_FEAT_DIM
#     "labels":     LongTensor [N]      0 benign / 1 recon / 2 LM_ok
#     "n_nodes":    int
#     "ip_to_id":   dict[str, int]      for inverse mapping in eval reports
#     "edge_feat_dim": int
#   }
#
# Each shard is sorted chronologically — TGN training requires this.
#
# CHRONOLOGICAL SPLIT
# -------------------
#   train = day 1 + day 2  (2019-07-19, 2019-07-20)
#   eval  = day 3          (2019-07-21)
#
# A shared NodeIdMapper is built on train flows first, then extended with
# eval-only nodes. This keeps train IDs stable but lets eval reference new
# hosts (rare on PicoDomain, but the code should handle it).
#
# CYBERSECURITY REASONING
# -----------------------
# Chronological train/eval split eliminates time-leakage: the model is
# evaluated only on events strictly after everything it trained on. This
# is what production deployment looks like.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from lated.pipelines.offline.picodomain_parser import (
    PicoDomainParser, RedteamEvent, TRAIN_DAYS, EVAL_DAYS,
)
from lated.pipelines.offline.weak_labeler import WeakLabeler
from lated.pipelines.offline.edge_featurizer import (
    EDGE_FEAT_DIM, NodeIdMapper, featurize,
)


def _parse_zeek_ts(ts: str) -> float:
    """Zeek JSON ts like '2019-07-19T13:00:00.123Z' → UNIX seconds."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).timestamp()


def _materialize_split(
    parser: PicoDomainParser,
    redteam_events: list[RedteamEvent],
    days: tuple[str, ...],
    node_mapper: NodeIdMapper,
) -> dict:
    """Stream day(s) of flows, label + featurize them, return tensor dict."""
    src_ids: list[int] = []
    dst_ids: list[int] = []
    ts_list:  list[float] = []
    feats:    list[np.ndarray] = []
    labels:   list[int] = []

    wl = WeakLabeler()
    flow_stream = parser.iter_enriched_flows(day=list(days))
    for rec in wl.label(flow_stream, redteam_events):
        src_ip = rec.get("id.orig_h")
        dst_ip = rec.get("id.resp_h")
        ts_raw = rec.get("ts")
        if not src_ip or not dst_ip or not isinstance(ts_raw, str):
            continue
        src_ids.append(node_mapper.get(src_ip))
        dst_ids.append(node_mapper.get(dst_ip))
        ts_list.append(_parse_zeek_ts(ts_raw))
        feats.append(featurize(rec))
        labels.append(int(rec.get("label", 0)))

    if not ts_list:
        raise RuntimeError(f"No flows produced for days {days}")

    # Sort chronologically — Zeek output is mostly sorted but some flows
    # span chunk boundaries, so don't trust it.
    ts_arr = np.asarray(ts_list, dtype=np.float64)
    order = np.argsort(ts_arr, kind="stable")

    src_arr = np.asarray(src_ids, dtype=np.int64)[order]
    dst_arr = np.asarray(dst_ids, dtype=np.int64)[order]
    ts_arr  = ts_arr[order].astype(np.float64)
    feat_arr = np.stack(feats, axis=0)[order]
    lab_arr  = np.asarray(labels, dtype=np.int64)[order]

    return {
        "src_ids":   torch.from_numpy(src_arr),
        "dst_ids":   torch.from_numpy(dst_arr),
        "ts":        torch.from_numpy(ts_arr),
        "edge_feat": torch.from_numpy(feat_arr),
        "labels":    torch.from_numpy(lab_arr),
    }


def build_shards(
    root: str | Path = "data/picodomain",
    out_dir: str | Path = "data/datasets",
    train_days: tuple[str, ...] = TRAIN_DAYS,
    eval_days: tuple[str, ...] = EVAL_DAYS,
    augment_lm: int = 0,
) -> dict[str, Path]:
    """End-to-end materialization. Returns paths to train.pt / eval.pt.

    If `augment_lm > 0`, the train shard is passed through synth_lm.synthesize
    with that multiplier before being written to disk. The eval shard is
    never augmented.
    """
    root = Path(root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    parser = PicoDomainParser(root)
    redteam_events = list(parser.iter_redteam())

    node_mapper = NodeIdMapper()

    print(f"[dataset_builder] Building TRAIN shard from days={train_days} …")
    train = _materialize_split(parser, redteam_events, train_days, node_mapper)
    print(f"[dataset_builder]   train flows: {len(train['ts'])}, "
          f"nodes so far: {node_mapper.n_nodes}")

    print(f"[dataset_builder] Building EVAL shard from days={eval_days} …")
    eval_ = _materialize_split(parser, redteam_events, eval_days, node_mapper)
    print(f"[dataset_builder]   eval flows: {len(eval_['ts'])}, "
          f"nodes total: {node_mapper.n_nodes}")

    meta = {
        "n_nodes":       node_mapper.n_nodes,
        "ip_to_id":      node_mapper.ip_to_id,
        "edge_feat_dim": EDGE_FEAT_DIM,
    }

    train_blob = {**train, **meta}
    eval_blob  = {**eval_,  **meta}

    if augment_lm > 0:
        from lated.pipelines.offline.synth_lm import synthesize, SynthConfig, _stats
        print(f"[dataset_builder] Augmenting TRAIN shard with multiplier={augment_lm} …")
        _stats(train_blob, "before")
        train_blob = synthesize(train_blob, SynthConfig(multiplier=augment_lm))
        _stats(train_blob, "after")

    train_path = out_dir / "train.pt"
    eval_path  = out_dir / "eval.pt"
    torch.save(train_blob, train_path)
    torch.save(eval_blob,  eval_path)
    print(f"[dataset_builder] wrote {train_path}  ({train_path.stat().st_size/1e6:.1f} MB)")
    print(f"[dataset_builder] wrote {eval_path}   ({eval_path.stat().st_size/1e6:.1f} MB)")

    return {"train": train_path, "eval": eval_path}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/picodomain")
    ap.add_argument("--out",  default="data/datasets")
    ap.add_argument("--augment-lm", type=int, default=0,
                    help="Per-positive synthetic copies to add to train "
                         "(0 = no augmentation). Eval is never augmented.")
    args = ap.parse_args()
    build_shards(root=args.root, out_dir=args.out, augment_lm=args.augment_lm)
