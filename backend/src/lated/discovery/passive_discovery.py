# =============================================================================
# lated.discovery.passive_discovery — non-intrusive host discovery
# =============================================================================
#
# Two supported modes:
#
#   1. Replay (file)
#      `source` is a JSON file with shape:
#        {"hosts":[{ip,mac?,hostname?,first_seen,last_seen,...}],
#         "flows":[{src_ip,dst_ip,ts,count?,src_port?,dst_port?}]}
#
#   2. Live (directory)
#      `source` is a directory; every `*.log` file is read line-by-line as
#      NDJSON. Each line is one event:
#        {"kind":"host","ip":...,"mac"?:...,"hostname"?:...,"ts":...}
#        {"kind":"arp","ip":...,"mac":...,"ts":...}
#        {"kind":"dns","ip":...,"hostname":...,"ts":...}
#        {"kind":"flow","src_ip":...,"dst_ip":...,"ts":...,
#         "count"?:N,"src_port"?:N,"dst_port"?:N}
#
# Live mode is a single-pass tail (everything currently on disk). It is real
# (no fake support, no silent fallback) and trivially testable. Continuous
# tailing would require a worker thread — out of scope for this hardening pass.
# =============================================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from lated.common.schemas import Host

from lated.discovery.host_registry import HostRegistry, _to_datetime


@dataclass(frozen=True)
class ObservedEdge:
    src_host_id: str
    dst_host_id: str
    ts: datetime
    count: int
    src_port: int | None = None
    dst_port: int | None = None
    protocol: str | None = None


@dataclass
class PassiveObservation:
    hosts: list[Host]
    edges: list[ObservedEdge]


class PassiveDiscovery:
    """Reads observations from a fixture file (replay) or a log directory (live)."""

    def __init__(self, host_registry: HostRegistry, source: str | Path):
        self.host_registry = host_registry
        self.source = Path(source)

    def observe(self) -> PassiveObservation:
        if not self.source.exists():
            raise FileNotFoundError(f"Passive discovery source not found: {self.source}")
        if self.source.is_dir():
            hosts_raw, flows_raw = self._read_live_directory(self.source)
        elif self.source.suffix.lower() in {".pcap", ".pcapng"}:
            hosts_raw, flows_raw = self._read_pcap_file(self.source)
        elif self.source.suffix.lower() in {".log", ".jsonl", ".ndjson"}:
            hosts_raw, flows_raw = self._read_log_file(self.source)
        else:
            hosts_raw, flows_raw = self._read_replay_file(self.source)

        for record in hosts_raw:
            self.host_registry.upsert(record)

        edges: list[ObservedEdge] = []
        for flow in flows_raw:
            ts = _to_datetime(flow["ts"])
            src_id = self._resolve_endpoint(flow, "src", ts)
            dst_id = self._resolve_endpoint(flow, "dst", ts)
            edges.append(
                ObservedEdge(
                    src_host_id=src_id,
                    dst_host_id=dst_id,
                    ts=ts,
                    count=int(flow.get("count", 1)),
                    src_port=flow.get("src_port"),
                    dst_port=flow.get("dst_port"),
                    protocol=str(flow.get("protocol") or flow.get("proto") or "").lower() or None,
                )
            )

        return PassiveObservation(hosts=self.host_registry.list(), edges=edges)

    @staticmethod
    def _read_replay_file(path: Path) -> tuple[list[dict], list[dict]]:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Discovery fixture must be a JSON object with 'hosts' and 'flows' keys.")
        return list(payload.get("hosts", [])), list(payload.get("flows", []))

    @classmethod
    def _read_live_directory(cls, directory: Path) -> tuple[list[dict], list[dict]]:
        hosts: list[dict] = []
        flows: list[dict] = []
        for log_path in sorted(directory.glob("*.log")):
            cls._read_log_lines(log_path, hosts, flows)
        return hosts, flows

    @classmethod
    def _read_log_file(cls, path: Path) -> tuple[list[dict], list[dict]]:
        hosts: list[dict] = []
        flows: list[dict] = []
        cls._read_log_lines(path, hosts, flows)
        return hosts, flows

    @classmethod
    def _read_log_lines(cls, path: Path, hosts: list[dict], flows: list[dict]) -> None:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, start=1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid NDJSON in {path}:{line_no}: {exc.msg}"
                    ) from exc
                cls._dispatch_event(event, hosts, flows)

    @staticmethod
    def _read_pcap_file(path: Path) -> tuple[list[dict], list[dict]]:
        try:
            from scapy.all import IP, TCP, UDP, PcapReader  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PCAP passive discovery requires scapy to be installed.") from exc

        hosts: list[dict] = []
        flows: list[dict] = []
        with PcapReader(str(path)) as reader:
            for packet in reader:
                if IP not in packet:
                    continue
                ip_layer = packet[IP]
                ts = datetime.fromtimestamp(float(packet.time), tz=timezone.utc).isoformat()
                src_port = None
                dst_port = None
                if TCP in packet:
                    src_port = int(packet[TCP].sport)
                    dst_port = int(packet[TCP].dport)
                elif UDP in packet:
                    src_port = int(packet[UDP].sport)
                    dst_port = int(packet[UDP].dport)
                hosts.append({"ip": ip_layer.src, "first_seen": ts, "last_seen": ts})
                hosts.append({"ip": ip_layer.dst, "first_seen": ts, "last_seen": ts})
                flows.append(
                    {
                        "src_ip": ip_layer.src,
                        "dst_ip": ip_layer.dst,
                        "ts": ts,
                        "count": 1,
                        "src_port": src_port,
                        "dst_port": dst_port,
                    }
                )
        return hosts, flows

    @staticmethod
    def _dispatch_event(event: dict[str, Any], hosts: list[dict], flows: list[dict]) -> None:
        if PassiveDiscovery._looks_like_zeek_flow(event):
            ts = event.get("ts")
            src_ip = event.get("id.orig_h")
            dst_ip = event.get("id.resp_h")
            if src_ip:
                hosts.append({"ip": src_ip, "first_seen": ts, "last_seen": ts})
            if dst_ip:
                hosts.append({"ip": dst_ip, "first_seen": ts, "last_seen": ts})
            flows.append(
                {
                    "src_ip": src_ip,
                    "dst_ip": dst_ip,
                    "ts": ts,
                    "count": 1,
                    "src_port": event.get("id.orig_p"),
                    "dst_port": event.get("id.resp_p"),
                }
            )
            return
        kind = event.get("kind", "host")
        ts = event.get("ts") or event.get("first_seen") or event.get("last_seen")
        if kind == "flow":
            flows.append(event)
            for side in ("src", "dst"):
                ip = event.get(f"{side}_ip")
                if ip:
                    hosts.append({"ip": ip, "first_seen": ts, "last_seen": ts})
            return
        candidate = {k: v for k, v in event.items() if k != "kind"}
        candidate.setdefault("first_seen", ts)
        candidate.setdefault("last_seen", ts)
        hosts.append(candidate)

    @staticmethod
    def _looks_like_zeek_flow(event: dict[str, Any]) -> bool:
        return "id.orig_h" in event and "id.resp_h" in event and "ts" in event

    def _resolve_endpoint(self, flow: dict[str, Any], side: str, ts: datetime) -> str:
        ip_key = f"{side}_ip"
        ip = flow.get(ip_key)
        if not ip:
            raise ValueError(f"Flow entry missing '{ip_key}': {flow}")
        try:
            return self.host_registry.resolve(ip, ts)
        except KeyError:
            return self.host_registry.upsert({"ip": ip, "first_seen": ts, "last_seen": ts})
