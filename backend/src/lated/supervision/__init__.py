# =============================================================================
# lated.supervision — SOC Supervision Layer
# =============================================================================
#
# ROLE
# ----
# The analyst-facing surface of the platform. Exposes:
#   - REST API           : structured queries (alerts, hosts, graph, paths)
#   - WebSocket          : streaming events to the dashboard
#   - Alert engine       : converts SuspicionScore + AttackPath into Alert
#   - Persistence        : long-term storage of alerts and events
#
# SUBDIRECTORIES
# --------------
#   api/         : FastAPI application + routers
#   websocket/   : WebSocket server, channels, event publisher
#   alerts/      : alert engine + repository + severity mapping
#   storage/     : persistence backends (Postgres for alerts, etc.)
#
# CYBERSECURITY REASONING
# -----------------------
# The supervision layer is the EXTERNAL ATTACK SURFACE of the platform.
# Hardening priorities:
#   - all endpoints require auth (bearer token or mTLS),
#   - RBAC: analyst < supervisor < admin,
#   - rate limits to prevent UI from being weaponized into a DoS vector.
# =============================================================================
