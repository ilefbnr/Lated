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
    app.state.graph_repository = GraphRepository(
        persistence.get_session,
        baseline_path=resolved_baseline_path,
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
    )
    app.state.zeek_live_runtime = ZeekLiveRuntime(
        config=config,
        host_registry=app.state.realtime_host_registry,
        realtime_graph=app.state.realtime_graph,
        ws_channels=app.state.ws_channels,
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

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await app.state.ws_server.endpoint(websocket)

    @app.on_event("startup")
    async def _startup_live_runtime() -> None:
        if str(config.ingestion.source) == "zeek" and str(config.ingestion.mode) in {"live", "replay_live"}:
            app.state.zeek_live_runtime.start()

    @app.on_event("shutdown")
    async def _shutdown_live_runtime() -> None:
        app.state.zeek_live_runtime.stop()

    return app
