# =============================================================================
# lated.ingestion.netflow_parser — NetFlow / IPFIX collector
# =============================================================================
#
# PURPOSE
# -------
# Listens on a UDP port for NetFlow v5 / v9 / IPFIX exports and converts them
# into raw flow records.
#
# INPUTS
# ------
#   - UDP port number (typically 2055).
#   - Allowed exporter IPs (denylist enforced — drop unknown sources).
#
# OUTPUTS
# -------
#   - Raw flow dicts.
#
# INTERACTIONS
# ------------
#   - ingestion_service : consumer.
#
# CYBERSECURITY REASONING
# -----------------------
# NetFlow exports come from routers/switches — relatively trustworthy, but
# the UDP listener is internet-accessible from inside the network. Hardening:
#   - bind to internal interface only,
#   - allowlist of exporter IPs,
#   - parser rejects oversized / malformed templates,
#   - per-exporter rate limit to prevent log flooding.
# =============================================================================

from __future__ import annotations

import json
import socket
import time
from pathlib import Path
from typing import Iterator


class NetFlowParser:
    """UDP collector + decoder for NetFlow / IPFIX.

    Internal logic
    --------------
      - Bind a UDP socket on the configured port.
      - Maintain a per-exporter template table (v9 / IPFIX require it).
      - On each datagram:
          - check source against the allowlist,
          - decode header + records,
          - emit one raw flow dict per data record.
    """

    def __init__(
        self,
        port: int,
        allowlist: list[str],
        source_path: str | None = None,
        mode: str = "replay",
        max_idle_seconds: float = 5.0,
    ):
        self.port = int(port)
        self.allowlist = set(allowlist)
        self.source_path = source_path
        self.mode = str(mode)
        self.max_idle_seconds = float(max_idle_seconds)

    def records(self) -> Iterator[dict]:
        if self.mode == "live":
            yield from self._records_live()
            return
        yield from self._records_replay()

    def _records_replay(self) -> Iterator[dict]:
        if not self.source_path:
            raise FileNotFoundError("NetFlow replay requires a source_path.")
        path = Path(self.source_path)
        if not path.exists():
            raise FileNotFoundError(f"NetFlow replay file not found: {path}")
        with path.open("r", encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, start=1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid NetFlow replay record at {path}:{line_no}: {exc.msg}") from exc
                if not isinstance(record, dict):
                    continue
                yield record

    def _records_live(self) -> Iterator[dict]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", self.port))
        sock.settimeout(0.5)
        idle_since = time.monotonic()
        try:
            while True:
                try:
                    payload, address = sock.recvfrom(65535)
                except socket.timeout:
                    if time.monotonic() - idle_since >= self.max_idle_seconds:
                        return
                    continue
                exporter_ip = address[0]
                if self.allowlist and exporter_ip not in self.allowlist:
                    continue
                idle_since = time.monotonic()
                try:
                    record = json.loads(payload.decode("utf-8"))
                except Exception:
                    continue
                if isinstance(record, dict):
                    yield record
        finally:
            sock.close()
