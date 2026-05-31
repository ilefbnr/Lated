# =============================================================================
# lated.supervision.realtime_graph — flow-by-flow in-memory graph state
# =============================================================================

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from lated.common.network_topology import NetworkTopology
from lated.common.schemas import CanonicalFlow, WSChannel, WSEvent, WSEventName
from lated.discovery.host_registry import HostRegistry


def _normalize_ts(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


@dataclass
class RealtimeGraphState:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[str, dict[str, Any]] = field(default_factory=dict)
    generated_at: str = ""


class RealtimeGraphProcessor:
    """Maintains and publishes an in-memory graph updated flow by flow."""

    def __init__(
        self,
        publisher,
        host_registry: HostRegistry | None = None,
        network_topology: NetworkTopology | None = None,
    ):
        self.publisher = publisher
        self.host_registry = host_registry
        self.network_topology = network_topology or NetworkTopology.default()
        self.state = RealtimeGraphState()
        self._edge_packets: dict[str, int] = defaultdict(int)
        self._edge_bytes: dict[str, int] = defaultdict(int)

    def ingest(self, flow: CanonicalFlow) -> dict[str, Any]:
        ts = _normalize_ts(flow.ts).isoformat()
        self.state.generated_at = ts

        self._ensure_node(flow.src_host)
        self._ensure_node(flow.dst_host)

        edge_id = f"{flow.src_host}->{flow.dst_host}@live"
        self._edge_packets[edge_id] += int(flow.packet_count)
        self._edge_bytes[edge_id] += int(flow.byte_count)
        self.state.edges[edge_id] = {
            "data": {
                "id": edge_id,
                "source": flow.src_host,
                "target": flow.dst_host,
                "label": f"{str(flow.protocol).upper()} {flow.dst_port}",
                "weight": self._edge_bytes[edge_id],
                "packet_count": self._edge_packets[edge_id],
                "byte_count": self._edge_bytes[edge_id],
                "protocols": [str(flow.protocol)],
                "dst_ports": [int(flow.dst_port)],
                "src_ports": [int(flow.src_port)],
                "service_labels": [self._service_label(flow.dst_port)],
                "external": self._edge_is_external(flow.src_host, flow.dst_host),
                "connection_type": "external" if self._edge_is_external(flow.src_host, flow.dst_host) else "internal",
            }
        }

        payload = {
            "nodes": list(self.state.nodes.values()),
            "edges": [self.state.edges[edge_id]],
            "generated_at": self.state.generated_at,
        }
        event = WSEvent(
            channel=WSChannel.GRAPH,
            event=WSEventName.GRAPH_UPDATE,
            payload=payload,
            ts=_normalize_ts(flow.ts),
        )
        self._publish(event)
        return payload

    def snapshot(self) -> dict[str, Any]:
        return {
            "nodes": list(self.state.nodes.values()),
            "edges": list(self.state.edges.values()),
            "generated_at": self.state.generated_at,
        }

    def _publish(self, event: WSEvent) -> None:
        if self.publisher is None:
            return
        publish = getattr(self.publisher, "publish", None)
        if publish is not None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(publish(event))
                return
            loop.create_task(publish(event))

    def _ensure_node(self, host_id: str) -> None:
        if host_id in self.state.nodes:
            return
        label = host_id
        subnet = None
        ip_addresses: list[str] = []
        if self.host_registry is not None:
            try:
                host = self.host_registry.get(host_id)
                label = host.hostname or host.host_id
                subnet = host.subnet
                ip_addresses = list(host.ip_addresses)
            except Exception:
                pass

        classification = self.network_topology.classify_host(ip_addresses)
        critical = self.network_topology.is_critical_asset(host_id, ip_addresses)
        self.state.nodes[host_id] = {
            "data": {
                "id": host_id,
                "label": label,
                "risk": 0.0,
                "subnet": subnet,
                "ip_addresses": ip_addresses,
                "external": classification.zone.value == "external",
                "zone": classification.zone.value,
                "trust": classification.trust.value,
                "critical_asset": critical,
            }
        }

    def _edge_is_external(self, src_host: str, dst_host: str) -> bool:
        src = self.state.nodes.get(src_host, {}).get("data", {})
        dst = self.state.nodes.get(dst_host, {}).get("data", {})
        return bool(src.get("external") or dst.get("external"))

    @staticmethod
    def _service_label(port: int) -> str:
        labels = {
            22: "SSH",
            53: "DNS",
            80: "HTTP",
            88: "Kerberos",
            135: "RPC",
            139: "NetBIOS",
            389: "LDAP",
            443: "HTTPS",
            445: "SMB",
            636: "LDAPS",
            3389: "RDP",
            5985: "WinRM",
            5986: "WinRM-TLS",
        }
        return labels.get(int(port), f"PORT-{port}")
