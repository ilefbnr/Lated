# =============================================================================
# lated.discovery — Network Discovery Module
# =============================================================================
#
# ROLE IN ARCHITECTURE
# --------------------
# The bootstrap module. Runs ONCE (or on operator-triggered re-discovery) to
# learn the enterprise infrastructure that the platform will subsequently
# monitor. Produces the BASELINE GRAPH used as the initial state of the
# temporal graph builder.
#
# SUBMODULES
# ----------
#   discovery_service   : orchestrator — selects mode (passive/active/hybrid)
#   passive_discovery   : learns hosts from ARP / DNS / NetFlow without probing
#   active_discovery    : opt-in active probing (ICMP / TCP SYN) — privileged
#   topology_builder    : turns raw observations into a topology graph
#   host_registry       : canonicalizes hosts (IP churn, multi-interface)
#   baseline_graph      : final, persisted baseline used by the graph module
#
# INPUTS  : passive traffic, ARP, DNS, optional Nmap-like scans
# OUTPUTS : Host[] + BaselineGraph
#
# CYBERSECURITY REASONING
# -----------------------
# Discovery itself is a sensitive operation:
#   - Active scans can trigger upstream IDS or impact fragile devices.
#   - Passive mode is therefore the default and SHOULD cover most environments.
# Hybrid mode is offered for greenfield deployments where passive observation
# would take too long to converge.
# =============================================================================
