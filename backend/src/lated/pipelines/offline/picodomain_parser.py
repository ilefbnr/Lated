# =============================================================================
# lated.pipelines.offline.picodomain_parser — PicoDomain dataset parser
# =============================================================================
#
# PURPOSE
# -------
# Parses the PicoDomain-master dataset (replaces LANL as the offline corpus):
#   - per-day Zeek logs (conn.log + enrichment logs) split into hourly chunks
#   - Red Log.xlsx ground-truth red-team activity
#
# It yields RAW Zeek records (downstream `flow_normalizer` converts them into
# CanonicalFlow) and RedteamEvent objects (downstream `weak_labeler` projects
# them onto the flow stream).
#
# DATASET LAYOUT (root = backend/data/picodomain)
#   <root>/
#     2019-07-19/        ← day 1, training
#       conn.HH_00_00-HH_00_00.log
#       smb_files.*.log  smb_mapping.*.log  dce_rpc.*.log
#       ntlm.*.log       kerberos.*.log     dns.*.log  ...
#     2019-07-20/        ← day 2, training
#     2019-07-21/        ← day 3, evaluation
#     Red Log.xlsx
#
# All Zeek logs are JSON Lines (one object per line, dotted keys like
# `id.orig_h`). ZeekParser already handles this format, so we reuse it.
#
# INTERACTIONS
# ------------
#   - ingestion.zeek_parser.ZeekParser : reused per-day for conn.log iteration.
#   - dataset_builder                  : consumer (Step 4 of the plan).
#   - weak_labeler                     : consumer of iter_redteam (Step 3).
#
# CYBERSECURITY REASONING
# -----------------------
# Red-team prose in the Action column has no MITRE technique IDs. We classify
# each row into a coarse phase via keyword match — good enough for weak
# labelling (binary LM vs not-LM) without overcommitting to a taxonomy the
# author of the dataset never used.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Iterator, Iterable

from lated.ingestion.zeek_parser import ZeekParser
from lated.ingestion.zeek_enricher import ZeekEnricher


# -----------------------------------------------------------------------------
# Static dataset metadata (lifted from the "Normal User Workstations" sheet of
# Red Log.xlsx). Baked here because it is structural: only 7 hosts exist and
# they will not change between runs.
# -----------------------------------------------------------------------------
HOST_IP_MAP: dict[str, str] = {
    "10.99.99.27":  "RND-WIN10-2",
    "10.99.99.29":  "RND-WIN10-1",
    "10.99.99.30":  "HR-WIN7-2",
    "10.99.99.152": "HR-WIN7-1",
    "10.99.99.160": "SUPERSECRETXP",
    "10.99.99.5":   "CORP-DC",
    "10.99.99.100": "PFSENSE",
}
HOSTNAME_IP_MAP: dict[str, str] = {v.upper(): k for k, v in HOST_IP_MAP.items()}

DAYS: tuple[str, ...] = ("2019-07-19", "2019-07-20", "2019-07-21")
TRAIN_DAYS: tuple[str, ...] = ("2019-07-19", "2019-07-20")
EVAL_DAYS: tuple[str, ...] = ("2019-07-21",)


# -----------------------------------------------------------------------------
# Red-team event schema
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class RedteamEvent:
    """A single ground-truth red-team action from Red Log.xlsx."""

    ts: datetime                   # full UTC timestamp
    victim_host: str               # hostname as written in the spreadsheet
    victim_ip: str | None          # resolved via HOSTNAME_IP_MAP (None if unknown)
    victim_user: str | None
    c2_server: str | None
    action: str                    # raw prose
    phase: str                     # classified phase (see _classify_phase)


# Keyword → phase. Order matters: first match wins, so put the strongest
# signals first.
_PHASE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lateral",        ("lateral", "pivot", "wmiexec", "psexec", "smbexec",
                         "winrm", "rdp ", "ssh ", "remote service", "remote exec",
                         "wmi ", " via ")),
    ("recon",          ("nmap", "port scan", "enumerat", "discover",
                         "recon", "sweep")),
    ("credential",     ("credential", "mimikatz", "lsass", "kerberoast",
                         "asreproast", "dump", "secretsdump", "hash")),
    ("privesc",        ("elevate", "privesc", "hot potato", "local admin",
                         "uac", "token")),
    ("persistence",    ("persisten", "run key", "scheduled task", "hijackable",
                         "wmi event", "registry run")),
    ("exfil",          ("exfil", "upload", "transfer out", "exfiltration")),
    ("initial_access", ("trojaniz", "phish", "download", "macro", "archive")),
    ("execution",      ("callback", "callbac", "execute", "agent", "tasked",
                         "reboot", "session", "meterpreter", "beacon")),
)


def _classify_phase(action: str) -> str:
    a = action.lower()
    for phase, kws in _PHASE_KEYWORDS:
        if any(kw in a for kw in kws):
            return phase
    return "other"


# -----------------------------------------------------------------------------
# Parser
# -----------------------------------------------------------------------------
class PicoDomainParser:
    """Iterators over PicoDomain Zeek conn.log records and Red Log events."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        if not self.root.is_dir():
            raise FileNotFoundError(f"PicoDomain root not found: {self.root}")
        self.skipped = 0

    # ------------------------------------------------------------------ flows

    def iter_flows(self, day: str | Iterable[str] | None = None) -> Iterator[dict]:
        """
        Yields raw Zeek conn.log records (JSON dicts).

        `day` selects which day(s) to read:
          - None      → all three days in chronological order
          - "2019-07-19" → single day
          - iterable of day strings → those days in the given order

        Downstream `flow_normalizer` converts these dicts into CanonicalFlow.
        """
        for d in self._resolve_days(day):
            day_dir = self.root / d
            parser = ZeekParser(day_dir)          # globs `conn*.log`
            yield from parser.records()
            self.skipped += parser.skipped

    def iter_enriched_flows(self, day: str | Iterable[str] | None = None) -> Iterator[dict]:
        """
        Yields conn.log records with SMB / DCE-RPC / NTLM enrichment fields
        attached (joined by `uid` within each hourly chunk). This is what
        the MITRE Rules detector consumes.
        """
        for d in self._resolve_days(day):
            enricher = ZeekEnricher(self.root / d)
            yield from enricher.iter_enriched_conn()
            self.skipped += enricher.skipped

    def _resolve_days(self, day: str | Iterable[str] | None) -> tuple[str, ...]:
        if day is None:
            return DAYS
        if isinstance(day, str):
            return (day,)
        return tuple(day)

    # --------------------------------------------------------------- redteam

    def iter_redteam(self) -> Iterator[RedteamEvent]:
        """
        Yields RedteamEvent objects parsed from Red Log.xlsx.

        Spreadsheet structure (sheet "Red Activity"):
          - column A: either a `datetime` (date header for the section)
                      or a `time` (clock-of-day of one event)
          - columns B..E: victim host, victim user, C2 server, action prose
        Date headers have empty B..E; data rows have populated B..E.
        """
        # Local import: openpyxl is only needed for offline labelling, not for
        # the online runtime, so don't impose it on the runtime requirements.
        import openpyxl  # type: ignore

        xlsx_path = self.root / "Red Log.xlsx"
        wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
        ws = wb["Red Activity"]

        current_date: date | None = None
        rows = ws.iter_rows(values_only=True)
        next(rows, None)                          # skip the header row

        for raw in rows:
            if raw is None:
                continue
            ts_cell = raw[0] if len(raw) > 0 else None
            victim_host = raw[1] if len(raw) > 1 else None
            victim_user = raw[2] if len(raw) > 2 else None
            c2_server   = raw[3] if len(raw) > 3 else None
            action      = raw[4] if len(raw) > 4 else None

            # Section header: column A is a datetime (midnight), B..E empty.
            if isinstance(ts_cell, datetime) and victim_host is None:
                current_date = ts_cell.date()
                continue

            # Data row: column A is a time-of-day, B..E populated.
            if isinstance(ts_cell, time) and victim_host:
                # "END OF DATA" is a sentinel terminator row in the spreadsheet
                # — no real event, drop it silently.
                if str(victim_host).strip().upper() == "END OF DATA":
                    continue
                if current_date is None:
                    self.skipped += 1
                    continue
                ts = datetime.combine(current_date, ts_cell, tzinfo=timezone.utc)
                victim_ip = HOSTNAME_IP_MAP.get(str(victim_host).upper())
                yield RedteamEvent(
                    ts=ts,
                    victim_host=str(victim_host),
                    victim_ip=victim_ip,
                    victim_user=str(victim_user) if victim_user else None,
                    c2_server=str(c2_server) if c2_server else None,
                    action=str(action) if action else "",
                    phase=_classify_phase(str(action) if action else ""),
                )
                continue

            # Unrecognised row (blank, partial). Don't crash — count and move on.
            if ts_cell is not None or victim_host is not None:
                self.skipped += 1

        wb.close()
