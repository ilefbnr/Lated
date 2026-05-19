# =============================================================================
# lated.discovery.discovery_service — orchestrator
# =============================================================================
#
# Reads config.discovery, loads any previously persisted HostRegistry so host
# identity history is preserved across runs, runs the passive pipeline, runs
# active probing when explicitly enabled, builds the BaselineGraph and
# persists it (with an HMAC signature in production).
# =============================================================================

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from lated.common.exceptions import ConfigError

from lated.discovery.active_discovery import ActiveDiscovery
from lated.discovery.baseline_graph import BaselineGraph
from lated.discovery.host_registry import HostRegistry
from lated.discovery.passive_discovery import PassiveDiscovery
from lated.discovery.topology_builder import TopologyBuilder


DEFAULT_BASELINE_PATH = Path("data/baseline/latest.json")
DEFAULT_REGISTRY_PATH = Path("data/discovery/host_registry.json")
DEV_FALLBACK_SECRET = "lated-dev-baseline-key"


class DiscoveryService:
    """Discovery pipeline orchestrator."""

    def __init__(
        self,
        config: Any,
        source_path: str | Path,
        baseline_path: str | Path = DEFAULT_BASELINE_PATH,
        registry_path: str | Path = DEFAULT_REGISTRY_PATH,
        active_targets: list[str] | None = None,
        env: str = "development",
        secret_key: str | None = None,
        active_scanner: ActiveDiscovery | None = None,
    ):
        self.config = config
        self.source_path = Path(source_path)
        self.baseline_path = Path(baseline_path)
        self.registry_path = Path(registry_path)
        self.env = str(env)
        self.secret_key = secret_key or os.environ.get("LATED_SECRET_KEY") or (
            DEV_FALLBACK_SECRET if self.env != "production" else None
        )
        if self.env == "production" and not self.secret_key:
            raise ConfigError("Production discovery requires LATED_SECRET_KEY.")

        self.host_registry = self._load_or_create_registry(
            liveness_seconds=int(getattr(config, "passive_window_seconds", 86400))
        )
        self.passive = PassiveDiscovery(self.host_registry, self.source_path)
        self.topology_builder = TopologyBuilder()
        self.active = active_scanner or ActiveDiscovery(
            enabled=bool(getattr(config, "active_scan_enabled", False)),
            host_registry=self.host_registry,
        )
        self._active_targets = active_targets

    def run(self) -> BaselineGraph:
        mode = str(getattr(self.config, "mode", "passive"))
        if mode not in {"passive", "active", "hybrid"}:
            raise ConfigError(f"Unsupported discovery mode: {mode}")

        observation = self.passive.observe()

        if mode in {"active", "hybrid"}:
            if not self.active.enabled:
                raise ConfigError(
                    f"discovery.mode={mode} requires discovery.active_scan_enabled=true."
                )
            targets = self._active_targets if self._active_targets is not None else self._derive_targets(observation)
            self.active.scan(targets)

        topology = self.topology_builder.build(self.host_registry.list(), observation.edges)
        baseline = BaselineGraph.build(self.host_registry, topology)
        baseline.save(self.baseline_path, secret_key=self.secret_key, env=self.env)
        self.host_registry.save(self.registry_path)
        return baseline

    def _load_or_create_registry(self, liveness_seconds: int) -> HostRegistry:
        if self.registry_path.exists():
            try:
                return HostRegistry.load(self.registry_path)
            except (ValueError, KeyError):
                # Corrupted or incompatible — start fresh rather than crash boot.
                pass
        return HostRegistry(liveness_seconds=liveness_seconds)

    @staticmethod
    def _derive_targets(observation) -> list[str]:
        seen: list[str] = []
        for host in observation.hosts:
            for ip in host.ip_addresses:
                if ip not in seen:
                    seen.append(ip)
        return seen
