# =============================================================================
# lated.correlation.correlation_store — persist AttackPath into supervision DB
# =============================================================================
#
# Writes correlation outputs into the same SQLite tables that supervision's
# /paths route already reads (`attack_paths`, `alerts`). The schema is created
# idempotently so a standalone test can use a tmp DB without standing up the
# full supervision Persistence.
#
# Save semantics: REPLACE on path_id (correlation replays its full state, so
# the latest output wins). Alerts are inserted with INSERT OR REPLACE on
# alert_id — also replay-friendly.
# =============================================================================

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from lated.common.schemas import Alert, AttackPath, SCHEMA_VERSION

from lated.correlation.correlation_engine import CorrelationResult


class CorrelationStore:
    """Persists AttackPath objects + their timeline alerts."""

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._ensure_schema()

    def save(self, result: CorrelationResult) -> None:
        path = result.path
        with self.session_factory() as connection:
            for alert in path.timeline:
                self._upsert_alert(connection, alert)
            self._upsert_path(connection, path)

    def save_many(self, results: Iterable[CorrelationResult]) -> int:
        count = 0
        for result in results:
            self.save(result)
            count += 1
        return count

    def _upsert_alert(self, connection, alert: Alert) -> None:
        connection.execute(
            """
            INSERT OR REPLACE INTO alerts (
                alert_id, created_at, severity, kind, subject_host, description,
                score, evidence, mitre_tags, explainability, status, schema_version,
                acknowledged_by, acknowledged_at, closed_by, closed_at, disposition
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.alert_id,
                alert.created_at.isoformat(),
                alert.severity,
                alert.kind,
                alert.subject_host,
                alert.description,
                float(alert.score),
                json.dumps(list(alert.evidence)),
                json.dumps(list(alert.mitre_tags)),
                json.dumps(dict(alert.explainability)),
                alert.status,
                alert.schema_version,
                None,
                None,
                None,
                None,
                None,
            ),
        )

    def _upsert_path(self, connection, path: AttackPath) -> None:
        connection.execute(
            """
            INSERT OR REPLACE INTO attack_paths (
                path_id, created_at, hosts, pivot_hosts, path_confidence,
                mitre_tactic_chain, timeline_alert_ids, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                path.path_id,
                path.created_at.isoformat(),
                json.dumps(list(path.hosts)),
                json.dumps(list(path.pivot_hosts)),
                float(path.path_confidence),
                json.dumps(list(path.mitre_tactic_chain)),
                json.dumps([alert.alert_id for alert in path.timeline]),
                path.schema_version,
            ),
        )

    def _ensure_schema(self) -> None:
        with self.session_factory() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    subject_host TEXT NOT NULL,
                    description TEXT NOT NULL,
                    score REAL NOT NULL,
                    evidence TEXT NOT NULL,
                    mitre_tags TEXT NOT NULL,
                    explainability TEXT NOT NULL,
                    status TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    acknowledged_by TEXT,
                    acknowledged_at TEXT,
                    closed_by TEXT,
                    closed_at TEXT,
                    disposition TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS attack_paths (
                    path_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    hosts TEXT NOT NULL,
                    pivot_hosts TEXT NOT NULL,
                    path_confidence REAL NOT NULL,
                    mitre_tactic_chain TEXT NOT NULL,
                    timeline_alert_ids TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                )
                """
            )


def session_factory_for(path: str | Path):
    """Return a context-manager session factory backed by a SQLite file path."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _factory():
        connection = sqlite3.connect(target)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    return _factory


__all__ = ["CorrelationStore", "session_factory_for", "SCHEMA_VERSION"]
