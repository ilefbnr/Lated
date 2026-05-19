# =============================================================================
# lated.ingestion — Ingestion Module
# =============================================================================
#
# ROLE IN ARCHITECTURE
# --------------------
# The validation curtain of the platform. Receives untrusted telemetry from
# PCAP / Zeek / NetFlow sources and converts it into validated CanonicalFlow
# records. NO module downstream of ingestion ever parses raw bytes.
#
# SUBMODULES
# ----------
#   ingestion_service   : top-level dispatcher
#   pcap_parser         : packet capture parser (scapy)
#   zeek_parser         : Zeek conn.log parser
#   netflow_parser      : NetFlow v5 / v9 / IPFIX parser
#   flow_normalizer     : sensor-specific -> canonical schema
#   flow_validator      : schema + range validation, fail-loud
#   canonical_schema    : helpers around CanonicalFlow construction
#
# INPUTS  : raw PCAP / Zeek logs / NetFlow datagrams
# OUTPUTS : stream of validated CanonicalFlow records
#
# CYBERSECURITY REASONING
# -----------------------
# Ingestion is the ONLY trust boundary. Every assumption made here is the
# last line of defence before adversary-controlled bytes reach AI logic.
# Therefore this module is:
#   - isolated  : no AI dependencies, no model loading,
#   - bounded   : all numeric fields range-checked,
#   - replayable: every accepted flow is persistable for forensic replay.
# =============================================================================
