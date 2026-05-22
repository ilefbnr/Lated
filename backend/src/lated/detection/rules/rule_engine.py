# =============================================================================
# lated.detection.rules.rule_engine — declarative MITRE rule evaluator
# =============================================================================
#
# Per-flow rule evaluator. Each flow is checked against every rule; when a
# rule's conditions are ALL satisfied, the engine emits a ReconScore tagged
# detector=MITRE_RULES, kind=LM. Multiple rules can fire on the same flow —
# the engine aggregates them per (subject_host, window_start) using max
# score and union of signals/mitre_tags, so SuspicionFusion still sees one
# heuristic contribution per host/window.
#
# The engine is windowed by `window_seconds` (default 60s) so that hits
# align with the LM/TGNN window cadence and fuse cleanly.
# =============================================================================

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Iterator

from lated.common.schemas import (
    CanonicalFlow, DetectionKind, DetectorName, ReconScore,
)
from lated.detection.rules.rule_loader import Condition, Rule


_NORMALIZED_EXT_LOOKUP = (
    "smb_files_names",  # for "contains_any" on extensions like ".ps1"
)


class MITRERulesDetector:
    """Evaluate a flow stream against a declarative MITRE rule catalog."""

    def __init__(
        self,
        rules: list[Rule],
        window_seconds: int = 60,
        host_registry=None,
    ):
        self.rules = list(rules)
        self.window_seconds = int(window_seconds)
        self.host_registry = host_registry

    # ----------------------------------------------------------------- API

    def run(self, flows: Iterable[CanonicalFlow]) -> list[ReconScore]:
        return list(self.score(flows))

    def score(self, flows: Iterable[CanonicalFlow]) -> Iterator[ReconScore]:
        # Bucketize hits per (subject, window_start). At the end of the
        # stream we emit one aggregated ReconScore per bucket.
        buckets: dict[tuple[str, datetime], _Bucket] = defaultdict(_Bucket)

        for flow in flows:
            matched = [rule for rule in self.rules if self._matches(rule, flow)]
            if not matched:
                continue
            window_start = self._window_start(flow.ts)
            for rule in matched:
                subject = flow.src_host if rule.subject == "src" else flow.dst_host
                target = flow.dst_host if rule.subject == "src" else flow.src_host
                key = (subject, window_start)
                buckets[key].apply(rule, target, flow.dst_port)

        for (subject, window_start), bucket in sorted(buckets.items()):
            yield ReconScore(
                detector=DetectorName.MITRE_RULES,
                kind=DetectionKind.LM,
                window_start=window_start,
                subject_host=subject,
                score=bucket.score,
                unique_destinations=len(bucket.targets),
                unique_dst_ports=len(bucket.ports),
                burst_rate=0.0,
                target_hosts=sorted(bucket.targets),
                protocol=None,
                triggered_signals=sorted(bucket.signals),
                evidence=bucket.evidence(),
                mitre_tags=sorted(bucket.mitre_tags),
                confidence=bucket.score,
                critical_asset_touched=False,
                new_relation=False,
            )

    # ------------------------------------------------------------- internals

    def _window_start(self, ts: datetime) -> datetime:
        ts_utc = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        epoch = int(ts_utc.timestamp())
        bucket = epoch - (epoch % self.window_seconds)
        return datetime.fromtimestamp(bucket, tz=timezone.utc)

    def _matches(self, rule: Rule, flow: CanonicalFlow) -> bool:
        for cond in rule.conditions:
            if not self._eval_condition(cond, flow):
                return False
        return True

    def _eval_condition(self, cond: Condition, flow: CanonicalFlow) -> bool:
        value = self._resolve_field(cond.field, flow)
        op = cond.op
        expected = cond.value

        if op == "equals":
            return value == expected
        if op == "not_equals":
            return value != expected
        if op == "in":
            return isinstance(expected, list) and value in expected
        if op == "not_in":
            return isinstance(expected, list) and value not in expected
        if op == "contains":
            if value is None:
                return False
            if isinstance(value, str):
                return str(expected) in value
            if isinstance(value, (list, tuple, set)):
                return expected in value
            return False
        if op == "contains_any":
            if value is None or not isinstance(expected, list):
                return False
            if isinstance(value, str):
                return any(str(token) in value for token in expected)
            if isinstance(value, (list, tuple, set)):
                # Support endswith match for extensions (".ps1", ".bat", ...).
                # If every expected starts with ".", treat as suffix match
                # against each item in the value list.
                if all(isinstance(t, str) and t.startswith(".") for t in expected):
                    return any(
                        isinstance(item, str)
                        and any(item.lower().endswith(token) for token in expected)
                        for item in value
                    )
                value_set = set(value)
                return any(token in value_set for token in expected)
            return False
        if op == "greater_than":
            try:
                return value is not None and float(value) > float(expected)
            except (TypeError, ValueError):
                return False
        if op == "less_than":
            try:
                return value is not None and float(value) < float(expected)
            except (TypeError, ValueError):
                return False
        if op == "exists":
            if isinstance(value, (list, dict, str)):
                return len(value) > 0
            return value is not None
        if op == "hostname_differs":
            # Special: compare enrichment.ntlm_client_hostname (or whichever
            # field is being checked) to the actual src host's hostname
            # resolved from the host registry, if available. Fallback:
            # compare to the canonical src host id.
            if value is None:
                return False
            target_hostname = self._resolve_hostname(flow.src_host)
            if target_hostname is None:
                return False
            return str(value).strip().lower() != target_hostname.strip().lower()

        return False

    def _resolve_field(self, dotted: str, flow: CanonicalFlow) -> Any:
        # Top-level CanonicalFlow attributes go through getattr; anything
        # under "enrichment." goes through dict access.
        parts = dotted.split(".")
        if not parts:
            return None
        head = parts[0]
        if head == "enrichment":
            value: Any = flow.enrichment or {}
            for key in parts[1:]:
                if not isinstance(value, dict):
                    return None
                value = value.get(key)
            return value
        value = getattr(flow, head, None)
        for key in parts[1:]:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                value = getattr(value, key, None)
        return value

    def _resolve_hostname(self, host_id: str) -> str | None:
        if self.host_registry is None:
            return host_id
        try:
            host = self.host_registry.get(host_id)
        except Exception:
            return host_id
        return getattr(host, "hostname", None) or host_id


class _Bucket:
    """Per-(subject, window) aggregator: max score + union of context."""

    __slots__ = ("score", "signals", "mitre_tags", "rule_ids", "targets", "ports")

    def __init__(self) -> None:
        self.score: float = 0.0
        self.signals: set[str] = set()
        self.mitre_tags: set[str] = set()
        self.rule_ids: list[str] = []
        self.targets: set[str] = set()
        self.ports: set[int] = set()

    def apply(self, rule: Rule, target: str, dst_port: int) -> None:
        self.score = min(1.0, max(self.score, rule.score))
        self.signals.update(rule.signals)
        self.mitre_tags.update(rule.mitre_tags)
        self.rule_ids.append(rule.id)
        if target:
            self.targets.add(target)
        if dst_port:
            self.ports.add(int(dst_port))

    def evidence(self) -> list[str]:
        return [f"rule={rid}" for rid in self.rule_ids]
