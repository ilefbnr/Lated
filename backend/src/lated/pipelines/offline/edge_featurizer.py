# =============================================================================
# lated.pipelines.offline.edge_featurizer — enriched flow -> tensor row
# =============================================================================
#
# PURPOSE
# -------
# Turns an enriched conn dict (output of ZeekEnricher) into the fixed-size
# numeric row the TGN trainer expects: (src_id, dst_id, ts_float, edge_feat).
# Designed for offline batch use — produces NumPy arrays, not torch tensors,
# so we can compose with the dataset builder without depending on torch here.
#
# FEATURE LAYOUT (TOTAL = 47 dims)
# --------------------------------
#   idx 0..13   port bucket (one-hot, 14 buckets — see PORT_BUCKETS)
#   idx 14..17  protocol one-hot (tcp / udp / icmp / other)
#   idx 18      log1p(duration)
#   idx 19      log1p(orig_bytes)
#   idx 20      log1p(resp_bytes)
#   idx 21      log1p(orig_pkts)
#   idx 22      log1p(resp_pkts)
#   idx 23..32  conn_state one-hot (10 Zeek states)
#   idx 33      local_orig (0/1)
#   idx 34      local_resp (0/1)
#   idx 35..40  enrichment booleans (has_smb, has_dce, has_ntlm,
#                ntlm_success, has_pe_transfer, admin_share)
#   idx 41..46  DCE endpoint flags (drsuapi, scm_remote, wbem,
#                netlogon, srvsvc, epmapper)
#
# All values are float32 in [0, ~log range]. No scaling here — let the
# downstream model do its own normalization with BatchNorm or LayerNorm if
# needed.
# =============================================================================

from __future__ import annotations

import math
import numpy as np


# ----------------------------------------------------------------- constants

EDGE_FEAT_DIM: int = 47

PORT_BUCKETS: dict[int, int] = {
    53: 0,    # DNS
    88: 1,    # Kerberos
    135: 2,   # DCE-RPC endpoint mapper
    137: 3,   # NetBIOS name
    138: 3,   # NetBIOS datagram (shares bucket 3)
    139: 4,   # NetBIOS session (SMB v1)
    389: 5,   # LDAP
    445: 6,   # SMB
    3389: 7,  # RDP
    5985: 8,  # WinRM
    5986: 8,  # WinRM/SSL
    22: 9,    # SSH
    80: 10,   # HTTP
    443: 11,  # HTTPS
    # 12 = other_low  (port < 1024)
    # 13 = other_high (port >= 1024)
}
_N_PORT_BUCKETS = 14

_PROTO_INDEX: dict[str, int] = {"tcp": 0, "udp": 1, "icmp": 2}
_N_PROTO = 4   # tcp / udp / icmp / other

_CONN_STATES: tuple[str, ...] = (
    "SF", "S0", "REJ", "RSTO", "RSTR", "OTH", "S1", "S2", "S3", "SH",
)
_CONN_STATE_INDEX: dict[str, int] = {s: i for i, s in enumerate(_CONN_STATES)}
_N_CONN_STATES = len(_CONN_STATES)

# DCE endpoint flag → set of substrings (lowercased) that activate it.
_DCE_FLAG_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("drsuapi",   ("drsuapi",)),
    ("scm",       ("iremotescmact", "scmactivator")),
    ("wbem",      ("iwbemservices", "iwbemlevel1login", "iwbemloginclient")),
    ("netlogon",  ("netlogon",)),
    ("srvsvc",    ("srvsvc",)),
    ("epmapper",  ("epmapper",)),
)
_N_DCE_FLAGS = len(_DCE_FLAG_KEYWORDS)


# ----------------------------------------------------------------- helpers

def _port_bucket(port: int | None) -> int:
    if port is None or port < 0:
        return 13
    if port in PORT_BUCKETS:
        return PORT_BUCKETS[port]
    return 12 if port < 1024 else 13


def _proto_idx(proto: str | None) -> int:
    if proto is None:
        return 3
    return _PROTO_INDEX.get(proto.lower(), 3)


def _conn_state_idx(state: str | None) -> int | None:
    if state is None:
        return None
    return _CONN_STATE_INDEX.get(state)


def _safe_log1p(x) -> float:
    if x is None:
        return 0.0
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    if v <= 0:
        return 0.0
    return math.log1p(v)


# --------------------------------------------------------------- featurizer

def featurize(rec: dict) -> np.ndarray:
    """Turn one enriched conn dict into a float32 vector of shape (47,)."""
    feat = np.zeros(EDGE_FEAT_DIM, dtype=np.float32)

    # --- port one-hot (0..13) ---
    feat[_port_bucket(rec.get("id.resp_p"))] = 1.0

    # --- protocol one-hot (14..17) ---
    feat[14 + _proto_idx(rec.get("proto"))] = 1.0

    # --- duration + bytes + packets (18..22) ---
    feat[18] = _safe_log1p(rec.get("duration"))
    feat[19] = _safe_log1p(rec.get("orig_bytes"))
    feat[20] = _safe_log1p(rec.get("resp_bytes"))
    feat[21] = _safe_log1p(rec.get("orig_pkts"))
    feat[22] = _safe_log1p(rec.get("resp_pkts"))

    # --- conn_state one-hot (23..32) ---
    cs_idx = _conn_state_idx(rec.get("conn_state"))
    if cs_idx is not None:
        feat[23 + cs_idx] = 1.0

    # --- local_orig / local_resp (33..34) ---
    feat[33] = 1.0 if rec.get("local_orig") else 0.0
    feat[34] = 1.0 if rec.get("local_resp") else 0.0

    # --- enrichment booleans (35..40) ---
    feat[35] = 1.0 if rec.get("smb_paths") else 0.0
    feat[36] = 1.0 if rec.get("dce_endpoints") else 0.0
    feat[37] = 1.0 if rec.get("has_ntlm") else 0.0
    feat[38] = 1.0 if rec.get("ntlm_success") else 0.0
    feat[39] = 1.0 if rec.get("has_pe_transfer") else 0.0
    feat[40] = 1.0 if rec.get("admin_share") else 0.0

    # --- DCE endpoint flags (41..46) ---
    endpoints = rec.get("dce_endpoints") or []
    endpoints_low = " ".join(str(e).lower() for e in endpoints)
    for offset, (_flag, kws) in enumerate(_DCE_FLAG_KEYWORDS):
        if any(kw in endpoints_low for kw in kws):
            feat[41 + offset] = 1.0

    return feat


# --------------------------------------------------------------- node mapper

class NodeIdMapper:
    """Assigns stable integer IDs (0..N-1) to host IPs as they are seen."""

    def __init__(self):
        self._ip_to_id: dict[str, int] = {}

    def get(self, ip: str) -> int:
        nid = self._ip_to_id.get(ip)
        if nid is None:
            nid = len(self._ip_to_id)
            self._ip_to_id[ip] = nid
        return nid

    @property
    def n_nodes(self) -> int:
        return len(self._ip_to_id)

    @property
    def ip_to_id(self) -> dict[str, int]:
        return dict(self._ip_to_id)

    def id_to_ip(self) -> dict[int, str]:
        return {v: k for k, v in self._ip_to_id.items()}
