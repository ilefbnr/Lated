# =============================================================================
# lated.ingestion.pcap_parser — PCAP source parser
# =============================================================================
#
# PURPOSE
# -------
# Reads packet capture data (live interface or PCAP file) and yields raw flow
# records. Flow aggregation is done with a configurable timeout (default 60s).
#
# INPUTS
# ------
#   - Live mode  : a network interface name (requires CAP_NET_RAW).
#   - File mode  : path to a .pcap / .pcapng file (e.g. for replay/testing).
#
# OUTPUTS
# -------
#   - Stream of raw flow dicts:
#       { ts, src_ip, dst_ip, src_port, dst_port, proto,
#         duration, packets, bytes, sensor }
#
# INTERACTIONS
# ------------
#   - ingestion_service : drives the parser via .records().
#
# CYBERSECURITY REASONING
# -----------------------
# PCAP parsing is the highest-risk parser:
#   - operates on attacker-controlled bytes,
#   - underlying libraries (scapy / libpcap) have a non-zero CVE history.
# Hardening:
#   - run in a dedicated container with read-only fs and dropped privileges,
#   - cap packet rate per source IP (rate-limit reassembly),
#   - reject malformed packets quickly — never recurse into nested layers
#     beyond a configured depth.
# =============================================================================

from __future__ import annotations

from typing import AsyncIterator


class PCAPParser:
    """Parses pcap files / live interfaces into raw flow records.

    Internal logic
    --------------
      __init__(source: str, mode: 'live'|'file')

      async records() -> AsyncIterator[dict]:
        # 1. Open scapy sniff (live) or PcapReader (file).
        # 2. For each packet:
        #    - extract 5-tuple,
        #    - update an in-memory flow table keyed on 5-tuple,
        #    - on flow timeout (no packet for N seconds), emit the flow.
        # 3. Drop packets that fail safety checks (oversized headers, etc.).
    """

    def __init__(self, source: str, mode: str):
        ...

    async def records(self) -> AsyncIterator[dict]:
        raise NotImplementedError("Architecture skeleton.")
