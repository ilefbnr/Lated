# =============================================================================
# lated.detection.tgnn.runtime_featurizer — CanonicalFlow -> 47-dim vector
# =============================================================================
#
# Mirrors `pipelines.offline.edge_featurizer.featurize` but consumes our
# canonical runtime shape (CanonicalFlow + enrichment dict) instead of the
# raw enriched Zeek conn dict. Output layout MUST match the trained model:
#
#   idx 0..13   port bucket (one-hot, 14 buckets)
#   idx 14..17  protocol one-hot
#   idx 18      log1p(duration)
#   idx 19      log1p(orig_bytes ≈ byte_count for runtime — split unknown)
#   idx 20      log1p(resp_bytes ≈ 0)
#   idx 21      log1p(orig_pkts ≈ packet_count)
#   idx 22      log1p(resp_pkts ≈ 0)
#   idx 23..32  conn_state one-hot (10 Zeek states; left zero at runtime)
#   idx 33      local_orig (1 if both hosts internal, else 0)
#   idx 34      local_resp (1 if dst internal, else 0)
#   idx 35..40  enrichment booleans (has_smb, has_dce, has_ntlm,
#                ntlm_success, has_pe_transfer, admin_share)
#   idx 41..46  DCE endpoint flags (drsuapi, scm_remote, wbem,
#                netlogon, srvsvc, epmapper)
#
# Parity with offline featurizer:
#   - CanonicalFlow now preserves the directional split (orig/resp bytes+pkts),
#     `conn_state`, and `local_orig`/`local_resp` straight from the Zeek conn
#     record (see FlowNormalizer). The runtime vector is therefore identical to
#     the training vector for Zeek-sourced flows.
#   - For non-Zeek sensors that lack these fields, we degrade gracefully: the
#     total goes on the orig side (idx 19/21), resp stays 0, conn_state stays
#     all-zero, and local_* default to 0 (mirrors the offline featurizer's
#     behavior on missing fields).
# =============================================================================

from __future__ import annotations

import math
from typing import Any

import numpy as np

from lated.common.schemas import CanonicalFlow
from lated.pipelines.offline.edge_featurizer import (
    EDGE_FEAT_DIM, PORT_BUCKETS, _CONN_STATE_INDEX, _DCE_FLAG_KEYWORDS,
)


_PROTO_INDEX: dict[str, int] = {"tcp": 0, "udp": 1, "icmp": 2}


def _port_bucket(port: int | None) -> int:
    if port is None or port < 0:
        return 13
    if port in PORT_BUCKETS:
        return PORT_BUCKETS[port]
    return 12 if port < 1024 else 13


def _proto_idx(proto: str | None) -> int:
    if proto is None:
        return 3
    return _PROTO_INDEX.get(str(proto).lower(), 3)


def _safe_log1p(x: Any) -> float:
    if x is None:
        return 0.0
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    if v <= 0:
        return 0.0
    return math.log1p(v)


def featurize_flow(flow: CanonicalFlow) -> np.ndarray:
    """Return a (47,) float32 vector matching the trained model's input."""
    feat = np.zeros(EDGE_FEAT_DIM, dtype=np.float32)

    feat[_port_bucket(int(flow.dst_port))] = 1.0
    feat[14 + _proto_idx(str(flow.protocol))] = 1.0

    feat[18] = _safe_log1p(flow.duration)

    # Directional bytes/pkts: use the real Zeek split when CanonicalFlow carries
    # it (now preserved by FlowNormalizer); otherwise degrade gracefully by
    # putting the total on the orig side — same fallback the old code used.
    orig_bytes = flow.orig_bytes if flow.orig_bytes is not None else flow.byte_count
    resp_bytes = flow.resp_bytes if flow.resp_bytes is not None else 0
    orig_pkts = flow.orig_pkts if flow.orig_pkts is not None else flow.packet_count
    resp_pkts = flow.resp_pkts if flow.resp_pkts is not None else 0
    feat[19] = _safe_log1p(orig_bytes)
    feat[20] = _safe_log1p(resp_bytes)
    feat[21] = _safe_log1p(orig_pkts)
    feat[22] = _safe_log1p(resp_pkts)

    # conn_state one-hot (idx 23..32) — same table as the offline featurizer.
    if flow.conn_state is not None:
        cs_idx = _CONN_STATE_INDEX.get(flow.conn_state)
        if cs_idx is not None:
            feat[23 + cs_idx] = 1.0

    enr = flow.enrichment or {}
    # local_orig / local_resp from Zeek when available (matches training). When
    # absent (non-Zeek sensor), default to 0 to mirror the offline featurizer's
    # behavior on missing fields, rather than the old hard-coded 1.
    feat[33] = 1.0 if flow.local_orig else 0.0
    feat[34] = 1.0 if flow.local_resp else 0.0

    feat[35] = 1.0 if enr.get("smb_paths") else 0.0
    feat[36] = 1.0 if enr.get("dce_endpoints") else 0.0
    feat[37] = 1.0 if enr.get("has_ntlm") else 0.0
    feat[38] = 1.0 if enr.get("ntlm_success") else 0.0
    feat[39] = 1.0 if enr.get("has_pe_transfer") else 0.0
    feat[40] = 1.0 if enr.get("admin_share") else 0.0

    endpoints = enr.get("dce_endpoints") or []
    endpoints_low = " ".join(str(e).lower() for e in endpoints)
    for offset, (_flag, kws) in enumerate(_DCE_FLAG_KEYWORDS):
        if any(kw in endpoints_low for kw in kws):
            feat[41 + offset] = 1.0

    return feat
