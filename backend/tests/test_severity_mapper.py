# =============================================================================
# tests/test_severity_mapper.py — Severity escalation rules
# =============================================================================

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.network_topology import NetworkTopology, parse_zone_entries  # noqa: E402
from lated.common.schemas import Severity  # noqa: E402
from lated.supervision.alerts.severity_mapper import SeverityMapper  # noqa: E402


def test_score_only_mapping():
    m = SeverityMapper()
    assert m.map(0.05) == Severity.INFO.value
    assert m.map(0.45) == Severity.LOW.value
    assert m.map(0.65) == Severity.MEDIUM.value
    assert m.map(0.80) == Severity.HIGH.value
    assert m.map(0.95) == Severity.CRITICAL.value


def test_static_critical_asset_bumps_severity():
    m = SeverityMapper(critical_asset_ids={"host-DC01"})
    # Base would be LOW; bumped to MEDIUM by critical asset
    assert m.map(0.45, host_id="host-DC01") == Severity.MEDIUM.value
    # Other host: no bump
    assert m.map(0.45, host_id="host-WS01") == Severity.LOW.value


def test_path_length_and_critical_compound():
    m = SeverityMapper(critical_asset_ids={"host-DC01"})
    # LOW + 1 (path>=3) + 1 (critical) = HIGH
    assert m.map(0.45, host_id="host-DC01", path_length=4) == Severity.HIGH.value


def test_callable_used_when_set_misses():
    topo = NetworkTopology(critical_assets=["host-DC01"])

    fake_registry = {
        "host-DC01": ["10.0.0.4"],
        "host-WS01": ["10.0.0.50"],
    }

    def is_crit(host_id: str) -> bool:
        return topo.is_critical_asset(host_id, fake_registry.get(host_id))

    m = SeverityMapper(is_critical_host=is_crit)

    assert m.map(0.45, host_id="host-DC01") == Severity.MEDIUM.value
    assert m.map(0.45, host_id="host-WS01") == Severity.LOW.value


def test_callable_swallows_failure_gracefully():
    def boom(host_id: str) -> bool:
        raise RuntimeError("registry offline")

    m = SeverityMapper(is_critical_host=boom)
    # Must not raise, severity stays at base
    assert m.map(0.45, host_id="anything") == Severity.LOW.value


def test_sensitive_zone_via_topology_promotes_severity():
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

    fake_registry = {"host-DB": ["10.50.0.10"]}

    def is_crit(host_id: str) -> bool:
        return topo.is_critical_asset(host_id, fake_registry.get(host_id))

    m = SeverityMapper(is_critical_host=is_crit)
    # Host sits in a sensitive zone -> bump from LOW to MEDIUM
    assert m.map(0.45, host_id="host-DB") == Severity.MEDIUM.value


def test_ceiling_at_critical():
    m = SeverityMapper(critical_asset_ids={"host-DC01"})
    # Already CRITICAL, two bumps shouldn't overflow
    assert m.map(0.95, host_id="host-DC01", path_length=8) == Severity.CRITICAL.value
