# =============================================================================
# lated.discovery.host_registry — canonical host identity service
# =============================================================================
#
# MVP IMPLEMENTATION
# ------------------
# Time-indexed in-memory registry. Deterministic host_ids derived from the
# most stable observed key (MAC > hostname > first observed IP) so test
# fixtures map to the same identifiers run after run.
#
# Matching priority for upsert():
#   1. MAC address (cross-IP, cross-hostname stable)
#   2. stable hostname
#   3. IP + temporal proximity (last_seen within liveness window)
#
# resolve(ip, ts) replays the IP <-> host bindings: when an IP gets reassigned
# (DHCP churn), the registry keeps both bindings with valid_from/valid_to so
# historical lookups stay correct.
# =============================================================================

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lated.common.schemas import SCHEMA_VERSION, Host


DEFAULT_LIVENESS_SECONDS = 86400


@dataclass
class _Binding:
    ip: str
    valid_from: datetime
    valid_to: datetime | None = None


@dataclass
class _Record:
    host_id: str
    ip_addresses: list[str] = field(default_factory=list)
    hostname: str | None = None
    subnet: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    mac: str | None = None
    os_guess: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    bindings: list[_Binding] = field(default_factory=list)


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise TypeError(f"Cannot interpret datetime value: {value!r}")


def _stable_key(mac: str | None, hostname: str | None, ip: str | None, first_seen: datetime) -> str:
    if mac:
        return f"mac:{mac.lower()}"
    if hostname:
        return f"hostname:{hostname.lower()}"
    if ip:
        return f"ip:{ip}@{first_seen.isoformat()}"
    raise ValueError("Candidate must carry at least one of mac, hostname, ip.")


def _derive_host_id(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"host-{digest}"


def _infer_subnet(ip: str) -> str | None:
    parts = ip.split(".")
    if len(parts) != 4:
        return None
    return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"


class HostRegistry:
    """Time-indexed canonical host registry (MVP, in-memory)."""

    def __init__(self, liveness_seconds: int = DEFAULT_LIVENESS_SECONDS):
        self._records: dict[str, _Record] = {}
        self._by_mac: dict[str, str] = {}
        self._by_hostname: dict[str, str] = {}
        self._liveness = timedelta(seconds=liveness_seconds)

    def upsert(self, candidate: dict[str, Any]) -> str:
        """Insert or update a host candidate. Returns the canonical host_id."""
        ip = candidate.get("ip")
        mac = candidate.get("mac")
        hostname = candidate.get("hostname")
        first_seen = _to_datetime(candidate.get("first_seen") or candidate.get("ts"))
        last_seen = _to_datetime(candidate.get("last_seen") or candidate.get("ts") or first_seen)

        host_id = self._match(mac=mac, hostname=hostname, ip=ip, ts=first_seen)
        if host_id is None:
            host_id = _derive_host_id(_stable_key(mac, hostname, ip, first_seen))
            self._records[host_id] = _Record(host_id=host_id, first_seen=first_seen)

        record = self._records[host_id]

        if mac:
            mac_key = mac.lower()
            record.mac = mac_key
            self._by_mac[mac_key] = host_id
        if hostname:
            host_key = hostname.lower()
            record.hostname = hostname
            self._by_hostname[host_key] = host_id
        if ip:
            self._bind_ip(record, ip, first_seen, last_seen)
            if record.subnet is None:
                record.subnet = _infer_subnet(ip)
        if candidate.get("os_guess"):
            record.os_guess = candidate["os_guess"]
        if candidate.get("metadata"):
            record.metadata.update(dict(candidate["metadata"]))

        if record.first_seen is None or first_seen < record.first_seen:
            record.first_seen = first_seen
        if record.last_seen is None or last_seen > record.last_seen:
            record.last_seen = last_seen

        return host_id

    def resolve(self, ip: str, ts: datetime | str) -> str:
        """Return the host_id bound to `ip` at `ts`."""
        when = _to_datetime(ts)
        for record in self._records.values():
            for binding in record.bindings:
                if binding.ip != ip:
                    continue
                if binding.valid_from <= when and (binding.valid_to is None or when <= binding.valid_to):
                    return record.host_id
        raise KeyError(f"No host bound to {ip} at {when.isoformat()}")

    def get(self, host_id: str) -> Host:
        record = self._records.get(host_id)
        if record is None:
            raise KeyError(f"Unknown host_id: {host_id}")
        return self._to_schema(record)

    def list(self) -> list[Host]:
        return [self._to_schema(record) for record in sorted(self._records.values(), key=lambda r: r.host_id)]

    def list_active(self, now: datetime | str) -> list[Host]:
        cutoff = _to_datetime(now) - self._liveness
        return [
            self._to_schema(record)
            for record in sorted(self._records.values(), key=lambda r: r.host_id)
            if record.last_seen is not None and record.last_seen >= cutoff
        ]

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "liveness_seconds": int(self._liveness.total_seconds()),
            "records": [self._record_to_dict(record) for record in sorted(self._records.values(), key=lambda r: r.host_id)],
        }
        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "HostRegistry":
        source = Path(path)
        with source.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"Incompatible host_registry schema_version {payload.get('schema_version')!r}."
            )
        registry = cls(liveness_seconds=int(payload.get("liveness_seconds", DEFAULT_LIVENESS_SECONDS)))
        for raw in payload.get("records", []):
            record = _Record(
                host_id=raw["host_id"],
                ip_addresses=list(raw.get("ip_addresses", [])),
                hostname=raw.get("hostname"),
                subnet=raw.get("subnet"),
                first_seen=_to_datetime(raw["first_seen"]) if raw.get("first_seen") else None,
                last_seen=_to_datetime(raw["last_seen"]) if raw.get("last_seen") else None,
                mac=raw.get("mac"),
                os_guess=raw.get("os_guess"),
                metadata=dict(raw.get("metadata", {})),
                bindings=[
                    _Binding(
                        ip=binding["ip"],
                        valid_from=_to_datetime(binding["valid_from"]),
                        valid_to=_to_datetime(binding["valid_to"]) if binding.get("valid_to") else None,
                    )
                    for binding in raw.get("bindings", [])
                ],
            )
            registry._records[record.host_id] = record
            if record.mac:
                registry._by_mac[record.mac] = record.host_id
            if record.hostname:
                registry._by_hostname[record.hostname.lower()] = record.host_id
        return registry

    @staticmethod
    def _record_to_dict(record: _Record) -> dict:
        return {
            "host_id": record.host_id,
            "ip_addresses": list(record.ip_addresses),
            "hostname": record.hostname,
            "subnet": record.subnet,
            "first_seen": record.first_seen.isoformat() if record.first_seen else None,
            "last_seen": record.last_seen.isoformat() if record.last_seen else None,
            "mac": record.mac,
            "os_guess": record.os_guess,
            "metadata": dict(record.metadata),
            "bindings": [
                {
                    "ip": binding.ip,
                    "valid_from": binding.valid_from.isoformat(),
                    "valid_to": binding.valid_to.isoformat() if binding.valid_to else None,
                }
                for binding in record.bindings
            ],
        }

    def _match(self, mac: str | None, hostname: str | None, ip: str | None, ts: datetime) -> str | None:
        if mac:
            return self._by_mac.get(mac.lower())
        if hostname:
            return self._by_hostname.get(hostname.lower())
        if ip:
            for record in self._records.values():
                for binding in record.bindings:
                    if binding.ip != ip:
                        continue
                    if binding.valid_to is None:
                        return record.host_id
        return None

    def _bind_ip(self, record: _Record, ip: str, first_seen: datetime, last_seen: datetime) -> None:
        if ip not in record.ip_addresses:
            record.ip_addresses.append(ip)

        for binding in record.bindings:
            if binding.ip == ip and binding.valid_to is None:
                if last_seen > binding.valid_from:
                    binding.valid_from = min(binding.valid_from, first_seen)
                return

        for other in self._records.values():
            if other is record:
                continue
            for binding in other.bindings:
                if binding.ip == ip and binding.valid_to is None:
                    binding.valid_to = first_seen

        record.bindings.append(_Binding(ip=ip, valid_from=first_seen, valid_to=None))

    @staticmethod
    def _to_schema(record: _Record) -> Host:
        metadata = dict(record.metadata)
        if record.mac:
            metadata.setdefault("mac", record.mac)
        return Host(
            host_id=record.host_id,
            ip_addresses=list(record.ip_addresses),
            hostname=record.hostname,
            subnet=record.subnet,
            first_seen=record.first_seen or datetime.now(timezone.utc),
            last_seen=record.last_seen or record.first_seen or datetime.now(timezone.utc),
            os_guess=record.os_guess,
            metadata=metadata,
            schema_version=SCHEMA_VERSION,
        )
