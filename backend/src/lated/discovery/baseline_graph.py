# =============================================================================
# lated.discovery.baseline_graph — baseline enterprise graph (MVP)
# =============================================================================
#
# Persists a small JSON artifact representing "what the network looks like at
# rest". Format is intentionally simple and stable:
#
#   {
#     "schema_version": "1.0.0",
#     "created_at": "<ISO8601 UTC>",
#     "nodes": [
#       {"host_id": "...", "hostname": "...", "subnet": "...",
#        "first_seen": "...", "last_seen": "...", "ip_addresses": [...]}
#     ],
#     "edges": [
#       {"src": "host-...", "dst": "host-...", "communication_count": 42}
#     ],
#     "subnets": {"10.0.0.0/24": ["host-...", ...]},
#     "gateways": ["host-..."]
#   }
# =============================================================================

from __future__ import annotations

import hmac
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lated.common.schemas import SCHEMA_VERSION


@dataclass
class BaselineNode:
    host_id: str
    hostname: str | None
    subnet: str | None
    first_seen: str
    last_seen: str
    ip_addresses: list[str] = field(default_factory=list)


@dataclass
class BaselineEdge:
    src: str
    dst: str
    communication_count: int
    src_ports: list[int] = field(default_factory=list)
    dst_ports: list[int] = field(default_factory=list)
    protocols: list[str] = field(default_factory=list)
    service_labels: list[str] = field(default_factory=list)


@dataclass
class BaselineGraph:
    """Baseline enterprise graph + JSON persistence."""

    created_at: str
    nodes: list[BaselineNode]
    edges: list[BaselineEdge]
    subnets: dict[str, list[str]] = field(default_factory=dict)
    gateways: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def build(cls, host_registry, topology: dict[str, Any]) -> "BaselineGraph":
        hosts = host_registry.list()
        nodes = [
            BaselineNode(
                host_id=host.host_id,
                hostname=host.hostname,
                subnet=host.subnet,
                first_seen=host.first_seen.isoformat(),
                last_seen=host.last_seen.isoformat(),
                ip_addresses=list(host.ip_addresses),
            )
            for host in hosts
        ]

        adjacency = topology.get("adjacency", {})
        edge_details = topology.get("edge_details", {})
        edges: list[BaselineEdge] = []
        for src in sorted(adjacency):
            for dst in sorted(adjacency[src]):
                detail = edge_details.get(src, {}).get(dst, {})
                edges.append(
                    BaselineEdge(
                        src=src,
                        dst=dst,
                        communication_count=int(adjacency[src][dst]),
                        src_ports=list(detail.get("src_ports", [])),
                        dst_ports=list(detail.get("dst_ports", [])),
                        protocols=list(detail.get("protocols", [])),
                        service_labels=list(detail.get("service_labels", [])),
                    )
                )

        return cls(
            created_at=datetime.now(timezone.utc).isoformat(),
            nodes=nodes,
            edges=edges,
            subnets={cidr: list(host_ids) for cidr, host_ids in topology.get("subnets", {}).items()},
            gateways=list(topology.get("gateways", [])),
            services=list(topology.get("services", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "subnets": dict(self.subnets),
            "gateways": list(self.gateways),
            "services": list(self.services),
        }

    def save(
        self,
        path: str | Path,
        secret_key: str | None = None,
        env: str = "development",
    ) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload_bytes = json.dumps(self.to_dict(), indent=2, sort_keys=False).encode("utf-8")
        target.write_bytes(payload_bytes)

        sig_path = _sig_path_for(target)
        if secret_key:
            sig_path.write_text(_compute_signature(payload_bytes, secret_key), encoding="utf-8")
        elif env == "production":
            raise ValueError(
                "Baseline save in production requires a secret_key for signature."
            )
        else:
            # development: keep stale sidecar from going stale silently
            if sig_path.exists():
                sig_path.unlink()
        return target

    @classmethod
    def load(
        cls,
        path: str | Path,
        secret_key: str | None = None,
        env: str = "development",
    ) -> "BaselineGraph":
        source = Path(path)
        raw_bytes = source.read_bytes()
        sig_path = _sig_path_for(source)

        if env == "production":
            if not sig_path.exists():
                raise ValueError("Production baseline must carry a .sig sidecar.")
            if secret_key is None:
                raise ValueError("Production baseline load requires a secret_key.")
            _verify_signature(raw_bytes, sig_path.read_text(encoding="utf-8").strip(), secret_key)
        elif sig_path.exists() and secret_key is not None:
            _verify_signature(raw_bytes, sig_path.read_text(encoding="utf-8").strip(), secret_key)

        payload = json.loads(raw_bytes.decode("utf-8"))
        schema = payload.get("schema_version")
        if schema != SCHEMA_VERSION:
            raise ValueError(
                f"Incompatible baseline schema_version {schema!r}; expected {SCHEMA_VERSION!r}."
            )

        nodes = [BaselineNode(**node) for node in payload.get("nodes", [])]
        edges = [BaselineEdge(**edge) for edge in payload.get("edges", [])]
        return cls(
            created_at=payload.get("created_at", ""),
            nodes=nodes,
            edges=edges,
            subnets=dict(payload.get("subnets", {})),
            gateways=list(payload.get("gateways", [])),
            services=list(payload.get("services", [])),
            schema_version=schema,
        )


def _sig_path_for(path: Path) -> Path:
    return path.with_name(path.name + ".sig")


def _compute_signature(payload: bytes, secret_key: str) -> str:
    return hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _verify_signature(payload: bytes, recorded: str, secret_key: str) -> None:
    expected = _compute_signature(payload, secret_key)
    if not hmac.compare_digest(expected, recorded):
        raise ValueError("Baseline signature mismatch.")
