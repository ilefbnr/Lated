from __future__ import annotations

from fastapi import HTTPException


class FlowsRepository:
    """Read-oriented repository for suspicious flows."""

    PAGE_SIZE = 50

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def list(self, filters: dict, page: int) -> tuple[list[dict], int]:
        clauses: list[str] = []
        values: list[object] = []

        if filters.get("q"):
            like = f"%{filters['q']}%"
            clauses.append("(src_host LIKE ? OR dst_host LIKE ?)")
            values.extend([like, like])

        if filters.get("min_suspicion") is not None:
            clauses.append("suspicion >= ?")
            values.append(filters["min_suspicion"])

        if filters.get("since"):
            clauses.append("ts >= ?")
            values.append(filters["since"])

        if filters.get("until"):
            clauses.append("ts <= ?")
            values.append(filters["until"])

        sort = filters.get("sort") or "ts"
        sort_column = {
            "ts": "ts",
            "bytes": "byte_count",
            "packets": "packet_count",
            "suspicion": "suspicion",
        }.get(sort, "ts")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = max(page - 1, 0) * self.PAGE_SIZE

        with self.session_factory() as connection:
            total_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM suspicious_flows {where_sql}",
                values,
            ).fetchone()
            rows = connection.execute(
                f"""
                SELECT * FROM suspicious_flows
                {where_sql}
                ORDER BY {sort_column} DESC, flow_id ASC
                LIMIT ? OFFSET ?
                """,
                [*values, self.PAGE_SIZE, offset],
            ).fetchall()

        return [self._row_to_dict(row) for row in rows], int(total_row["count"] if total_row else 0)

    def get(self, flow_id: str) -> dict:
        with self.session_factory() as connection:
            row = connection.execute(
                "SELECT * FROM suspicious_flows WHERE flow_id = ?",
                (flow_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Flow not found")
        return self._row_to_dict(row)

    def record(self, flow, suspicion: float = 0.0, related_alert_id: str | None = None) -> None:
        """Persist a live CanonicalFlow into the suspicious_flows table so the
        REST /flows view reflects real-time traffic (not just demo seed).

        Called from ZeekLiveRuntime per flow. INSERT OR REPLACE keyed on
        flow_id makes it idempotent if the same flow is seen twice.
        """
        ts = flow.ts.isoformat() if hasattr(flow.ts, "isoformat") else str(flow.ts)
        with self.session_factory() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO suspicious_flows (
                    flow_id, ts, src_host, dst_host, src_port, dst_port,
                    protocol, duration, packet_count, byte_count, suspicion,
                    related_alert_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    flow.flow_id,
                    ts,
                    flow.src_host,
                    flow.dst_host,
                    int(flow.src_port),
                    int(flow.dst_port),
                    str(flow.protocol),
                    float(flow.duration),
                    int(flow.packet_count),
                    int(flow.byte_count),
                    float(suspicion),
                    related_alert_id,
                ),
            )

    def by_host(self, host_id: str, since: str | None = None, until: str | None = None) -> list[dict]:
        clauses = ["(src_host = ? OR dst_host = ?)"]
        values: list[object] = [host_id, host_id]
        if since:
            clauses.append("ts >= ?")
            values.append(since)
        if until:
            clauses.append("ts <= ?")
            values.append(until)

        where_sql = " AND ".join(clauses)
        with self.session_factory() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM suspicious_flows
                WHERE {where_sql}
                ORDER BY ts DESC, flow_id ASC
                LIMIT ?
                """,
                [*values, self.PAGE_SIZE],
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "flow_id": row["flow_id"],
            "ts": row["ts"],
            "src_host": row["src_host"],
            "dst_host": row["dst_host"],
            "src_port": row["src_port"],
            "dst_port": row["dst_port"],
            "protocol": row["protocol"],
            "duration": row["duration"],
            "packet_count": row["packet_count"],
            "byte_count": row["byte_count"],
            "suspicion": row["suspicion"],
            "related_alert_id": row["related_alert_id"],
        }
