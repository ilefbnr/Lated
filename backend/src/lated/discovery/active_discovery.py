# =============================================================================
# lated.discovery.active_discovery — opt-in active probing
# =============================================================================
#
# Implements a real (but small) active discovery pass using TCP connect
# probes. We use TCP connect rather than raw SYN because it works on every
# OS without elevated privileges — pragmatic for an MVP.
#
# Safety properties:
#   - Refuses to scan unless `active_scan_enabled=True`.
#   - Rate-limited: at most `rate_limit_pps` probes per second per process.
#   - Bounded port set (caller-supplied; defaults to a tiny well-known set).
#   - Per-probe timeout to avoid hanging on filtered hosts.
#   - The probe function is injectable for tests.
# =============================================================================

from __future__ import annotations

import socket
import time
from datetime import datetime, timezone
from typing import Callable, Iterable


DEFAULT_PROBE_PORTS = (22, 80, 135, 139, 443, 445)
DEFAULT_PROBE_TIMEOUT_SECONDS = 0.2


class ActiveDiscoveryDisabled(RuntimeError):
    """Raised when active scanning is requested while disabled by config."""


def _tcp_connect_probe(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


class ActiveDiscovery:
    """Rate-limited TCP-connect active discovery."""

    def __init__(
        self,
        enabled: bool,
        host_registry,
        rate_limit_pps: int = 10,
        ports: Iterable[int] = DEFAULT_PROBE_PORTS,
        timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
        probe_fn: Callable[[str, int, float], bool] | None = None,
    ):
        self.enabled = bool(enabled)
        self.host_registry = host_registry
        self.rate_limit_pps = max(1, int(rate_limit_pps))
        self.ports = tuple(int(p) for p in ports)
        self.timeout_seconds = float(timeout_seconds)
        self._probe_fn = probe_fn or _tcp_connect_probe
        self._min_interval = 1.0 / self.rate_limit_pps

    def scan(self, targets: list[str]) -> list[str]:
        """Probe each target IP. Returns host_ids of responders.

        Each responder is upserted into the registry with metadata
        {"active_response": true, "open_ports": [...]} for downstream use.
        """
        if not self.enabled:
            raise ActiveDiscoveryDisabled(
                "Active discovery requested but discovery.active_scan_enabled is false."
            )

        responders: list[str] = []
        last_probe_at = 0.0
        for ip in targets:
            open_ports: list[int] = []
            for port in self.ports:
                self._respect_rate_limit(last_probe_at)
                last_probe_at = time.monotonic()
                if self._probe_fn(ip, port, self.timeout_seconds):
                    open_ports.append(port)
            if not open_ports:
                continue
            now = datetime.now(timezone.utc)
            host_id = self.host_registry.upsert(
                {
                    "ip": ip,
                    "first_seen": now,
                    "last_seen": now,
                    "metadata": {"active_response": True, "open_ports": open_ports},
                }
            )
            responders.append(host_id)
        return responders

    def _respect_rate_limit(self, last_probe_at: float) -> None:
        if last_probe_at == 0.0:
            return
        elapsed = time.monotonic() - last_probe_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
