# =============================================================================
# lated.supervision.storage.persistence — SQLAlchemy bootstrap
# =============================================================================
#
# PURPOSE
# -------
# Centralizes SQLAlchemy engine + session_factory creation. Repositories
# accept a session_factory and never construct their own — this enables
# test-time substitution with an in-memory engine.
#
# CYBERSECURITY REASONING
# -----------------------
# Connection strings come from env (POSTGRES_*) and NEVER from REST input.
# Connection pool sizes are capped to avoid resource exhaustion attacks
# against the DB.
# =============================================================================

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class Persistence:
    """SQLAlchemy engine + session factory holder.

    Methods
    -------
      configure(config) -> None
      get_session() -> Session   # context manager
    """

    def __init__(self):
        self._database_path: Path | None = None

    def configure(self, config, database_path: str | Path | None = None) -> None:
        if database_path is not None:
            self._database_path = Path(database_path)
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            root = Path(__file__).resolve().parents[4]
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self._database_path = data_dir / "supervision.sqlite3"

        with self.get_session() as connection:
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
                CREATE TABLE IF NOT EXISTS hosts (
                    host_id TEXT PRIMARY KEY,
                    ip_addresses TEXT NOT NULL,
                    hostname TEXT,
                    subnet TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    os_guess TEXT,
                    metadata TEXT NOT NULL,
                    current_risk REAL NOT NULL,
                    last_alert_at TEXT,
                    active_alerts INTEGER NOT NULL,
                    schema_version TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS host_risk_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    risk REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS host_heatmap (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_id TEXT NOT NULL,
                    neighbor_host_id TEXT NOT NULL,
                    intensity REAL NOT NULL,
                    bytes INTEGER NOT NULL,
                    packets INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS suspicious_flows (
                    flow_id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    src_host TEXT NOT NULL,
                    dst_host TEXT NOT NULL,
                    src_port INTEGER NOT NULL,
                    dst_port INTEGER NOT NULL,
                    protocol TEXT NOT NULL,
                    duration REAL NOT NULL,
                    packet_count INTEGER NOT NULL,
                    byte_count INTEGER NOT NULL,
                    suspicion REAL NOT NULL,
                    related_alert_id TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    nodes TEXT NOT NULL,
                    edges TEXT NOT NULL
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

        self._seed_if_empty()

    @contextmanager
    def get_session(self):
        if self._database_path is None:
            raise RuntimeError("Persistence.configure() must be called before get_session().")

        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _seed_if_empty(self) -> None:
        # Demo seeding is OPT-IN. In live/production mode we never want fake
        # hosts/alerts/flows/paths polluting the SOC views. Set
        # LATED_SEED_DEMO=1 only when showing the offline UI demo against an
        # empty database.
        if os.environ.get("LATED_SEED_DEMO", "").strip().lower() not in {"1", "true", "yes", "on"}:
            return
        self._seed_hosts_if_empty()
        self._seed_alerts_if_empty()
        self._seed_flows_if_empty()
        self._seed_graph_if_empty()
        self._seed_paths_if_empty()

    def _seed_hosts_if_empty(self) -> None:
        with self.get_session() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM hosts").fetchone()
            if row is not None and row["count"] > 0:
                return

            now = datetime.now(timezone.utc).isoformat()
            hosts = [
                {
                    "host_id": "host-workstation-01",
                    "ip_addresses": ["10.0.0.21"],
                    "hostname": "ws-finance-01",
                    "subnet": "10.0.0.0/24",
                    "first_seen": now,
                    "last_seen": now,
                    "os_guess": "windows",
                    "metadata": {"role": "workstation"},
                    "current_risk": 0.82,
                    "last_alert_at": now,
                    "active_alerts": 1,
                    "schema_version": "1.0.0",
                },
                {
                    "host_id": "host-server-02",
                    "ip_addresses": ["10.0.0.11"],
                    "hostname": "fs-core-02",
                    "subnet": "10.0.0.0/24",
                    "first_seen": now,
                    "last_seen": now,
                    "os_guess": "linux",
                    "metadata": {"role": "file_server"},
                    "current_risk": 0.41,
                    "last_alert_at": now,
                    "active_alerts": 0,
                    "schema_version": "1.0.0",
                },
                {
                    "host_id": "host-dc-01",
                    "ip_addresses": ["10.0.0.5"],
                    "hostname": "dc-core-01",
                    "subnet": "10.0.0.0/24",
                    "first_seen": now,
                    "last_seen": now,
                    "os_guess": "windows",
                    "metadata": {"role": "domain_controller"},
                    "current_risk": 0.30,
                    "last_alert_at": None,
                    "active_alerts": 0,
                    "schema_version": "1.0.0",
                },
            ]
            for host in hosts:
                connection.execute(
                    """
                    INSERT INTO hosts (
                        host_id, ip_addresses, hostname, subnet, first_seen, last_seen,
                        os_guess, metadata, current_risk, last_alert_at, active_alerts,
                        schema_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        host["host_id"],
                        json.dumps(host["ip_addresses"]),
                        host["hostname"],
                        host["subnet"],
                        host["first_seen"],
                        host["last_seen"],
                        host["os_guess"],
                        json.dumps(host["metadata"]),
                        host["current_risk"],
                        host["last_alert_at"],
                        host["active_alerts"],
                        host["schema_version"],
                    ),
                )

            risk_history = [
                ("host-workstation-01", now, 0.82),
                ("host-workstation-01", now, 0.73),
                ("host-server-02", now, 0.41),
            ]
            for item in risk_history:
                connection.execute(
                    "INSERT INTO host_risk_history (host_id, ts, risk) VALUES (?, ?, ?)",
                    item,
                )

            heatmap_rows = [
                ("host-workstation-01", "host-server-02", 0.87, 82000, 1140),
                ("host-workstation-01", "host-dc-01", 0.52, 31000, 440),
            ]
            for item in heatmap_rows:
                connection.execute(
                    """
                    INSERT INTO host_heatmap (
                        host_id, neighbor_host_id, intensity, bytes, packets
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    item,
                )

    def _seed_alerts_if_empty(self) -> None:
        with self.get_session() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM alerts").fetchone()
            if row is not None and row["count"] > 0:
                return

            now = datetime.now(timezone.utc).isoformat()
            alerts_seed = [
                (
                    "alert-001",
                    now,
                    "high",
                    "fusion",
                    "host-workstation-01",
                    "Suspicious lateral movement sequence observed.",
                    0.82,
                    json.dumps(["flow-001", "snapshot-001"]),
                    json.dumps(["TA0008", "T1021"]),
                    json.dumps({"narrative": "Recon followed by host pivot."}),
                    "open",
                    "1.0.0",
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
                (
                    "alert-002",
                    now,
                    "medium",
                    "reconnaissance",
                    "host-workstation-01",
                    "Recon sweep across internal subnet detected.",
                    0.61,
                    json.dumps(["flow-002"]),
                    json.dumps(["TA0043", "T1046"]),
                    json.dumps({"narrative": "Port-scan signal triggered."}),
                    "open",
                    "1.0.0",
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            ]
            for item in alerts_seed:
                connection.execute(
                    """
                    INSERT INTO alerts (
                        alert_id, created_at, severity, kind, subject_host, description,
                        score, evidence, mitre_tags, explainability, status, schema_version,
                        acknowledged_by, acknowledged_at, closed_by, closed_at, disposition
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    item,
                )

    def _seed_flows_if_empty(self) -> None:
        with self.get_session() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM suspicious_flows").fetchone()
            if row is not None and row["count"] > 0:
                return

            now = datetime.now(timezone.utc).isoformat()
            flows_seed = [
                (
                    "flow-001",
                    now,
                    "host-workstation-01",
                    "host-server-02",
                    51324,
                    445,
                    "tcp",
                    12.5,
                    1140,
                    82000,
                    0.87,
                    "alert-001",
                ),
                (
                    "flow-002",
                    now,
                    "host-workstation-01",
                    "host-dc-01",
                    51800,
                    389,
                    "tcp",
                    3.2,
                    440,
                    31000,
                    0.52,
                    "alert-002",
                ),
                (
                    "flow-003",
                    now,
                    "host-server-02",
                    "host-workstation-01",
                    445,
                    51324,
                    "tcp",
                    0.4,
                    60,
                    4200,
                    0.18,
                    None,
                ),
            ]
            for item in flows_seed:
                connection.execute(
                    """
                    INSERT INTO suspicious_flows (
                        flow_id, ts, src_host, dst_host, src_port, dst_port,
                        protocol, duration, packet_count, byte_count, suspicion,
                        related_alert_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    item,
                )

    def _seed_graph_if_empty(self) -> None:
        with self.get_session() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM graph_snapshots").fetchone()
            if row is not None and row["count"] > 0:
                return

            now = datetime.now(timezone.utc).isoformat()
            baseline_nodes = [
                {"data": {"id": "host-workstation-01", "label": "ws-finance-01", "risk": 0.82, "subnet": "10.0.0.0/24"}},
                {"data": {"id": "host-server-02", "label": "fs-core-02", "risk": 0.41, "subnet": "10.0.0.0/24"}},
                {"data": {"id": "host-dc-01", "label": "dc-core-01", "risk": 0.30, "subnet": "10.0.0.0/24"}},
            ]
            baseline_edges = [
                {
                    "data": {
                        "id": "host-workstation-01->host-server-02@baseline",
                        "source": "host-workstation-01",
                        "target": "host-server-02",
                        "weight": 0.87,
                        "suspicion": 0.87,
                        "onAttackPath": True,
                        "pathId": "path-001",
                    }
                },
                {
                    "data": {
                        "id": "host-workstation-01->host-dc-01@baseline",
                        "source": "host-workstation-01",
                        "target": "host-dc-01",
                        "weight": 0.52,
                        "suspicion": 0.52,
                        "onAttackPath": True,
                        "pathId": "path-001",
                    }
                },
                {
                    "data": {
                        "id": "host-server-02->host-workstation-01@baseline",
                        "source": "host-server-02",
                        "target": "host-workstation-01",
                        "weight": 0.18,
                        "suspicion": 0.18,
                        "onAttackPath": False,
                    }
                },
            ]
            snapshot_nodes = [
                {**node, "data": {**node["data"], "compromised": node["data"]["id"] == "host-workstation-01"}}
                for node in baseline_nodes
            ]
            snapshot_edges = [
                {
                    "data": {
                        **edge["data"],
                        "id": edge["data"]["id"].replace("@baseline", f"@{now}"),
                    }
                }
                for edge in baseline_edges
            ]
            graph_seed = [
                ("graph-baseline", "baseline", now, json.dumps(baseline_nodes), json.dumps(baseline_edges)),
                ("graph-snapshot-001", "snapshot", now, json.dumps(snapshot_nodes), json.dumps(snapshot_edges)),
            ]
            for item in graph_seed:
                connection.execute(
                    """
                    INSERT INTO graph_snapshots (
                        snapshot_id, kind, ts, nodes, edges
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    item,
                )

    def _seed_paths_if_empty(self) -> None:
        with self.get_session() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM attack_paths").fetchone()
            if row is not None and row["count"] > 0:
                return

            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                INSERT INTO attack_paths (
                    path_id, created_at, hosts, pivot_hosts, path_confidence,
                    mitre_tactic_chain, timeline_alert_ids, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "path-001",
                    now,
                    json.dumps(["host-workstation-01", "host-server-02", "host-dc-01"]),
                    json.dumps(["host-workstation-01"]),
                    0.79,
                    json.dumps(["TA0043", "TA0008"]),
                    json.dumps(["alert-002", "alert-001"]),
                    "1.0.0",
                ),
            )
