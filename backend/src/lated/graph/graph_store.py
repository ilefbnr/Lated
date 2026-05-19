# =============================================================================
# lated.graph.graph_store — TemporalSnapshot persistence (SQLite)
# =============================================================================
#
# Schema:
#   temporal_snapshots(
#     snapshot_id    TEXT PRIMARY KEY,
#     window_start   TEXT NOT NULL,
#     window_end     TEXT NOT NULL,
#     nodes          TEXT NOT NULL,      -- JSON list[str]
#     edges          TEXT NOT NULL,      -- JSON list[[src,dst]]
#     edge_features  TEXT NOT NULL,      -- JSON dict[str, EdgeFeatures]
#     node_features  TEXT NOT NULL,      -- JSON dict[str, NodeFeatures]
#     schema_version TEXT NOT NULL
#   )
#   snapshot_hosts(
#     snapshot_id  TEXT NOT NULL,
#     host_id      TEXT NOT NULL,
#     PRIMARY KEY (snapshot_id, host_id)
#   )
#
# Snapshots are write-once: a duplicate snapshot_id triggers INSERT OR IGNORE
# so replays remain idempotent. JSON values use sorted keys → bit-stable.
# =============================================================================

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from lated.common.schemas import EdgeFeatures, NodeFeatures, TemporalSnapshot


class GraphStore:
    """SQLite-backed snapshot store."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS temporal_snapshots (
                    snapshot_id    TEXT PRIMARY KEY,
                    window_start   TEXT NOT NULL,
                    window_end     TEXT NOT NULL,
                    nodes          TEXT NOT NULL,
                    edges          TEXT NOT NULL,
                    edge_features  TEXT NOT NULL,
                    node_features  TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshot_hosts (
                    snapshot_id TEXT NOT NULL,
                    host_id     TEXT NOT NULL,
                    PRIMARY KEY (snapshot_id, host_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshot_hosts_host "
                "ON snapshot_hosts(host_id, snapshot_id)"
            )

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, snapshot: TemporalSnapshot) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO temporal_snapshots (
                    snapshot_id, window_start, window_end,
                    nodes, edges, edge_features, node_features, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.window_start.isoformat(),
                    snapshot.window_end.isoformat(),
                    json.dumps(list(snapshot.nodes), sort_keys=True),
                    json.dumps([list(edge) for edge in snapshot.edges], sort_keys=True),
                    json.dumps(
                        {key: feat.model_dump() for key, feat in snapshot.edge_features.items()},
                        sort_keys=True,
                    ),
                    json.dumps(
                        {key: feat.model_dump() for key, feat in snapshot.node_features.items()},
                        sort_keys=True,
                    ),
                    snapshot.schema_version,
                ),
            )
            for host_id in snapshot.nodes:
                conn.execute(
                    "INSERT OR IGNORE INTO snapshot_hosts (snapshot_id, host_id) VALUES (?, ?)",
                    (snapshot.snapshot_id, host_id),
                )

    def load(self, window_start: datetime | str) -> TemporalSnapshot:
        key = self._coerce_iso(window_start)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM temporal_snapshots WHERE window_start = ?",
                (key,),
            ).fetchone()
        if row is None:
            raise KeyError(f"No snapshot found for window_start={key}")
        return self._row_to_snapshot(row)

    def query_window(self, start: datetime | str, end: datetime | str) -> list[TemporalSnapshot]:
        start_iso = self._coerce_iso(start)
        end_iso = self._coerce_iso(end)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM temporal_snapshots
                WHERE window_start >= ? AND window_end <= ?
                ORDER BY window_start ASC, snapshot_id ASC
                """,
                (start_iso, end_iso),
            ).fetchall()
        return [self._row_to_snapshot(row) for row in rows]

    def query_host(
        self,
        host_id: str,
        start: datetime | str,
        end: datetime | str,
    ) -> list[TemporalSnapshot]:
        start_iso = self._coerce_iso(start)
        end_iso = self._coerce_iso(end)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.* FROM temporal_snapshots s
                JOIN snapshot_hosts h ON h.snapshot_id = s.snapshot_id
                WHERE h.host_id = ?
                  AND s.window_start >= ?
                  AND s.window_end <= ?
                ORDER BY s.window_start ASC, s.snapshot_id ASC
                """,
                (host_id, start_iso, end_iso),
            ).fetchall()
        return [self._row_to_snapshot(row) for row in rows]

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM temporal_snapshots").fetchone()
        return int(row["c"] if row else 0)

    @staticmethod
    def _coerce_iso(value: datetime | str) -> str:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return str(value)

    @staticmethod
    def _row_to_snapshot(row) -> TemporalSnapshot:
        edge_features_raw = json.loads(row["edge_features"])
        node_features_raw = json.loads(row["node_features"])
        edges_raw = json.loads(row["edges"])
        return TemporalSnapshot(
            snapshot_id=row["snapshot_id"],
            window_start=datetime.fromisoformat(row["window_start"]),
            window_end=datetime.fromisoformat(row["window_end"]),
            nodes=list(json.loads(row["nodes"])),
            edges=[tuple(edge) for edge in edges_raw],
            edge_features={key: EdgeFeatures(**value) for key, value in edge_features_raw.items()},
            node_features={key: NodeFeatures(**value) for key, value in node_features_raw.items()},
            schema_version=row["schema_version"],
        )
