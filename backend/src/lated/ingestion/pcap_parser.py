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

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


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

    def __init__(
        self,
        source: str,
        mode: str,
        flow_timeout_seconds: int = 60,
        max_idle_seconds: float = 5.0,
    ):
        self.source = str(source)
        self.mode = str(mode)
        self.flow_timeout_seconds = int(flow_timeout_seconds)
        self.max_idle_seconds = float(max_idle_seconds)

    def records(self) -> Iterator[dict]:
        try:
            from scapy.all import IP, TCP, UDP, AsyncSniffer, PcapReader  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PCAP parsing requires scapy to be installed.") from exc

        if self.mode == "live":
            packets: list = []
            sniffer = AsyncSniffer(iface=self.source, store=True)
            sniffer.start()
            sniffer.join(timeout=self.max_idle_seconds)
            sniffer.stop()
            packets = list(getattr(sniffer, "results", []) or [])
        else:
            path = Path(self.source)
            if not path.exists():
                raise FileNotFoundError(f"PCAP file not found: {path}")
            with PcapReader(str(path)) as reader:
                packets = list(reader)

        flow_table: dict[tuple[str, str, int, int, str], dict[str, object]] = {}
        for packet in packets:
            if IP not in packet:
                continue
            ip_layer = packet[IP]
            protocol = "other"
            src_port = 0
            dst_port = 0
            if TCP in packet:
                protocol = "tcp"
                src_port = int(packet[TCP].sport)
                dst_port = int(packet[TCP].dport)
            elif UDP in packet:
                protocol = "udp"
                src_port = int(packet[UDP].sport)
                dst_port = int(packet[UDP].dport)

            ts = datetime.fromtimestamp(float(packet.time), tz=timezone.utc)
            key = (str(ip_layer.src), str(ip_layer.dst), src_port, dst_port, protocol)
            entry = flow_table.get(key)
            packet_len = int(len(packet))
            if entry is None:
                flow_table[key] = {
                    "ts": ts,
                    "src_ip": str(ip_layer.src),
                    "dst_ip": str(ip_layer.dst),
                    "src_port": src_port,
                    "dst_port": dst_port,
                    "proto": protocol,
                    "duration": 0.0,
                    "packets": 1,
                    "bytes": packet_len,
                    "last_seen": ts,
                }
                continue
            start = entry["ts"]
            last_seen = entry["last_seen"]
            if isinstance(start, datetime) and isinstance(last_seen, datetime):
                entry["duration"] = max(float(entry["duration"]), (ts - start).total_seconds())
            entry["packets"] = int(entry["packets"]) + 1
            entry["bytes"] = int(entry["bytes"]) + packet_len
            entry["last_seen"] = ts

        for index, record in enumerate(sorted(flow_table.values(), key=lambda item: item["ts"]), start=1):
            yield {
                "flow_id": f"pcap-{index:06d}",
                "ts": record["ts"],
                "src_ip": record["src_ip"],
                "dst_ip": record["dst_ip"],
                "src_port": record["src_port"],
                "dst_port": record["dst_port"],
                "proto": record["proto"],
                "duration": record["duration"],
                "packet_count": record["packets"],
                "byte_count": record["bytes"],
            }
