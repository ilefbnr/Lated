# =============================================================================
# lated.common.network_topology — declarative network zoning & asset criticality
# =============================================================================
#
# PURPOSE
# -------
# Single source of truth for "where does this IP / host belong in our network?"
# Replaces the RFC 1918-only `is_private` heuristic that was previously hard-coded
# in graph_repository / realtime_graph.
#
# Real SOC tools (Splunk ES networks.csv, Zeek Site::local_nets, Suricata HOME_NET,
# Defender for Identity AD-Sites import) all rely on an admin-provided topology
# map. LateD now follows the same pattern.
#
# CLASSIFICATION CONTRACT
# -----------------------
# Given an IP, the topology returns a HostClassification with:
#   - zone   : corporate | dmz | datacenter | iot | ot | public_owned |
#              partner | external | unknown
#   - trust  : trusted | semi_trusted | untrusted
#   - sensitive : True for assets the admin flagged as critical-by-subnet
#
# Lookup is longest-prefix-match (most specific CIDR wins), so a /32 carve-out
# for a single critical host can override a broader /16 corporate range.
#
# FALLBACK
# --------
# IPs that match no configured CIDR fall back to RFC 1918:
#   - private  -> corporate / trusted   (legacy behaviour preserved)
#   - public   -> external  / untrusted
# An empty config therefore reproduces the old behaviour exactly — this change
# is fully backwards-compatible.
# =============================================================================

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Zone(str, Enum):
    CORPORATE = "corporate"
    DMZ = "dmz"
    DATACENTER = "datacenter"
    IOT = "iot"
    OT = "ot"
    PUBLIC_OWNED = "public_owned"   # IPs publiques détenues par l'entreprise (cloud, NAT externe)
    PARTNER = "partner"             # VPN site-to-site, MPLS, fournisseurs trusted
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class Trust(str, Enum):
    TRUSTED = "trusted"
    SEMI_TRUSTED = "semi_trusted"
    UNTRUSTED = "untrusted"


ALL_ZONES: frozenset[str] = frozenset(z.value for z in Zone)
ALL_TRUSTS: frozenset[str] = frozenset(t.value for t in Trust)


@dataclass(frozen=True)
class ZoneEntry:
    """A single CIDR -> (zone, trust) mapping, with optional sensitivity flag."""
    network: ipaddress.IPv4Network | ipaddress.IPv6Network
    zone: Zone
    trust: Trust
    name: str | None = None
    sensitive: bool = False


@dataclass(frozen=True)
class HostClassification:
    """Result of classifying an IP or host."""
    zone: Zone
    trust: Trust
    sensitive: bool
    matched_cidr: str | None  # None means RFC 1918 fallback was used


# Sentinels for the "no config" case — pre-allocated to avoid per-call churn.
_FALLBACK_INTERNAL = HostClassification(Zone.CORPORATE, Trust.TRUSTED, False, None)
_FALLBACK_EXTERNAL = HostClassification(Zone.EXTERNAL, Trust.UNTRUSTED, False, None)
_FALLBACK_UNKNOWN = HostClassification(Zone.UNKNOWN, Trust.SEMI_TRUSTED, False, None)


class NetworkTopology:
    """
    Resolves IPs to network zones using admin-provided CIDR rules.

    Lookup strategy: longest-prefix-match. The most specific rule wins, so
    operators can carve out a /32 critical asset inside a broader /16 zone.
    """

    def __init__(
        self,
        entries: Iterable[ZoneEntry] = (),
        critical_assets: Iterable[str] = (),
    ) -> None:
        # Sort by prefix length descending → longest-prefix-match by linear scan.
        # (Number of zones is small — < 100 typical — so a trie is overkill.)
        self._entries: tuple[ZoneEntry, ...] = tuple(
            sorted(entries, key=lambda e: e.network.prefixlen, reverse=True)
        )
        self._critical_assets: frozenset[str] = frozenset(critical_assets)

    # ------------------------------------------------------------------ lookup
    def classify_ip(self, ip: str) -> HostClassification:
        try:
            addr = ipaddress.ip_address(str(ip))
        except (ValueError, TypeError):
            return _FALLBACK_UNKNOWN

        for entry in self._entries:
            if addr.version != entry.network.version:
                continue
            if addr in entry.network:
                return HostClassification(
                    zone=entry.zone,
                    trust=entry.trust,
                    sensitive=entry.sensitive,
                    matched_cidr=str(entry.network),
                )

        # No explicit rule — fall back to RFC 1918 semantics.
        if addr.is_private:
            return _FALLBACK_INTERNAL
        return _FALLBACK_EXTERNAL

    def classify_host(self, ip_addresses: Iterable[str]) -> HostClassification:
        """
        Classify a host that may carry multiple IPs (multi-homed, dual-stack).

        Strategy: the first explicit (non-fallback) classification wins.
        If no IP matches any rule, the most "internal" fallback wins
        (a host with one private IP is internal, even if it also has a public one).
        """
        explicit: HostClassification | None = None
        any_private = False
        any_public = False
        has_ip = False

        for ip in ip_addresses:
            has_ip = True
            c = self.classify_ip(ip)
            if c.matched_cidr is not None and explicit is None:
                explicit = c
            elif c.matched_cidr is None:
                if c.zone == Zone.CORPORATE:
                    any_private = True
                elif c.zone == Zone.EXTERNAL:
                    any_public = True

        if explicit is not None:
            return explicit
        if not has_ip:
            return _FALLBACK_UNKNOWN
        if any_private:
            return _FALLBACK_INTERNAL
        if any_public:
            return _FALLBACK_EXTERNAL
        return _FALLBACK_UNKNOWN

    # ------------------------------------------------------------- convenience
    def is_external_host(self, ip_addresses: Iterable[str]) -> bool:
        return self.classify_host(ip_addresses).zone == Zone.EXTERNAL

    def is_external_edge(
        self,
        src_ips: Iterable[str],
        dst_ips: Iterable[str],
    ) -> bool:
        return self.is_external_host(src_ips) or self.is_external_host(dst_ips)

    def is_critical_asset(
        self,
        host_id: str | None = None,
        ip_addresses: Iterable[str] | None = None,
    ) -> bool:
        if host_id is not None and host_id in self._critical_assets:
            return True
        ips = list(ip_addresses or [])
        for ip in ips:
            if ip in self._critical_assets:
                return True
        if ips and self.classify_host(ips).sensitive:
            return True
        return False

    # ------------------------------------------------------------ introspection
    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def critical_asset_ids(self) -> frozenset[str]:
        return self._critical_assets

    # ----------------------------------------------------------------- factories
    @classmethod
    def default(cls) -> "NetworkTopology":
        """Empty topology — pure RFC 1918 fallback. Used when config is absent."""
        return cls(entries=(), critical_assets=())


def parse_zone_entries(
    raw_zones: list[dict],
    *,
    error_prefix: str = "network_topology.zones",
) -> list[ZoneEntry]:
    """
    Validate and parse a list of zone-rule dicts (as loaded from YAML).

    Raises ValueError on the first invalid entry — caller is expected to wrap
    this in a ConfigError to match the rest of the config loader's contract.
    """
    parsed: list[ZoneEntry] = []
    for index, raw in enumerate(raw_zones):
        where = f"{error_prefix}[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{where}: each zone entry must be a mapping.")

        cidr = raw.get("cidr")
        if not isinstance(cidr, str) or not cidr.strip():
            raise ValueError(f"{where}.cidr: missing or not a string.")
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            raise ValueError(f"{where}.cidr: invalid CIDR '{cidr}' ({exc}).") from exc

        zone_raw = raw.get("zone")
        if zone_raw not in ALL_ZONES:
            raise ValueError(
                f"{where}.zone: '{zone_raw}' is not one of {sorted(ALL_ZONES)}."
            )

        trust_raw = raw.get("trust", "trusted")
        if trust_raw not in ALL_TRUSTS:
            raise ValueError(
                f"{where}.trust: '{trust_raw}' is not one of {sorted(ALL_TRUSTS)}."
            )

        name = raw.get("name")
        if name is not None and not isinstance(name, str):
            raise ValueError(f"{where}.name: must be a string when provided.")

        sensitive = raw.get("sensitive", False)
        if not isinstance(sensitive, bool):
            raise ValueError(f"{where}.sensitive: must be a boolean.")

        parsed.append(
            ZoneEntry(
                network=network,
                zone=Zone(zone_raw),
                trust=Trust(trust_raw),
                name=name,
                sensitive=sensitive,
            )
        )
    return parsed
