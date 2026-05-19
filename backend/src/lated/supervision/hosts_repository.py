from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException

from lated.common.schemas import Host, HostHeatmapCell, HostRiskPoint, HostRiskSummary


class HostsRepository:
    """Read-oriented repository for host supervision views."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def list(self, subnet: str | None = None) -> list[Host]:
        query = "SELECT * FROM hosts"
        params: tuple[object, ...] = ()
        if subnet:
            query += " WHERE subnet = ?"
            params = (subnet,)
        query += " ORDER BY host_id"
        with self.session_factory() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_host(row) for row in rows]

    def get(self, host_id: str) -> Host:
        with self.session_factory() as connection:
            row = connection.execute("SELECT * FROM hosts WHERE host_id = ?", (host_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Host not found")
        return self._row_to_host(row)

    def top_risky(self, limit: int = 25) -> list[HostRiskSummary]:
        with self.session_factory() as connection:
            rows = connection.execute(
                """
                SELECT host_id, hostname, subnet, current_risk, last_alert_at, active_alerts
                FROM hosts
                ORDER BY current_risk DESC, active_alerts DESC, host_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            HostRiskSummary(
                host_id=row["host_id"],
                hostname=row["hostname"],
                subnet=row["subnet"],
                current_risk=row["current_risk"],
                last_alert_at=(datetime.fromisoformat(row["last_alert_at"]) if row["last_alert_at"] else None),
                active_alerts=row["active_alerts"],
            )
            for row in rows
        ]

    def risk_evolution(self, host_id: str, hours: int = 24) -> list[HostRiskPoint]:
        self.get(host_id)
        with self.session_factory() as connection:
            rows = connection.execute(
                """
                SELECT ts, risk FROM host_risk_history
                WHERE host_id = ?
                ORDER BY ts DESC
                LIMIT ?
                """,
                (host_id, max(hours, 1)),
            ).fetchall()
        return [HostRiskPoint(ts=datetime.fromisoformat(row["ts"]), risk=row["risk"]) for row in reversed(rows)]

    def heatmap(self, host_id: str, window_minutes: int = 60) -> list[HostHeatmapCell]:
        del window_minutes
        self.get(host_id)
        with self.session_factory() as connection:
            rows = connection.execute(
                """
                SELECT neighbor_host_id, intensity, bytes, packets
                FROM host_heatmap
                WHERE host_id = ?
                ORDER BY intensity DESC, neighbor_host_id ASC
                """,
                (host_id,),
            ).fetchall()
        return [
            HostHeatmapCell(
                neighbor_host_id=row["neighbor_host_id"],
                intensity=row["intensity"],
                bytes=row["bytes"],
                packets=row["packets"],
            )
            for row in rows
        ]

    @staticmethod
    def _row_to_host(row) -> Host:
        return Host(
            host_id=row["host_id"],
            ip_addresses=json.loads(row["ip_addresses"]),
            hostname=row["hostname"],
            subnet=row["subnet"],
            first_seen=datetime.fromisoformat(row["first_seen"]),
            last_seen=datetime.fromisoformat(row["last_seen"]),
            os_guess=row["os_guess"],
            metadata=json.loads(row["metadata"]),
            schema_version=row["schema_version"],
        )
