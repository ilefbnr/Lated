# =============================================================================
# lated.common.constants — well-known string identifiers
# =============================================================================
#
# PURPOSE
# -------
# Single source of truth for every "magic string" used across modules:
#   - WebSocket channel names,
#   - MITRE ATT&CK tactic/technique tags,
#   - Alert event names,
#   - Internal queue / topic names.
#
# Putting them here means a typo can't silently desync two modules.
#
# CYBERSECURITY REASONING
# -----------------------
# Standardized identifiers are required for correlation with external SIEMs
# and SOAR playbooks. MITRE tags in particular MUST match the canonical
# strings exactly — analysts pivot on them.
# =============================================================================

from __future__ import annotations

# -----------------------------------------------------------------------------
# WebSocket channels (must match frontend wsEvents.ts)
# -----------------------------------------------------------------------------
WS_CHANNEL_ALERTS = "alerts"
WS_CHANNEL_GRAPH = "graph"
WS_CHANNEL_HOSTS = "hosts"
WS_CHANNEL_FLOWS = "flows"
WS_CHANNEL_HEALTH = "health"
WS_CHANNEL_TIMELINE = "timeline"

# -----------------------------------------------------------------------------
# WebSocket event names
# -----------------------------------------------------------------------------
EVT_ALERT_NEW = "alert.new"
EVT_ALERT_UPDATE = "alert.update"
EVT_GRAPH_UPDATE = "graph.update"
EVT_HOST_RISK = "host.risk"
EVT_FLOW_NEW = "flow.new"
EVT_PATH_NEW = "path.new"
EVT_HEALTH_HEARTBEAT = "health.heartbeat"

# -----------------------------------------------------------------------------
# MITRE ATT&CK tags relevant to LateD's detection scope
# -----------------------------------------------------------------------------
MITRE_TA_DISCOVERY = "TA0007"          # Reconnaissance (post-compromise)
MITRE_TA_LATERAL_MOVEMENT = "TA0008"
MITRE_T_NETWORK_SERVICE_SCANNING = "T1046"
MITRE_T_REMOTE_SERVICES = "T1021"
MITRE_T_REMOTE_DESKTOP = "T1021.001"
MITRE_T_SMB_ADMIN_SHARES = "T1021.002"
MITRE_T_WMI = "T1047"

# -----------------------------------------------------------------------------
# Internal queue / Redis topic names
# -----------------------------------------------------------------------------
TOPIC_CANONICAL_FLOWS = "lated.flows.canonical"
TOPIC_SNAPSHOTS = "lated.graph.snapshots"
TOPIC_LM_SCORES = "lated.detect.lm"
TOPIC_RECON_SCORES = "lated.detect.recon"
TOPIC_SUSPICION = "lated.detect.suspicion"
TOPIC_ALERTS = "lated.alerts"

# -----------------------------------------------------------------------------
# Limits & sentinels
# -----------------------------------------------------------------------------
MAX_HOSTS_PER_SNAPSHOT = 100_000
MAX_EDGES_PER_SNAPSHOT = 5_000_000
UNKNOWN_HOST_ID = "unknown"
