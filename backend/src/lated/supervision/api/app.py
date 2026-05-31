# =============================================================================
# lated.supervision.api.app — FastAPI application factory
# =============================================================================
#
# PURPOSE
# -------
# Builds the ASGI application served by uvicorn. Wires:
#   - all REST routers,
#   - the WebSocket server,
#   - global middleware (auth, request_id, CORS, rate limit),
#   - exception handlers (mapping LatedError -> HTTP status).
#
# INPUTS  : AppConfig (from ConfigManager)
# OUTPUTS : FastAPI instance ready for uvicorn.
#
# INTERACTIONS
# ------------
#   - main.run_api : caller.
#   - All routers + websocket : included here.
#
# CYBERSECURITY REASONING
# -----------------------
# The factory is the single place where security middleware is mounted.
# Centralizing it ensures no router can accidentally bypass auth.
# =============================================================================

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from lated.discovery.host_registry import HostRegistry
from lated.common.config_manager import ConfigManager
from lated.supervision.discovery_workflow import DiscoveryWorkflow
from lated.supervision.alerts.alert_repository import AlertRepository
from lated.supervision.api.routes_alerts import router as alerts_router
from lated.supervision.api.routes_attack_paths import router as paths_router
from lated.supervision.api.routes_auth import router as auth_router
from lated.supervision.api.routes_baseline import router as baseline_router
from lated.supervision.api.routes_discovery import router as discovery_router
from lated.supervision.api.routes_flows import router as flows_router
from lated.supervision.api.routes_graph import router as graph_router
from lated.supervision.api.routes_health import router as health_router
from lated.supervision.api.routes_hosts import router as hosts_router
from lated.supervision.api.routes_realtime import router as realtime_router
from lated.supervision.auth import authenticate_websocket
from lated.supervision.realtime_graph import RealtimeGraphProcessor
from lated.supervision.flows_repository import FlowsRepository
from lated.supervision.graph_repository import GraphRepository
from lated.supervision.hosts_repository import HostsRepository
from lated.supervision.live_detection_pipeline import LiveDetectionPipeline
from lated.supervision.paths_repository import PathsRepository
from lated.supervision.zeek_live_runtime import ZeekLiveRuntime
from lated.supervision.storage.event_store import EventStore
from lated.supervision.storage.persistence import Persistence
from lated.supervision.websocket.ws_channels import WSChannels
from lated.supervision.websocket.ws_server import WSServer


def _default_baseline_path() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "baseline" / "latest.json"


def _default_registry_path() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "discovery" / "host_registry.json"


def create_app(
    config,
    baseline_path: str | Path | None = None,
    supervision_db_path: str | Path | None = None,
):
    """Construct the FastAPI ASGI app.

    Steps
    -----
      1. fastapi.FastAPI(title="LateD", version=...)
      2. Mount middleware: request_id, auth (bearer), CORS, rate limit.
      3. Register exception handlers: LatedError -> 4xx/5xx mapping.
      4. Include routers: alerts, hosts, graph, paths, flows, health, admin.
      5. Register WebSocket route group via supervision.websocket.ws_server.
      6. Register startup/shutdown hooks (DB pool, redis, model warm-up).
    """
    app = FastAPI(title="LateD", version="0.1.0")
    app.state.config = config
    app.state.config_manager = ConfigManager
    app.state.backend_root = Path(__file__).resolve().parents[4]
    persistence = Persistence()
    persistence.configure(config, database_path=supervision_db_path)
    app.state.persistence = persistence
    app.state.event_store = EventStore(persistence.get_session)
    app.state.alert_repository = AlertRepository(persistence.get_session)
    app.state.hosts_repository = HostsRepository(persistence.get_session)
    resolved_baseline_path = Path(baseline_path) if baseline_path is not None else _default_baseline_path()
    app.state.baseline_path = resolved_baseline_path
    app.state.registry_path = _default_registry_path()
    app.state.discovery_workflow = DiscoveryWorkflow(
        backend_root=app.state.backend_root,
        baseline_path=app.state.baseline_path,
        registry_path=app.state.registry_path,
        event_store=app.state.event_store,
    )
    network_topology = config.network_topology.topology
    app.state.network_topology = network_topology
    app.state.graph_repository = GraphRepository(
        persistence.get_session,
        baseline_path=resolved_baseline_path,
        network_topology=network_topology,
    )
    app.state.flows_repository = FlowsRepository(persistence.get_session)
    app.state.paths_repository = PathsRepository(
        persistence.get_session,
        alert_repository=app.state.alert_repository,
        graph_repository=app.state.graph_repository,
    )
    app.state.ws_channels = WSChannels()
    app.state.ws_server = WSServer(
        channels=app.state.ws_channels,
        auth=(lambda websocket: authenticate_websocket(websocket, config.supervision.ws_auth_required)),
        heartbeat_seconds=config.supervision.ws_heartbeat_seconds,
    )
    app.state.realtime_host_registry = HostRegistry()
    app.state.realtime_graph = RealtimeGraphProcessor(
        publisher=app.state.ws_channels,
        host_registry=app.state.realtime_host_registry,
        network_topology=network_topology,
    )

    # --- Live detection pipeline ---------------------------------------
    # Constructed only when the source is Zeek; reuses the offline
    # `build_components` to assemble detectors/fusion/correlation with the
    # exact same wiring as the batch orchestrator.
    app.state.live_detection_pipeline = None
    if str(config.ingestion.source) == "zeek":
        try:
            from lated.pipelines.online.pipeline_runner import build_components
            supervision_db = persistence.database_path if hasattr(persistence, "database_path") else (
                app.state.backend_root / "data" / "supervision.sqlite3"
            )
            graph_store_path = app.state.backend_root / "data" / "graph" / "snapshots.sqlite3"
            graph_store_path.parent.mkdir(parents=True, exist_ok=True)
            components = build_components(
                config,
                supervision_db_path=str(supervision_db),
                graph_store_path=str(graph_store_path),
                host_registry=app.state.realtime_host_registry,
            )
            app.state.detection_components = components
            app.state.live_detection_pipeline = LiveDetectionPipeline(
                graph_builder=components.graph_builder,
                recon_detector=components.recon_detector,
                smb_detector=components.smb_detector,
                rdp_detector=components.rdp_detector,
                winrm_detector=components.winrm_detector,
                rare_edge_detector=components.rare_edge_detector,
                mitre_rules_detector=components.mitre_rules_detector,
                lm_inference=components.lm_inference,
                fusion=components.fusion,
                correlation=components.correlation,
                alert_engine=components.alert_engine,
                correlation_store=components.correlation_store,
                ws_channels=app.state.ws_channels,
                window_seconds=int(config.graph.snapshot_window_seconds),
            )
        except Exception as exc:
            # Live detection is best-effort. If wiring fails (missing model,
            # missing baseline, etc.) the live graph still works.
            app.state.live_detection_pipeline = None
            app.state.live_detection_error = f"{type(exc).__name__}: {exc}"

    app.state.zeek_live_runtime = ZeekLiveRuntime(
        config=config,
        host_registry=app.state.realtime_host_registry,
        realtime_graph=app.state.realtime_graph,
        ws_channels=app.state.ws_channels,
        detection_pipeline=app.state.live_detection_pipeline,
        hosts_repository=app.state.hosts_repository,
        flows_repository=app.state.flows_repository,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(discovery_router)
    app.include_router(alerts_router)
    app.include_router(hosts_router)
    app.include_router(graph_router)
    app.include_router(flows_router)
    app.include_router(paths_router)
    app.include_router(realtime_router)
    app.include_router(baseline_router)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await app.state.ws_server.endpoint(websocket)

    # Periodic save of the evolving rare-edge baseline. Lives only as long
    # as the app does; cancelled on shutdown.
    app.state._baseline_save_task = None

    @app.on_event("startup")
    async def _startup_live_runtime() -> None:
        if str(config.ingestion.source) == "zeek" and str(config.ingestion.mode) in {"live", "replay_live"}:
            app.state.zeek_live_runtime.start()
        # Schedule baseline auto-save every 60s so the memory persists.
        components = getattr(app.state, "detection_components", None)
        if components is not None and getattr(components, "rare_edge_detector", None) is not None:
            import asyncio
            async def _baseline_saver():
                detector = components.rare_edge_detector
                while True:
                    try:
                        await asyncio.sleep(60)
                    except asyncio.CancelledError:
                        break
                    if hasattr(detector, "is_dirty") and detector.is_dirty():
                        try:
                            detector.save()
                        except Exception:
                            pass
            app.state._baseline_save_task = asyncio.create_task(_baseline_saver())

    @app.on_event("shutdown")
    async def _shutdown_live_runtime() -> None:
        app.state.zeek_live_runtime.stop()
        task = getattr(app.state, "_baseline_save_task", None)
        if task is not None:
            task.cancel()
        # Final flush of the baseline so we don't lose the in-memory updates.
        components = getattr(app.state, "detection_components", None)
        if components is not None and getattr(components, "rare_edge_detector", None) is not None:
            try:
                components.rare_edge_detector.save()
            except Exception:
                pass

    return app
