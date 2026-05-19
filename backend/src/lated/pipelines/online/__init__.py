# =============================================================================
# lated.pipelines.online — Online Detection Pipeline
# =============================================================================
#
# PURPOSE
# -------
# Real-time orchestration of all online stages:
#   1. Discovery (one-shot at startup if no baseline persisted).
#   2. Ingestion (continuous).
#   3. Graph building.
#   4. TGNN inference + recon detection (in parallel).
#   5. Fusion -> Correlation -> Alert engine -> WebSocket fanout.
#
# FILES
# -----
#   stream_orchestrator : wires the async streams together
#   pipeline_runner     : entrypoint (`lated-online`)
#   runtime_controller  : exposes start/stop/reload to admin endpoints
# =============================================================================
