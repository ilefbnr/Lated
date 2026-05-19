# =============================================================================
# lated.ingestion.zeek_parser — Zeek conn.log replay (JSON Lines)
# =============================================================================
#
# MVP scope:
#   - replay-friendly single-pass read of `conn.log*` files in a directory,
#   - JSON Lines format only (one JSON object per line; the Zeek JSON output
#     mode emits this natively),
#   - malformed lines are skipped silently with a `skipped` counter; the
#     stream keeps going.
#
# Out of scope here: live tailing with rotation, TSV header parsing, and
# stateful resume-from-offset.
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


CONN_LOG_GLOB = "conn*.log"


class ZeekParser:
    """Yields raw Zeek conn.log records from a directory of JSON files."""

    def __init__(self, log_dir: str | Path):
        self.log_dir = Path(log_dir)
        self.skipped = 0

    def records(self) -> Iterator[dict]:
        if not self.log_dir.exists() or not self.log_dir.is_dir():
            raise FileNotFoundError(f"Zeek log directory not found: {self.log_dir}")

        for log_path in sorted(self.log_dir.glob(CONN_LOG_GLOB)):
            with log_path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        self.skipped += 1
                        continue
                    if not isinstance(record, dict):
                        self.skipped += 1
                        continue
                    yield record
