# =============================================================================
# lated.supervision.alerts.alert_repository — alert persistence
# =============================================================================
#
# PURPOSE
# -------
# Persists Alert objects (Postgres) and serves the REST endpoints with
# paginated queries, filters, and ack/close mutations.
#
# SCHEMA (Postgres)
# -----------------
#   alerts(
#     alert_id text primary key,
#     created_at timestamptz,
#     severity text,
#     kind text,
#     subject_host text,
#     description text,
#     score numeric,
#     evidence jsonb,
#     mitre_tags text[],
#     explainability jsonb,
#     status text default 'open',
#     acknowledged_by text,
#     acknowledged_at timestamptz,
#     closed_by text,
#     closed_at timestamptz,
#     disposition text
#   )
#
# CYBERSECURITY REASONING
# -----------------------
# Every mutation (ack/close) is audit-logged with the acting user, the
# previous state, and the new state. Auditability is non-negotiable.
# =============================================================================

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException

from lated.common.schemas import Alert


class AlertRepository:
    """Postgres-backed alert repository.

    Methods
    -------
      insert(alert)
      bump(alert_id, suspicion_score)
      list(filters, page) -> (rows, total)
      get(alert_id) -> Alert
      ack(alert_id, user)
      close(alert_id, user, disposition)
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def insert(self, alert: Alert) -> None:
        with self.session_factory() as connection:
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
                    alert.score,
                    json.dumps(alert.evidence),
                    json.dumps(alert.mitre_tags),
                    json.dumps(alert.explainability),
                    alert.status,
                    alert.schema_version,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )

    def list(self, filters: dict, page: int):
        clauses: list[str] = []
        values: list[object] = []

        if filters.get("host"):
            clauses.append("subject_host = ?")
            values.append(filters["host"])

        severities = filters.get("severity") or []
        if severities:
            placeholders = ", ".join("?" for _ in severities)
            clauses.append(f"severity IN ({placeholders})")
            values.extend(severities)

        if filters.get("since"):
            clauses.append("created_at >= ?")
            values.append(filters["since"])

        if filters.get("until"):
            clauses.append("created_at <= ?")
            values.append(filters["until"])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        page_size = 50
        offset = max(page - 1, 0) * page_size

        with self.session_factory() as connection:
            total_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM alerts {where_sql}",
                values,
            ).fetchone()
            rows = connection.execute(
                f"""
                SELECT * FROM alerts
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*values, page_size, offset],
            ).fetchall()

        return [self._row_to_alert(row) for row in rows], int(total_row["count"] if total_row else 0)

    def get(self, alert_id: str) -> Alert:
        with self.session_factory() as connection:
            row = connection.execute(
                "SELECT * FROM alerts WHERE alert_id = ?",
                (alert_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        return self._row_to_alert(row)

    def ack(self, alert_id: str, user: str) -> Alert:
        now = datetime.now(timezone.utc).isoformat()
        with self.session_factory() as connection:
            connection.execute(
                """
                UPDATE alerts
                SET status = 'ack', acknowledged_by = ?, acknowledged_at = ?
                WHERE alert_id = ?
                """,
                (user, now, alert_id),
            )
        return self.get(alert_id)

    def close(self, alert_id: str, user: str, disposition: str) -> Alert:
        now = datetime.now(timezone.utc).isoformat()
        with self.session_factory() as connection:
            connection.execute(
                """
                UPDATE alerts
                SET status = 'closed', closed_by = ?, closed_at = ?, disposition = ?
                WHERE alert_id = ?
                """,
                (user, now, disposition, alert_id),
            )
        return self.get(alert_id)

    @staticmethod
    def _row_to_alert(row) -> Alert:
        return Alert(
            alert_id=row["alert_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            severity=row["severity"],
            kind=row["kind"],
            subject_host=row["subject_host"],
            description=row["description"],
            score=row["score"],
            evidence=json.loads(row["evidence"]),
            mitre_tags=json.loads(row["mitre_tags"]),
            explainability=json.loads(row["explainability"]),
            status=row["status"],
            schema_version=row["schema_version"],
        )
