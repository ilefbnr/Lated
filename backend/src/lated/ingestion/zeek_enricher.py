# =============================================================================
# lated.ingestion.zeek_enricher — join conn.log with SMB / DCE-RPC / NTLM
# =============================================================================
#
# PURPOSE
# -------
# Generic Zeek-by-`uid` joiner. Reads a directory of hourly-chunked Zeek JSON
# logs (conn, smb_files, smb_mapping, dce_rpc, ntlm) and yields conn records
# augmented with derived fields that the MITRE Rules detector consumes.
#
# The join key is Zeek's `uid` — the same connection-unique identifier shows
# up across all four enrichment logs for events tied to that connection.
#
# JOIN STRATEGY
# -------------
# Per-hour batch index. For each hourly chunk N of conn.log, we load the
# matching enrichment logs (smb_files.N, dce_rpc.N, …) into a dict keyed by
# `uid`, then iterate conn.log and look up.
#
#   Memory: bounded by one hour of enrichment events (a few MB on PicoDomain).
#   Caveat: a uid whose enrichment events span hour boundaries (rare, only
#           long-lived SMB sessions) will be partially joined. Acceptable
#           for offline use; the lost coverage is marginal.
#
# OUTPUT FIELDS (derived, added to each conn dict)
# ------------------------------------------------
#   smb_paths              list[str]    \\host\share strings touched
#   smb_files_names        list[str]    filenames accessed
#   admin_share            bool         path contains ADMIN$ / C$ / IPC$
#   has_pe_transfer        bool         filename ends in .exe/.dll/.ps1/.bat/.scr
#   smb_tree_name          str | None   first server_tree_name seen (smb_mapping)
#   dce_endpoints          list[str]    RPC endpoints called (drsuapi, …)
#   dce_operations         list[str]    RPC operation names
#   dce_pipes              list[str]    named_pipe values
#   has_ntlm               bool
#   ntlm_success           bool
#   ntlm_client_hostname   str | None   client-claimed hostname (PtH signal)
#   ntlm_server_hostname   str | None   server-side hostname
#
# CYBERSECURITY REASONING
# -----------------------
# These derived fields are the minimal set the MITRE rules need to fire
# without doing additional parsing in the detector. Keeping derivation in
# ingestion (rather than the detector) means the rules stay declarative and
# testable.
# =============================================================================

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator


# Hourly chunk filename: e.g. `conn.13_00_00-14_00_00.log`. The suffix
# (after the leading `<logtype>.`) is what we join enrichment files by.
_HOURLY_SUFFIX_RE = re.compile(r"^conn\.(\d\d_\d\d_\d\d-\d\d_\d\d_\d\d)\.log$")

# File extensions / share names that signal a binary or admin share.
_PE_EXTENSIONS = (".exe", ".dll", ".ps1", ".bat", ".scr", ".cmd", ".vbs",
                   ".hta", ".lnk", ".msi", ".jar")
_ADMIN_SHARES = ("ADMIN$", "C$", "IPC$")


class ZeekEnricher:
    """Joins conn.log with smb_files / smb_mapping / dce_rpc / ntlm by `uid`."""

    def __init__(self, day_dir: str | Path):
        self.day_dir = Path(day_dir)
        if not self.day_dir.is_dir():
            raise FileNotFoundError(f"Zeek day directory not found: {self.day_dir}")
        self.skipped = 0

    # ------------------------------------------------------------------ API

    def iter_enriched_conn(self) -> Iterator[dict]:
        """Yields conn records with enrichment fields attached."""
        for hour_suffix in self._discover_hours():
            uid_index = self._build_uid_index(hour_suffix)
            conn_path = self.day_dir / f"conn.{hour_suffix}.log"
            for rec in self._iter_jsonl(conn_path):
                self._enrich(rec, uid_index)
                yield rec

    # ----------------------------------------------------------- internals

    def _discover_hours(self) -> list[str]:
        """Return sorted list of hourly suffixes present as conn.*.log."""
        suffixes: list[str] = []
        for path in self.day_dir.glob("conn.*.log"):
            m = _HOURLY_SUFFIX_RE.match(path.name)
            if m:
                suffixes.append(m.group(1))
        return sorted(suffixes)

    def _build_uid_index(self, hour_suffix: str) -> dict[str, dict[str, list[dict]]]:
        """
        Build `{uid: {"smb_files": [...], "smb_mapping": [...],
                       "dce_rpc": [...], "ntlm": [...]}}` for one hour.

        Missing files are tolerated — not every hour has every log type.
        """
        index: dict[str, dict[str, list[dict]]] = {}
        for logtype in ("smb_files", "smb_mapping", "dce_rpc", "ntlm"):
            path = self.day_dir / f"{logtype}.{hour_suffix}.log"
            if not path.is_file():
                continue
            for rec in self._iter_jsonl(path):
                uid = rec.get("uid")
                if not uid:
                    continue
                bucket = index.setdefault(uid, {
                    "smb_files": [], "smb_mapping": [],
                    "dce_rpc": [], "ntlm": [],
                })
                bucket[logtype].append(rec)
        return index

    def _enrich(self, conn: dict, uid_index: dict[str, dict[str, list[dict]]]) -> None:
        """Mutate `conn` in-place to add derived enrichment fields."""
        # Always set defaults so downstream code can rely on the keys existing.
        conn["smb_paths"] = []
        conn["smb_files_names"] = []
        conn["admin_share"] = False
        conn["has_pe_transfer"] = False
        conn["smb_tree_name"] = None
        conn["dce_endpoints"] = []
        conn["dce_operations"] = []
        conn["dce_pipes"] = []
        conn["has_ntlm"] = False
        conn["ntlm_success"] = False
        conn["ntlm_client_hostname"] = None
        conn["ntlm_server_hostname"] = None

        uid = conn.get("uid")
        if not uid:
            return
        bucket = uid_index.get(uid)
        if bucket is None:
            return

        # --- smb_files ---
        for rec in bucket["smb_files"]:
            path = rec.get("path")
            name = rec.get("name")
            if path:
                conn["smb_paths"].append(path)
                up = path.upper()
                if any(s in up for s in _ADMIN_SHARES):
                    conn["admin_share"] = True
            if name:
                conn["smb_files_names"].append(name)
                low = name.lower()
                if any(low.endswith(ext) for ext in _PE_EXTENSIONS):
                    conn["has_pe_transfer"] = True

        # --- smb_mapping ---
        for rec in bucket["smb_mapping"]:
            tree = rec.get("server_tree_name")
            if tree and conn["smb_tree_name"] is None:
                conn["smb_tree_name"] = tree

        # --- dce_rpc ---
        for rec in bucket["dce_rpc"]:
            ep = rec.get("endpoint")
            op = rec.get("operation")
            pipe = rec.get("named_pipe")
            if ep:   conn["dce_endpoints"].append(ep)
            if op:   conn["dce_operations"].append(op)
            if pipe: conn["dce_pipes"].append(str(pipe))

        # --- ntlm ---
        if bucket["ntlm"]:
            conn["has_ntlm"] = True
            for rec in bucket["ntlm"]:
                if rec.get("success") is True:
                    conn["ntlm_success"] = True
                if rec.get("hostname") and conn["ntlm_client_hostname"] is None:
                    conn["ntlm_client_hostname"] = rec["hostname"]
                srv = rec.get("server_nb_computer_name") or rec.get("server_dns_computer_name")
                if srv and conn["ntlm_server_hostname"] is None:
                    conn["ntlm_server_hostname"] = srv

    def _iter_jsonl(self, path: Path) -> Iterator[dict]:
        """Read a Zeek JSON-Lines log, skipping malformed lines."""
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    self.skipped += 1
                    continue
                if isinstance(rec, dict):
                    yield rec
                else:
                    self.skipped += 1
