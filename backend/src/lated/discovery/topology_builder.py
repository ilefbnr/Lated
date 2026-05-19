# =============================================================================
# lated.discovery.topology_builder — adjacency + subnet view
# =============================================================================
#
# Produces:
#   - subnets   : { CIDR -> [host_id, ...] }
#   - adjacency : { host_id -> { neighbor_host_id -> communication_count } }
#   - gateways  : hosts mediating traffic across multiple subnets (real signal)
#   - services  : hosts with significant cross-subnet fan-in on well-known
#                 service ports (DNS/SMB/HTTP/AD, etc.)
#
# Gateway heuristic:
#   A host G is a gateway iff
#     * G is observed as the SOURCE of flows whose destinations span >= 2
#       distinct subnets DIFFERENT from G's own subnet, AND
#     * the total cross-subnet flow count from G >= MIN_GATEWAY_CROSSINGS.
#   This is stricter than "touched >= 2 subnets" — a workstation that talks
#   to its file server AND its DC stays a workstation, not a gateway.
#
# Service heuristic:
#   A host S is a service host iff
#     * it appears as DESTINATION on a well-known service port from
#       sources spanning >= 2 subnets, OR
#     * its incoming flow count on a well-known port >= MIN_SERVICE_FAN_IN.
# =============================================================================

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from lated.common.schemas import Host

from lated.discovery.passive_discovery import ObservedEdge


WELL_KNOWN_SERVICE_PORTS = frozenset({22, 25, 53, 80, 88, 110, 123, 135, 139, 143, 389, 443, 445, 465, 514, 636, 993, 995, 3306, 3389, 5432})

MIN_GATEWAY_CROSSINGS = 2
MIN_SERVICE_FAN_IN = 3


class TopologyBuilder:
    """Builds a subnet + adjacency view from hosts and observed edges."""

    def build(self, hosts: Iterable[Host], edges: Iterable[ObservedEdge]) -> dict:
        hosts = list(hosts)
        edges = list(edges)

        subnets: dict[str, list[str]] = defaultdict(list)
        host_subnets: dict[str, str | None] = {}
        for host in hosts:
            host_subnets[host.host_id] = host.subnet
            if host.subnet:
                subnets[host.subnet].append(host.host_id)

        adjacency: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        edge_details: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
        for edge in edges:
            adjacency[edge.src_host_id][edge.dst_host_id] += edge.count
            detail = edge_details.setdefault(edge.src_host_id, {}).setdefault(
                edge.dst_host_id,
                {"dst_ports": set(), "src_ports": set(), "protocols": set()},
            )
            if edge.dst_port is not None:
                detail["dst_ports"].add(int(edge.dst_port))
            if edge.src_port is not None:
                detail["src_ports"].add(int(edge.src_port))
            if edge.protocol:
                detail["protocols"].add(str(edge.protocol).lower())

        gateways = self._infer_gateways(edges, host_subnets)
        services = self._infer_services(edges, host_subnets)

        sorted_subnets = {cidr: sorted(set(host_ids)) for cidr, host_ids in sorted(subnets.items())}
        sorted_adjacency = {
            src: dict(sorted(neighbors.items()))
            for src, neighbors in sorted(adjacency.items())
        }

        return {
            "subnets": sorted_subnets,
            "adjacency": sorted_adjacency,
            "edge_details": {
                src: {
                    dst: {
                        "dst_ports": sorted(detail["dst_ports"]),
                        "src_ports": sorted(detail["src_ports"]),
                        "protocols": sorted(detail["protocols"]),
                        "service_labels": self._service_labels_for_ports(sorted(detail["dst_ports"])),
                    }
                    for dst, detail in sorted(neighbors.items())
                }
                for src, neighbors in sorted(edge_details.items())
            },
            "gateways": gateways,
            "services": services,
        }

    @staticmethod
    def _service_labels_for_ports(dst_ports: list[int]) -> list[str]:
        port_map = {
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
        seen: list[str] = []
        for port in dst_ports:
            label = port_map.get(int(port))
            if label and label not in seen:
                seen.append(label)
        return seen

    @staticmethod
    def _infer_gateways(edges: list[ObservedEdge], host_subnets: dict[str, str | None]) -> list[str]:
        outbound_subnets: dict[str, set[str]] = defaultdict(set)
        outbound_count: dict[str, int] = defaultdict(int)
        for edge in edges:
            src_subnet = host_subnets.get(edge.src_host_id)
            dst_subnet = host_subnets.get(edge.dst_host_id)
            if src_subnet is None or dst_subnet is None:
                continue
            if src_subnet == dst_subnet:
                continue
            outbound_subnets[edge.src_host_id].add(dst_subnet)
            outbound_count[edge.src_host_id] += edge.count
        return sorted(
            host_id
            for host_id, observed in outbound_subnets.items()
            if len(observed) >= 2 and outbound_count[host_id] >= MIN_GATEWAY_CROSSINGS
        )

    @staticmethod
    def _infer_services(edges: list[ObservedEdge], host_subnets: dict[str, str | None]) -> list[str]:
        cross_subnet_sources: dict[str, set[str]] = defaultdict(set)
        well_known_fan_in: dict[str, int] = defaultdict(int)
        for edge in edges:
            if edge.dst_port not in WELL_KNOWN_SERVICE_PORTS:
                continue
            src_subnet = host_subnets.get(edge.src_host_id)
            dst_subnet = host_subnets.get(edge.dst_host_id)
            if src_subnet is not None and dst_subnet is not None and src_subnet != dst_subnet:
                cross_subnet_sources[edge.dst_host_id].add(src_subnet)
            well_known_fan_in[edge.dst_host_id] += edge.count
        return sorted(
            host_id
            for host_id in set(cross_subnet_sources) | set(well_known_fan_in)
            if len(cross_subnet_sources.get(host_id, set())) >= 2
            or well_known_fan_in.get(host_id, 0) >= MIN_SERVICE_FAN_IN
        )
