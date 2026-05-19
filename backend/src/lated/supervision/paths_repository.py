from __future__ import annotations

import json

from fastapi import HTTPException


class PathsRepository:
    """Read-oriented repository for reconstructed attack paths."""

    PAGE_SIZE = 50

    def __init__(self, session_factory, alert_repository, graph_repository):
        self.session_factory = session_factory
        self.alert_repository = alert_repository
        self.graph_repository = graph_repository

    def list(self, filters: dict, page: int) -> tuple[list[dict], int]:
        clauses: list[str] = []
        values: list[object] = []

        if filters.get("min_confidence") is not None:
            clauses.append("path_confidence >= ?")
            values.append(filters["min_confidence"])
        if filters.get("since"):
            clauses.append("created_at >= ?")
            values.append(filters["since"])
        if filters.get("until"):
            clauses.append("created_at <= ?")
            values.append(filters["until"])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = max(page - 1, 0) * self.PAGE_SIZE

        with self.session_factory() as connection:
            total_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM attack_paths {where_sql}",
                values,
            ).fetchone()
            rows = connection.execute(
                f"""
                SELECT * FROM attack_paths
                {where_sql}
                ORDER BY created_at DESC, path_id ASC
                LIMIT ? OFFSET ?
                """,
                [*values, self.PAGE_SIZE, offset],
            ).fetchall()

        return [self._row_to_summary(row) for row in rows], int(total_row["count"] if total_row else 0)

    def get(self, path_id: str) -> dict:
        row = self._fetch_row(path_id)
        summary = self._row_to_summary(row)
        summary["timeline"] = self._load_timeline(json.loads(row["timeline_alert_ids"]))
        return summary

    def timeline(self, path_id: str) -> list[dict]:
        row = self._fetch_row(path_id)
        return self._load_timeline(json.loads(row["timeline_alert_ids"]))

    def graph(self, path_id: str) -> dict:
        row = self._fetch_row(path_id)
        hosts = set(json.loads(row["hosts"]))
        baseline = self.graph_repository.baseline()
        resolved_hosts = set(self.graph_repository.resolve_node_ids(hosts).values())
        nodes = []
        for node in baseline["nodes"]:
            if node["data"]["id"] in resolved_hosts:
                marked = {**node["data"], "onAttackPath": True}
                nodes.append({"data": marked})
        edges = []
        for edge in baseline["edges"]:
            data = edge["data"]
            if data["source"] in resolved_hosts and data["target"] in resolved_hosts:
                marked = {**data, "onAttackPath": True, "pathId": path_id}
                edges.append({"data": marked})
        return {"nodes": nodes, "edges": edges, "generated_at": baseline["generated_at"]}

    def _fetch_row(self, path_id: str):
        with self.session_factory() as connection:
            row = connection.execute(
                "SELECT * FROM attack_paths WHERE path_id = ?",
                (path_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Attack path not found")
        return row

    def _load_timeline(self, alert_ids: list[str]) -> list[dict]:
        timeline: list[dict] = []
        for alert_id in alert_ids:
            try:
                alert = self.alert_repository.get(alert_id)
            except HTTPException:
                continue
            timeline.append(alert.model_dump(mode="json"))
        return timeline

    @staticmethod
    def _row_to_summary(row) -> dict:
        return {
            "path_id": row["path_id"],
            "created_at": row["created_at"],
            "hosts": json.loads(row["hosts"]),
            "pivot_hosts": json.loads(row["pivot_hosts"]),
            "path_confidence": row["path_confidence"],
            "mitre_tactic_chain": json.loads(row["mitre_tactic_chain"]),
            "alert_count": len(json.loads(row["timeline_alert_ids"])),
            "schema_version": row["schema_version"],
        }
