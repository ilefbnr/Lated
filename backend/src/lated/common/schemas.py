# =============================================================================
# lated.common.schemas — canonical data contracts
# =============================================================================
#
# PURPOSE
# -------
# Defines every data shape that crosses a module boundary in LateD.
# Pydantic v2 models give us:
#   - validation at the boundary (untrusted -> trusted),
#   - JSON serialization (REST/WebSocket),
#   - explicit, versioned contracts for forensic replay.
#
# WHY THIS FILE MATTERS
# ---------------------
# The architecture's "strict module separation" principle is enforced HERE.
# Ingestion -> Graph -> Detection -> Correlation -> Supervision communicate
# ONLY through these schemas. No module shares Python objects across
# boundaries unless wrapped in one of these models.
#
# CYBERSECURITY REASONING
# -----------------------
# - All untrusted input (PCAP/Zeek/NetFlow) must be coerced into CanonicalFlow
#   before any downstream module touches it. This is the "validation curtain".
# - Every schema carries a `schema_version` field. The model loader refuses to
#   process flows from incompatible schema versions.
# - Sensitive fields (raw payloads, credentials) are deliberately absent.
#
# CONTRACTS DECLARED HERE
# -----------------------
# CanonicalFlow ........ output of ingestion, input to graph
# Host ................. discovered enterprise host
# TemporalSnapshot ..... output of graph builder, input to detection
# EdgeFeatures ......... per-edge feature vector
# NodeFeatures ......... per-host feature vector
# LMScore .............. output of TGNN detector
# ReconScore ........... output of recon detector
# SuspicionScore ....... output of fusion engine
# Alert ................ atomic SOC alert
# AttackPath ........... reconstructed attack chain
# WSEvent .............. WebSocket envelope to the SOC UI
# =============================================================================

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


# -----------------------------------------------------------------------------
# Enumerations
# -----------------------------------------------------------------------------
class Severity(str, Enum):
    """Standard SOC severity ladder. Mirrors STIX 2.1 confidence levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Protocol(str, Enum):
    """Transport-layer protocols carried in CanonicalFlow."""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    OTHER = "other"


class DetectionKind(str, Enum):
    """Origin of a score / alert — used by the fusion + correlation engines."""
    LM = "lateral_movement"            # produced by TGNN
    RECON = "reconnaissance"           # produced by heuristic recon detector
    FUSION = "fusion"                  # produced by suspicion fusion
    CORRELATION = "correlation"        # produced by correlation engine


class DetectorName(str, Enum):
    """Canonical detector identifiers used across detection/fusion/correlation."""

    RECON = "recon"
    TGNN = "tgnn_lm"
    FUSION = "fusion"
    CORRELATION = "correlation"
    SMB = "smb_detector"
    RDP = "rdp_detector"
    WINRM = "winrm_detector"
    LDAP_KERBEROS = "ldap_kerberos_detector"
    RARE_EDGE = "rare_edge_detector"
    PRIVILEGED_ACCESS = "privileged_asset_access_detector"
    PIVOT = "pivot_detector"


class WSChannel(str, Enum):
    """WebSocket channel names shared with the frontend."""

    ALERTS = "alerts"
    GRAPH = "graph"
    HOSTS = "hosts"
    FLOWS = "flows"
    HEALTH = "health"
    TIMELINE = "timeline"


class WSEventName(str, Enum):
    """Canonical WebSocket event names shared with the frontend."""

    ALERT_NEW = "alert.new"
    ALERT_UPDATE = "alert.update"
    GRAPH_UPDATE = "graph.update"
    HOST_RISK = "host.risk"
    FLOW_NEW = "flow.new"
    PATH_NEW = "path.new"
    HEALTH_HEARTBEAT = "health.heartbeat"


class BaseSchemaModel(BaseModel):
    """Shared model config for all LateD schemas."""

    model_config = ConfigDict(use_enum_values=True, extra="forbid")


# -----------------------------------------------------------------------------
# CanonicalFlow
# -----------------------------------------------------------------------------
class CanonicalFlow(BaseSchemaModel):
    """
    Output of the ingestion module — the SINGLE input shape consumed by the
    graph builder. Every downstream module assumes this is already validated.
    """

    flow_id: str
    ts: datetime
    src_host: str
    dst_host: str
    src_port: int = Field(ge=0, le=65535)
    dst_port: int = Field(ge=0, le=65535)
    protocol: Protocol
    duration: float = Field(ge=0)
    packet_count: int = Field(ge=0)
    byte_count: int = Field(ge=0)
    source_sensor: str
    schema_version: str = SCHEMA_VERSION


# -----------------------------------------------------------------------------
# Host
# -----------------------------------------------------------------------------
class Host(BaseSchemaModel):
    """
    Represents a discovered enterprise host. Produced by the discovery module
    and persisted in the host registry.
    """

    host_id: str
    ip_addresses: list[str]
    hostname: str | None = None
    subnet: str | None = None
    first_seen: datetime
    last_seen: datetime
    os_guess: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


class HostRiskPoint(BaseSchemaModel):
    """Point-in-time host risk used by the frontend sparkline views."""

    ts: datetime
    risk: float = Field(ge=0, le=1)


class HostRiskSummary(BaseSchemaModel):
    """Compact host risk summary used by overview and hosts views."""

    host_id: str
    hostname: str | None = None
    subnet: str | None = None
    current_risk: float = Field(ge=0, le=1)
    last_alert_at: datetime | None = None
    active_alerts: int = Field(ge=0)


class HostHeatmapCell(BaseSchemaModel):
    """Per-neighbor communication intensity summary for host heatmaps."""

    neighbor_host_id: str
    intensity: float = Field(ge=0, le=1)
    bytes: int = Field(ge=0)
    packets: int = Field(ge=0)


# -----------------------------------------------------------------------------
# Temporal graph payloads
# -----------------------------------------------------------------------------
class EdgeFeatures(BaseSchemaModel):
    """Per-edge feature vector built by graph.edge_features."""

    bytes: float
    packets: float
    duration: float
    port_entropy: float
    fan_out: float
    fan_in: float
    temporal_delta: float


class NodeFeatures(BaseSchemaModel):
    """Per-host feature vector built by graph.node_features."""

    fan_out: float
    fan_in: float
    unique_neighbors: int
    communication_frequency: float
    historical_risk: float


class TemporalSnapshot(BaseSchemaModel):
    """
    A non-overlapping time window of the temporal graph.
    Consumed by both detectors (TGNN, recon).
    """

    snapshot_id: str
    window_start: datetime
    window_end: datetime
    nodes: list[str]
    edges: list[tuple[str, str]]
    edge_features: dict[str, EdgeFeatures]
    node_features: dict[str, NodeFeatures]
    schema_version: str = SCHEMA_VERSION


class DetectorSignal(BaseSchemaModel):
    """Shared detector output contract for all current and future detectors."""

    detector: DetectorName
    kind: DetectionKind
    window_start: datetime
    subject_host: str
    score: float = Field(ge=0, le=1)
    target_hosts: list[str] = Field(default_factory=list)
    protocol: str | None = None
    triggered_signals: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    mitre_tags: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    critical_asset_touched: bool = False
    new_relation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


# -----------------------------------------------------------------------------
# Detection outputs
# -----------------------------------------------------------------------------
class LMScore(BaseSchemaModel):
    """TGNN output for a single host/edge in a given window."""

    window_start: datetime
    subject_host: str
    score: float = Field(ge=0, le=1)
    contributing_edges: list[tuple[str, str]]
    model_version: str
    detector: DetectorName = DetectorName.TGNN
    kind: DetectionKind = DetectionKind.LM
    target_hosts: list[str] = Field(default_factory=list)
    protocol: str | None = None
    triggered_signals: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    mitre_tags: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    critical_asset_touched: bool = False
    new_relation: bool = False
    explainability: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


class ReconScore(BaseSchemaModel):
    """Heuristic recon detector output for a host in a sliding window."""

    window_start: datetime
    subject_host: str
    score: float = Field(ge=0, le=1)
    unique_destinations: int
    unique_dst_ports: int
    burst_rate: float
    detector: DetectorName = DetectorName.RECON
    kind: DetectionKind = DetectionKind.RECON
    target_hosts: list[str] = Field(default_factory=list)
    protocol: str | None = None
    triggered_signals: list[str]
    evidence: list[str] = Field(default_factory=list)
    mitre_tags: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    critical_asset_touched: bool = False
    new_relation: bool = False
    schema_version: str = SCHEMA_VERSION


class SuspicionScore(BaseSchemaModel):
    """
    Fused score combining LM + recon + historical risk.
    This is the canonical "host is suspicious" signal consumed by correlation.
    """

    window_start: datetime
    subject_host: str
    score: float = Field(ge=0, le=1)
    detector: DetectorName = DetectorName.FUSION
    kind: DetectionKind = DetectionKind.FUSION
    lm_contribution: float
    recon_contribution: float
    history_contribution: float
    explainability: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


# -----------------------------------------------------------------------------
# Alerts & attack paths
# -----------------------------------------------------------------------------
class Alert(BaseSchemaModel):
    """
    Atomic SOC alert. Emitted to the alert engine and the WebSocket fanout.
    The `alert_id` is correlatable with upstream SIEMs / SOAR.
    """

    alert_id: str
    created_at: datetime
    severity: Severity
    kind: DetectionKind
    subject_host: str
    description: str
    score: float = Field(ge=0, le=1)
    evidence: list[str]
    mitre_tags: list[str] = Field(default_factory=list)
    explainability: dict[str, Any] = Field(default_factory=dict)
    status: str = "open"
    schema_version: str = SCHEMA_VERSION


class AttackPath(BaseSchemaModel):
    """
    Output of the correlation engine — a reconstructed multi-step attack.
    Always chronological. May span minutes to hours.
    """

    path_id: str
    created_at: datetime
    hosts: list[str]
    pivot_hosts: list[str]
    timeline: list[Alert]
    path_confidence: float = Field(ge=0, le=1)
    mitre_tactic_chain: list[str] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


# -----------------------------------------------------------------------------
# WebSocket envelope
# -----------------------------------------------------------------------------
class WSEvent(BaseSchemaModel):
    """
    Canonical envelope for every WebSocket frame sent to the SOC UI.
    `channel` identifies the destination panel in the dashboard.
    """

    channel: WSChannel
    event: WSEventName
    payload: dict[str, Any]
    ts: datetime
    schema_version: str = SCHEMA_VERSION
