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

from typing import AsyncIterator


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

    def __init__(self, port: int, allowlist: list[str]):
        ...

    async def records(self) -> AsyncIterator[dict]:
        raise NotImplementedError("Architecture skeleton.")
