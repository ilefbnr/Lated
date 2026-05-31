from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from lated.common.network_topology import NetworkTopology


class GraphRepository:
    """Read-oriented repository serving graph payloads to the SOC UI."""

    def __init__(
        self,
        session_factory,
        baseline_path: str | Path | None = None,
        network_topology: NetworkTopology | None = None,
    ):
        self.session_factory = session_factory
        self.baseline_path = Path(baseline_path) if baseline_path else None
        self.network_topology = network_topology or NetworkTopology.default()

    def baseline(self) -> dict:
        if self.baseline_path is not None and self.baseline_path.exists():
            return self._baseline_from_artifact()
        return self._load_single(kind="baseline")

    def resolve_node_ids(self, host_ids: list[str] | set[str]) -> dict[str, str]:
        baseline = self.baseline()
        requested = list(host_ids)
        available = {node["data"]["id"] for node in baseline["nodes"]}
        resolved: dict[str, str] = {
            host_id: host_id for host_id in requested if host_id in available
        }

        missing = [host_id for host_id in requested if host_id not in resolved]
        if not missing:
            return resolved

        hostname_by_id = self._load_hostnames(missing)
        aliases: dict[str, str] = {}
        for node in baseline["nodes"]:
            data = node["data"]
            canonical_id = data["id"]
            for candidate in filter(None, {data.get("label"), data.get("hostname")}):
                aliases[str(candidate).lower()] = canonical_id

        for host_id in missing:
            hostname = hostname_by_id.get(host_id)
            if hostname is None:
                continue
            canonical_id = aliases.get(hostname.lower())
            if canonical_id is not None:
                resolved[host_id] = canonical_id

        return resolved

    def _baseline_from_artifact(self) -> dict:
        with self.baseline_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        risks = self._load_host_risks()
        gateway_ids = set(data.get("gateways", []))
        service_ids = set(data.get("services", []))
        nodes_by_id = {node["host_id"]: node for node in data.get("nodes", [])}
        nodes = []
        node_external: dict[str, bool] = {}
        for node in data.get("nodes", []):
            host_id = node["host_id"]
            ip_addresses = list(node.get("ip_addresses", []))
            classification = self.network_topology.classify_host(ip_addresses)
            external = classification.zone.value == "external"
            node_external[host_id] = external
            nodes.append(
                {
                    "data": {
                        "id": host_id,
                        "label": node.get("hostname") or host_id,
                        "risk": risks.get(host_id, 0.0),
                        "hostname": node.get("hostname"),
                        "subnet": node.get("subnet"),
                        "ip_addresses": ip_addresses,
                        "first_seen": node.get("first_seen"),
                        "last_seen": node.get("last_seen"),
                        "os_guess": node.get("os_guess"),
                        "gateway": host_id in gateway_ids,
                        "service": host_id in service_ids,
                        "external": external,
                        "zone": classification.zone.value,
                        "trust": classification.trust.value,
                        "critical_asset": self.network_topology.is_critical_asset(
                            host_id, ip_addresses
                        ),
                    }
                }
            )
        edges = []
        for edge in data.get("edges", []):
            edge_external = self._edge_is_external(edge, nodes_by_id, node_external)
            edges.append(
                {
                    "data": {
                        "id": f"{edge['src']}->{edge['dst']}@baseline",
                        "source": edge["src"],
                        "target": edge["dst"],
                        "label": self._edge_label(edge),
                        "weight": edge.get("communication_count", 0),
                        "src_ports": list(edge.get("src_ports", [])),
                        "dst_ports": list(edge.get("dst_ports", [])),
                        "protocols": list(edge.get("protocols", [])),
                        "service_labels": list(edge.get("service_labels", [])),
                        "external": edge_external,
                        "connection_type": "external" if edge_external else "internal",
                    }
                }
            )
        subnets = data.get("subnets", {})
        return {
            "nodes": nodes,
            "edges": edges,
            "generated_at": data.get("created_at", ""),
            "summary": {
                "host_count": len(nodes),
                "edge_count": len(edges),
                "subnet_count": len(subnets),
                "subnets": [
                    {"cidr": cidr, "host_count": len(host_ids)}
                    for cidr, host_ids in sorted(subnets.items())
                ],
                "gateway_host_ids": sorted(gateway_ids),
                "service_host_ids": sorted(service_ids),
            },
        }

    @staticmethod
    def _edge_label(edge: dict) -> str:
        services = [str(item) for item in edge.get("service_labels", []) if item]
        if services:
            return " / ".join(services)
        ports = [str(port) for port in edge.get("dst_ports", []) if port is not None]
        if ports:
            return f"ports {', '.join(ports[:3])}"
        protocols = [str(proto).upper() for proto in edge.get("protocols", []) if proto]
        if protocols:
            return " / ".join(protocols)
        return "communication"

    def _edge_is_external(
        self,
        edge: dict,
        nodes_by_id: dict[str, dict],
        precomputed: dict[str, bool],
    ) -> bool:
        src_id = edge.get("src")
        dst_id = edge.get("dst")
        if src_id in precomputed and dst_id in precomputed:
            return precomputed[src_id] or precomputed[dst_id]
        src_ips = list(nodes_by_id.get(src_id, {}).get("ip_addresses", []))
        dst_ips = list(nodes_by_id.get(dst_id, {}).get("ip_addresses", []))
        return self.network_topology.is_external_edge(src_ips, dst_ips)

    def _load_host_risks(self) -> dict[str, float]:
        try:
            with self.session_factory() as connection:
                rows = connection.execute("SELECT host_id, current_risk FROM hosts").fetchall()
        except Exception:
            return {}
        return {row["host_id"]: row["current_risk"] for row in rows}

    def latest_snapshot(self) -> dict:
        with self.session_factory() as connection:
            row = connection.execute(
                """
                SELECT snapshot_id, ts, nodes, edges FROM graph_snapshots
                WHERE kind = 'snapshot'
                ORDER BY ts DESC, snapshot_id DESC
                LIMIT 1
                """,
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="No snapshot available")
        return self._row_to_payload(row)

    def snapshot_at(self, ts: str) -> dict:
        with self.session_factory() as connection:
            row = connection.execute(
                """
                SELECT snapshot_id, ts, nodes, edges FROM graph_snapshots
                WHERE kind = 'snapshot' AND ts = ?
                LIMIT 1
                """,
                (ts,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return self._row_to_payload(row)

    def host_ego(self, host_id: str, hops: int = 1) -> dict:
        del hops
        baseline = self.baseline()
        resolved = self.resolve_node_ids([host_id]).get(host_id, host_id)
        edges = [
            edge
            for edge in baseline["edges"]
            if edge["data"]["source"] == resolved or edge["data"]["target"] == resolved
        ]
        node_ids = {resolved}
        for edge in edges:
            node_ids.add(edge["data"]["source"])
            node_ids.add(edge["data"]["target"])
        nodes = [node for node in baseline["nodes"] if node["data"]["id"] in node_ids]
        if not nodes:
            raise HTTPException(status_code=404, detail="Host not found in graph")
        return {"nodes": nodes, "edges": edges, "generated_at": baseline["generated_at"]}

    def _load_hostnames(self, host_ids: list[str]) -> dict[str, str]:
        if not host_ids:
            return {}
        placeholders = ", ".join("?" for _ in host_ids)
        try:
            with self.session_factory() as connection:
                rows = connection.execute(
                    f"SELECT host_id, hostname FROM hosts WHERE host_id IN ({placeholders})",
                    tuple(host_ids),
                ).fetchall()
        except Exception:
            return {}
        return {
            row["host_id"]: row["hostname"]
            for row in rows
            if row["hostname"] is not None
        }

    def _load_single(self, kind: str) -> dict:
        with self.session_factory() as connection:
            row = connection.execute(
                """
                SELECT snapshot_id, ts, nodes, edges FROM graph_snapshots
                WHERE kind = ?
                ORDER BY ts DESC, snapshot_id DESC
                LIMIT 1
                """,
                (kind,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"No {kind} graph available")
        return self._row_to_payload(row)

    @staticmethod
    def _row_to_payload(row) -> dict:
        return {
            "nodes": json.loads(row["nodes"]),
            "edges": json.loads(row["edges"]),
            "generated_at": row["ts"],
        }
