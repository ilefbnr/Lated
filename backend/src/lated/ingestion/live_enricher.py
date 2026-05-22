# =============================================================================
# lated.ingestion.live_enricher — streaming join of Zeek logs by `uid`
# =============================================================================
#
# Counterpart of `ZeekEnricher` for the live / replay_live pipeline. The
# offline enricher pre-loads a full hour of enrichment logs and joins;
# this one is incremental:
#
#   - Records flow in interleaved by `ts` (from ZeekParser multi-log mode).
#   - Non-conn records (smb_files, smb_mapping, dce_rpc, ntlm, kerberos)
#     are buffered in a uid-indexed dict.
#   - When a conn record arrives, we look up its uid bucket, derive the
#     enrichment fields, attach them under `enrichment`, and yield.
#   - Stale uid buckets are evicted by TTL to bound memory.
#
# Why this works for live: in Zeek, `conn.log` is written at connection
# END while protocol-event logs (smb_files, ntlm, kerberos…) are written
# DURING the connection. So enrichment records reliably arrive *before*
# the conn record. The TTL exists to catch the rare reverse case and to
# drop uids whose conn never materialized (e.g. dropped packets).
# =============================================================================

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Iterable, Iterator


# Same derivation tables as the offline ZeekEnricher — keep in sync.
_PE_EXTENSIONS = (
    ".exe", ".dll", ".ps1", ".bat", ".scr", ".cmd",
    ".vbs", ".hta", ".lnk", ".msi", ".jar",
)
_ADMIN_SHARES = ("ADMIN$", "C$", "IPC$")

# Log types we actually use for enrichment. Records of other types pass
# through harmlessly (buffered then evicted by TTL — they don't hurt).
_ENRICHMENT_TYPES = ("smb_files", "smb_mapping", "dce_rpc", "ntlm", "kerberos")


class LiveZeekEnricher:
    """Streaming join: in -> interleaved Zeek records, out -> enriched conn."""

    def __init__(self, max_buffered_uids: int = 20000):
        # OrderedDict gives us O(1) LRU eviction without an extra index.
        self._buffer: "OrderedDict[str, dict[str, list[dict]]]" = OrderedDict()
        self.max_buffered_uids = int(max_buffered_uids)

    # ------------------------------------------------------------------ API

    def enrich_stream(self, records: Iterable[dict]) -> Iterator[dict]:
        """Consume the parser's stream, yield enriched conn records only.

        Non-conn records are absorbed into the uid buffer. A conn record
        triggers a buffer lookup + emission with an `enrichment` dict
        attached. The buffer entry is dropped on emit (one-shot semantics:
        we don't expect a second conn with the same uid)."""
        for record in records:
            logtype = record.pop("_zeek_logtype", "conn")
            if logtype == "conn":
                conn = record
                conn["enrichment"] = self._derive(conn.get("uid"))
                yield conn
                continue
            if logtype in _ENRICHMENT_TYPES:
                self._buffer_record(logtype, record)

    # ------------------------------------------------------------- internals

    def _buffer_record(self, logtype: str, record: dict) -> None:
        uid = record.get("uid")
        if not uid:
            return
        bucket = self._buffer.get(uid)
        if bucket is None:
            bucket = {t: [] for t in _ENRICHMENT_TYPES}
            self._buffer[uid] = bucket
        else:
            # Refresh LRU position — recently-touched uids survive longer.
            self._buffer.move_to_end(uid)
        bucket[logtype].append(record)

        # Bounded buffer: evict the least-recently-touched uid(s).
        while len(self._buffer) > self.max_buffered_uids:
            self._buffer.popitem(last=False)

    def _derive(self, uid: str | None) -> dict[str, Any]:
        """Build the enrichment payload for a given uid and remove its
        buffer entry. Returns the empty defaults if uid is unknown."""
        derived: dict[str, Any] = {
            "smb_paths": [],
            "smb_files_names": [],
            "smb_actions": [],
            "admin_share": False,
            "has_pe_transfer": False,
            "smb_tree_name": None,
            "dce_endpoints": [],
            "dce_operations": [],
            "dce_pipes": [],
            "has_ntlm": False,
            "ntlm_success": False,
            "ntlm_client_hostname": None,
            "ntlm_server_hostname": None,
            "kerberos_types": [],
            "kerberos_services": [],
        }
        if not uid:
            return derived
        bucket = self._buffer.pop(uid, None)
        if bucket is None:
            return derived

        # --- smb_files ---
        for rec in bucket["smb_files"]:
            path = rec.get("path")
            name = rec.get("name")
            action = rec.get("action")
            if path:
                derived["smb_paths"].append(path)
                if any(s in path.upper() for s in _ADMIN_SHARES):
                    derived["admin_share"] = True
            if name:
                derived["smb_files_names"].append(name)
                low = name.lower()
                if any(low.endswith(ext) for ext in _PE_EXTENSIONS):
                    derived["has_pe_transfer"] = True
            if action:
                derived["smb_actions"].append(action)

        # --- smb_mapping ---
        for rec in bucket["smb_mapping"]:
            tree = rec.get("server_tree_name")
            if tree and derived["smb_tree_name"] is None:
                derived["smb_tree_name"] = tree

        # --- dce_rpc ---
        for rec in bucket["dce_rpc"]:
            ep = rec.get("endpoint")
            op = rec.get("operation")
            pipe = rec.get("named_pipe")
            if ep:
                derived["dce_endpoints"].append(ep)
            if op:
                derived["dce_operations"].append(op)
            if pipe:
                derived["dce_pipes"].append(str(pipe))

        # --- ntlm ---
        if bucket["ntlm"]:
            derived["has_ntlm"] = True
            for rec in bucket["ntlm"]:
                if rec.get("success") is True:
                    derived["ntlm_success"] = True
                if rec.get("hostname") and derived["ntlm_client_hostname"] is None:
                    derived["ntlm_client_hostname"] = rec["hostname"]
                srv = rec.get("server_nb_computer_name") or rec.get("server_dns_computer_name")
                if srv and derived["ntlm_server_hostname"] is None:
                    derived["ntlm_server_hostname"] = srv

        # --- kerberos ---
        for rec in bucket["kerberos"]:
            req_type = rec.get("request_type")
            service = rec.get("service")
            if req_type:
                derived["kerberos_types"].append(req_type)
            if service:
                derived["kerberos_services"].append(service)

        return derived
