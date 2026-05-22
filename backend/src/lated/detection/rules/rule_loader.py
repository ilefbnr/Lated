# =============================================================================
# lated.detection.rules.rule_loader — YAML rule catalog loader
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_OPS = frozenset({
    "equals", "not_equals", "in", "not_in",
    "contains", "contains_any",
    "greater_than", "less_than",
    "exists", "hostname_differs",
})


@dataclass(frozen=True)
class Condition:
    field: str
    op: str
    value: Any = None


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    mitre_tags: tuple[str, ...]
    score: float
    subject: str            # "src" | "dst"
    signals: tuple[str, ...]
    conditions: tuple[Condition, ...]


def load_rules(path: str | Path) -> list[Rule]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Rule catalog not found: {p}")
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list):
        raise ValueError(f"Rule catalog {p} must contain a top-level `rules:` list")

    parsed: list[Rule] = []
    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            raise ValueError(f"Rule #{index} is not a mapping")
        rid = str(raw.get("id") or f"RULE-{index}")
        score = float(raw.get("score", 0.5))
        subject = str(raw.get("subject", "src")).lower()
        if subject not in {"src", "dst"}:
            raise ValueError(f"Rule {rid}: subject must be 'src' or 'dst', got {subject!r}")
        conds_raw = raw.get("conditions") or []
        if not isinstance(conds_raw, list) or not conds_raw:
            raise ValueError(f"Rule {rid} must declare a non-empty `conditions` list")

        conditions: list[Condition] = []
        for cidx, cond in enumerate(conds_raw):
            if not isinstance(cond, dict):
                raise ValueError(f"Rule {rid} condition #{cidx} must be a mapping")
            field_name = cond.get("field")
            op = cond.get("op")
            if not field_name or not op:
                raise ValueError(f"Rule {rid} condition #{cidx}: missing field or op")
            if op not in SUPPORTED_OPS:
                raise ValueError(f"Rule {rid} condition #{cidx}: unsupported op {op!r}")
            conditions.append(Condition(field=str(field_name), op=str(op), value=cond.get("value")))

        parsed.append(Rule(
            id=rid,
            description=str(raw.get("description", "")),
            mitre_tags=tuple(str(t) for t in (raw.get("mitre_tags") or [])),
            score=max(0.0, min(1.0, score)),
            subject=subject,
            signals=tuple(str(s) for s in (raw.get("signals") or [])),
            conditions=tuple(conditions),
        ))

    return parsed
