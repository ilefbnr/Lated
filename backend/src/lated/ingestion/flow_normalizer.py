# =============================================================================
# lated.ingestion.flow_normalizer — sensor-specific -> canonical
# =============================================================================
#
# Per-sensor key remapping + IP -> host_id resolution via the HostRegistry.
# When an IP is unknown, it is upserted as an IP-only candidate so downstream
# code never deals with a raw IP — only canonical host_ids.
# =============================================================================

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


PROTOCOL_NORMALIZATION = {
    "tcp": "tcp",
    "udp": "udp",
    "icmp": "icmp",
}


class FlowNormalizer:
    """Maps parser-specific keys to canonical keys."""

    def __init__(self, host_registry):
        self.host_registry = host_registry

    def normalize(self, raw: dict[str, Any], source_sensor: str) -> dict[str, Any]:
        ts = self._coerce_ts(raw.get("ts"))
        src_ip = raw.get("src_ip") or raw.get("id.orig_h")
        dst_ip = raw.get("dst_ip") or raw.get("id.resp_h")
        src_port = self._coerce_int(raw.get("src_port", raw.get("id.orig_p")))
        dst_port = self._coerce_int(raw.get("dst_port", raw.get("id.resp_p")))

        protocol_raw = str(raw.get("protocol") or raw.get("proto") or "other").lower()
        protocol = PROTOCOL_NORMALIZATION.get(protocol_raw, "other")

        duration = self._coerce_float(raw.get("duration"))
        packet_count = self._sum_int(raw.get("packet_count"), raw.get("orig_pkts"), raw.get("resp_pkts"))
        byte_count = self._sum_int(
            raw.get("byte_count"),
            raw.get("orig_ip_bytes"),
            raw.get("resp_ip_bytes"),
            raw.get("orig_bytes"),
            raw.get("resp_bytes"),
        )

        src_host = self._resolve(src_ip, ts) if src_ip else None
        dst_host = self._resolve(dst_ip, ts) if dst_ip else None

        flow_id = raw.get("flow_id") or raw.get("uid") or self._deterministic_id(
            src_ip, dst_ip, src_port, dst_port, ts
        )

        return {
            "flow_id": flow_id,
            "ts": ts.isoformat() if isinstance(ts, datetime) else ts,
            "src_host": src_host,
            "dst_host": dst_host,
            "src_port": src_port if src_port is not None else 0,
            "dst_port": dst_port if dst_port is not None else 0,
            "protocol": protocol,
            "duration": duration if duration is not None else 0.0,
            "packet_count": packet_count if packet_count is not None else 0,
            "byte_count": byte_count if byte_count is not None else 0,
            "source_sensor": source_sensor,
        }

    def _resolve(self, ip: str, ts: datetime | None) -> str | None:
        when = ts or datetime.now(timezone.utc)
        try:
            return self.host_registry.resolve(ip, when)
        except KeyError:
            return self.host_registry.upsert({"ip": ip, "first_seen": when, "last_seen": when})

    @staticmethod
    def _coerce_ts(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return None

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _sum_int(*values: Any) -> int | None:
        total = 0
        seen_any = False
        for value in values:
            if value is None:
                continue
            try:
                total += int(value)
                seen_any = True
            except (TypeError, ValueError):
                continue
        return total if seen_any else None

    @staticmethod
    def _deterministic_id(src_ip, dst_ip, src_port, dst_port, ts) -> str:
        key = f"{src_ip}|{dst_ip}|{src_port}|{dst_port}|{ts.isoformat() if isinstance(ts, datetime) else ts}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return f"flow-{digest}"
