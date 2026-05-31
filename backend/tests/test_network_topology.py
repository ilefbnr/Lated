# =============================================================================
# tests/test_network_topology.py — declarative zoning classifier
# =============================================================================

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.network_topology import (  # noqa: E402
    NetworkTopology,
    Trust,
    Zone,
    parse_zone_entries,
)


# ----------------------------------------------------------------- fallback
def test_default_topology_falls_back_to_rfc1918():
    topo = NetworkTopology.default()

    assert topo.classify_ip("10.0.0.1").zone == Zone.CORPORATE
    assert topo.classify_ip("192.168.1.50").zone == Zone.CORPORATE
    assert topo.classify_ip("172.16.5.5").zone == Zone.CORPORATE
    assert topo.classify_ip("8.8.8.8").zone == Zone.EXTERNAL
    assert topo.classify_ip("1.1.1.1").zone == Zone.EXTERNAL


def test_default_topology_marks_unknown_for_invalid_ip():
    topo = NetworkTopology.default()
    assert topo.classify_ip("not-an-ip").zone == Zone.UNKNOWN
    assert topo.classify_ip("").zone == Zone.UNKNOWN


# ----------------------------------------------------------------- explicit rules
def test_longest_prefix_match_wins():
    entries = parse_zone_entries(
        [
            {"cidr": "10.0.0.0/8", "zone": "corporate", "trust": "trusted"},
            {
                "cidr": "10.50.0.0/24",
                "zone": "datacenter",
                "trust": "trusted",
                "sensitive": True,
            },
        ]
    )
    topo = NetworkTopology(entries=entries)

    # /24 wins over /8
    inside = topo.classify_ip("10.50.0.10")
    assert inside.zone == Zone.DATACENTER
    assert inside.sensitive is True

    # Outside the /24 → falls back to /8
    outside = topo.classify_ip("10.10.0.10")
    assert outside.zone == Zone.CORPORATE
    assert outside.sensitive is False


def test_public_owned_overrides_external_fallback():
    # Pick a real public range (Cloudflare 1.1.1.0/24 is routable public space)
    entries = parse_zone_entries(
        [{"cidr": "1.1.1.0/24", "zone": "public_owned", "trust": "trusted"}]
    )
    topo = NetworkTopology(entries=entries)

    assert topo.classify_ip("1.1.1.5").zone == Zone.PUBLIC_OWNED
    assert topo.is_external_host(["1.1.1.5"]) is False
    # An IP outside the rule still flows to the public-IP fallback
    assert topo.is_external_host(["8.8.8.8"]) is True


# ------------------------------------------------------------- multi-IP host
def test_multi_homed_host_uses_first_explicit_match():
    entries = parse_zone_entries(
        [{"cidr": "10.0.0.0/8", "zone": "corporate", "trust": "trusted"}]
    )
    topo = NetworkTopology(entries=entries)
    c = topo.classify_host(["8.8.8.8", "10.0.0.5"])
    assert c.zone == Zone.CORPORATE
    assert c.matched_cidr == "10.0.0.0/8"


def test_empty_ip_list_classifies_unknown():
    topo = NetworkTopology.default()
    assert topo.classify_host([]).zone == Zone.UNKNOWN


# ---------------------------------------------------------------- edges
def test_edge_external_when_any_endpoint_external():
    topo = NetworkTopology.default()
    assert topo.is_external_edge(["10.0.0.1"], ["10.0.0.2"]) is False
    assert topo.is_external_edge(["10.0.0.1"], ["8.8.8.8"]) is True
    assert topo.is_external_edge(["8.8.8.8"], ["1.1.1.1"]) is True


# ---------------------------------------------------------------- critical assets
def test_critical_asset_by_host_id_and_ip():
    topo = NetworkTopology(critical_assets=["host-DC01", "10.50.0.10"])
    assert topo.is_critical_asset(host_id="host-DC01") is True
    assert topo.is_critical_asset(ip_addresses=["10.50.0.10"]) is True
    assert topo.is_critical_asset(host_id="host-WS01") is False


def test_sensitive_zone_implies_critical():
    entries = parse_zone_entries(
        [
            {
                "cidr": "10.50.0.0/24",
                "zone": "datacenter",
                "trust": "trusted",
                "sensitive": True,
            }
        ]
    )
    topo = NetworkTopology(entries=entries)
    assert topo.is_critical_asset(ip_addresses=["10.50.0.7"]) is True
    assert topo.is_critical_asset(ip_addresses=["10.10.0.7"]) is False


# ---------------------------------------------------------------- validation
def test_parse_zone_entries_rejects_invalid_cidr():
    with pytest.raises(ValueError, match="invalid CIDR"):
        parse_zone_entries([{"cidr": "not-a-cidr", "zone": "corporate"}])


def test_parse_zone_entries_rejects_unknown_zone():
    with pytest.raises(ValueError, match="not one of"):
        parse_zone_entries([{"cidr": "10.0.0.0/8", "zone": "intranet"}])


def test_parse_zone_entries_rejects_unknown_trust():
    with pytest.raises(ValueError, match="not one of"):
        parse_zone_entries(
            [{"cidr": "10.0.0.0/8", "zone": "corporate", "trust": "vouched"}]
        )


def test_parse_zone_entries_defaults_trust_to_trusted():
    entries = parse_zone_entries([{"cidr": "10.0.0.0/8", "zone": "corporate"}])
    assert entries[0].trust == Trust.TRUSTED
