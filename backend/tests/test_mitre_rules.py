"""Tests for the declarative MITRE rules detector."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from lated.common.schemas import CanonicalFlow, DetectionKind, DetectorName, Protocol
from lated.detection.rules import MITRERulesDetector, load_rules
from lated.detection.rules.rule_engine import _Bucket
from lated.detection.rules.rule_loader import Condition, Rule


# ---------------------------------------------------------------- helpers

def _flow(
    *,
    src: str = "host-A",
    dst: str = "host-B",
    dst_port: int = 445,
    ts: datetime | None = None,
    enrichment: dict | None = None,
) -> CanonicalFlow:
    return CanonicalFlow(
        flow_id="f1",
        ts=ts or datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        src_host=src,
        dst_host=dst,
        src_port=49152,
        dst_port=dst_port,
        protocol=Protocol.TCP,
        duration=0.1,
        packet_count=4,
        byte_count=400,
        source_sensor="zeek",
        enrichment=enrichment or {},
    )


# ------------------------------------------------------------------ loader

def test_loader_parses_minimal_rule(tmp_path: Path) -> None:
    yaml_doc = dedent(
        """
        rules:
          - id: TEST-1
            description: "Admin share access"
            mitre_tags: ["T1021.002"]
            score: 0.7
            subject: src
            signals: ["smb_admin"]
            conditions:
              - field: enrichment.admin_share
                op: equals
                value: true
        """
    )
    path = tmp_path / "rules.yaml"
    path.write_text(yaml_doc, encoding="utf-8")
    rules = load_rules(path)
    assert len(rules) == 1
    rule = rules[0]
    assert rule.id == "TEST-1"
    assert rule.mitre_tags == ("T1021.002",)
    assert rule.score == 0.7
    assert rule.conditions[0] == Condition(
        field="enrichment.admin_share", op="equals", value=True,
    )


def test_loader_rejects_unknown_op(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        "rules:\n  - id: BAD\n    conditions:\n      - field: x\n        op: nope\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_rules(path)


# ------------------------------------------------------------------ engine

def _ruleset() -> list[Rule]:
    return [
        Rule(
            id="LM-001",
            description="admin share",
            mitre_tags=("T1021.002",),
            score=0.6,
            subject="src",
            signals=("smb_admin_share_access",),
            conditions=(
                Condition("enrichment.admin_share", "equals", True),
                Condition("dst_port", "in", [139, 445]),
            ),
        ),
        Rule(
            id="LM-003",
            description="dcsync",
            mitre_tags=("T1003.006",),
            score=0.95,
            subject="src",
            signals=("dcsync_drsuapi",),
            conditions=(
                Condition("enrichment.dce_endpoints", "contains", "drsuapi"),
            ),
        ),
    ]


def test_engine_matches_admin_share_smb() -> None:
    det = MITRERulesDetector(_ruleset(), window_seconds=60)
    flow = _flow(enrichment={"admin_share": True})
    out = det.run([flow])
    assert len(out) == 1
    hit = out[0]
    assert hit.detector == DetectorName.MITRE_RULES.value
    assert hit.kind == DetectionKind.LM.value
    assert hit.subject_host == "host-A"
    assert hit.score == pytest.approx(0.6)
    assert "smb_admin_share_access" in hit.triggered_signals
    assert "T1021.002" in hit.mitre_tags


def test_engine_skips_when_admin_share_false() -> None:
    det = MITRERulesDetector(_ruleset(), window_seconds=60)
    flow = _flow(enrichment={"admin_share": False})
    assert det.run([flow]) == []


def test_engine_dcsync_contains_drsuapi() -> None:
    det = MITRERulesDetector(_ruleset(), window_seconds=60)
    flow = _flow(dst_port=135, enrichment={"dce_endpoints": ["drsuapi", "samr"]})
    out = det.run([flow])
    assert len(out) == 1
    assert out[0].score == pytest.approx(0.95)
    assert "T1003.006" in out[0].mitre_tags


def test_engine_aggregates_multiple_rules_into_one_hit() -> None:
    # Both LM-001 and LM-003 fire on the same flow → one ReconScore with
    # max score and union of signals/tags.
    det = MITRERulesDetector(_ruleset(), window_seconds=60)
    flow = _flow(
        dst_port=445,
        enrichment={"admin_share": True, "dce_endpoints": ["drsuapi"]},
    )
    out = det.run([flow])
    assert len(out) == 1
    hit = out[0]
    assert hit.score == pytest.approx(0.95)  # max wins
    assert {"smb_admin_share_access", "dcsync_drsuapi"} <= set(hit.triggered_signals)
    assert {"T1021.002", "T1003.006"} <= set(hit.mitre_tags)


def test_engine_windows_align_per_60s() -> None:
    det = MITRERulesDetector(_ruleset(), window_seconds=60)
    t = datetime(2025, 1, 1, 12, 0, 15, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 12, 1, 30, tzinfo=timezone.utc)
    f1 = _flow(ts=t, enrichment={"admin_share": True})
    f2 = _flow(ts=t2, enrichment={"admin_share": True})
    out = det.run([f1, f2])
    assert len(out) == 2
    assert out[0].window_start.replace(tzinfo=timezone.utc) == datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert out[1].window_start.replace(tzinfo=timezone.utc) == datetime(2025, 1, 1, 12, 1, 0, tzinfo=timezone.utc)


def test_engine_extension_match_via_contains_any() -> None:
    rule = Rule(
        id="LM-009",
        description="script drop",
        mitre_tags=("T1059.001",),
        score=0.7,
        subject="src",
        signals=("smb_script_drop",),
        conditions=(
            Condition("enrichment.admin_share", "equals", True),
            Condition(
                "enrichment.smb_files_names",
                "contains_any",
                [".ps1", ".bat"],
            ),
        ),
    )
    det = MITRERulesDetector([rule], window_seconds=60)
    flow = _flow(enrichment={
        "admin_share": True,
        "smb_files_names": ["payload.PS1", "notes.txt"],
    })
    out = det.run([flow])
    assert len(out) == 1
    assert "T1059.001" in out[0].mitre_tags


def test_engine_hostname_differs_signals_pth() -> None:
    rule = Rule(
        id="LM-006",
        description="pth",
        mitre_tags=("T1550.002",),
        score=0.75,
        subject="src",
        signals=("ntlm_hostname_mismatch",),
        conditions=(
            Condition("enrichment.has_ntlm", "equals", True),
            Condition("enrichment.ntlm_success", "equals", True),
            Condition("enrichment.ntlm_client_hostname", "hostname_differs"),
        ),
    )
    det = MITRERulesDetector([rule], window_seconds=60, host_registry=None)
    flow = _flow(
        src="WS07",
        enrichment={
            "has_ntlm": True,
            "ntlm_success": True,
            "ntlm_client_hostname": "SOMETHING-ELSE",
        },
    )
    out = det.run([flow])
    assert len(out) == 1
    assert "T1550.002" in out[0].mitre_tags


def test_bucket_aggregates_max_and_unions() -> None:
    bucket = _Bucket()
    r1 = Rule("A", "", ("T1",), 0.3, "src", ("s1",), ())
    r2 = Rule("B", "", ("T2",), 0.8, "src", ("s2",), ())
    bucket.apply(r1, "target-1", 445)
    bucket.apply(r2, "target-2", 135)
    assert bucket.score == pytest.approx(0.8)
    assert bucket.signals == {"s1", "s2"}
    assert bucket.mitre_tags == {"T1", "T2"}
    assert bucket.targets == {"target-1", "target-2"}
    assert bucket.ports == {445, 135}


# ------------------------------------------------------ bundled catalog

def test_bundled_catalog_loads_and_has_known_rules() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    catalog = backend_root / "config" / "detection_rules.yaml"
    rules = load_rules(catalog)
    ids = {r.id for r in rules}
    assert {"LM-001", "LM-002", "LM-003", "LM-004"} <= ids
    # Each rule must have at least one MITRE tag.
    assert all(r.mitre_tags for r in rules)
