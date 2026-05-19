# =============================================================================
# lated.ingestion.flow_validator — schema + range enforcement
# =============================================================================
#
# Lightweight pre-check before the canonical Pydantic model. Catches obvious
# defects (missing keys, out-of-range ports, negative counters) so the stream
# can move on without the cost of a ValidationError trace.
#
# Returns (is_valid, reason). Reason strings are logged but never surfaced
# to clients.
# =============================================================================

from __future__ import annotations

from datetime import datetime
from typing import Any


REQUIRED_KEYS = (
    "flow_id",
    "ts",
    "src_host",
    "dst_host",
    "src_port",
    "dst_port",
    "protocol",
    "duration",
    "packet_count",
    "byte_count",
    "source_sensor",
)


class FlowValidator:
    """Validates normalized flow dicts against CanonicalFlow invariants."""

    def is_valid(self, flow: dict[str, Any]) -> tuple[bool, str | None]:
        for key in REQUIRED_KEYS:
            if key not in flow:
                return False, f"missing_key:{key}"
            if flow[key] is None and key not in {"src_port", "dst_port"}:
                return False, f"null_value:{key}"

        for port_key in ("src_port", "dst_port"):
            port = flow.get(port_key)
            if not isinstance(port, int) or isinstance(port, bool):
                return False, f"port_type:{port_key}"
            if port < 0 or port > 65535:
                return False, f"port_range:{port_key}"

        for count_key in ("packet_count", "byte_count"):
            value = flow.get(count_key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return False, f"count_invalid:{count_key}"

        duration = flow.get("duration")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
            return False, "duration_invalid"

        if not isinstance(flow["src_host"], str) or not flow["src_host"]:
            return False, "src_host_invalid"
        if not isinstance(flow["dst_host"], str) or not flow["dst_host"]:
            return False, "dst_host_invalid"

        if not isinstance(flow["ts"], (str, datetime)):
            return False, "ts_invalid"

        return True, None
