import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from officeplane.api.routes import router
from officeplane.api.management_routes import router as management_router
from officeplane.api.generate_routes import router as generate_router
from officeplane.api.team_routes import router as team_router
from officeplane.api.skills_routes import router as skills_router
from officeplane.api.jobs_routes import router as jobs_router
from officeplane.api.sessions_routes import router as sessions_router
from officeplane.api.ecm.instances import router as ecm_instances_router
from officeplane.api.ecm.documents import router as ecm_documents_router
from officeplane.api.ecm.collections import router as ecm_collections_router
from officeplane.api.ecm.search import router as ecm_search_router
from officeplane.api.ecm.workflows import router as ecm_workflows_router
from officeplane.api.lineage_routes import router as lineage_router
from officeplane.api.workspace_routes import router as workspace_router
from officeplane.api.search_routes import router as search_router
from officeplane.api.middleware import RequestIdMiddleware
from officeplane.api.websocket import websocket_endpoint
from officeplane.observability.logging import configure_logging
from officeplane.management.db import get_db, disconnect_db
from officeplane.broker import get_broker, close_broker
from officeplane.management.task_queue import task_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events: startup and shutdown"""
    # Startup
    print("[OfficePlane] Starting up...")

    # Connect to database
    await get_db()
    print("[OfficePlane] Database connected")

    # Connect broker (memory or redis, based on OFFICEPLANE_BROKER)
    try:
        broker = await get_broker()
        print(f"[OfficePlane] Broker connected: {type(broker).__name__}")
    except Exception as e:
        print(f"[OfficePlane] Broker failed to connect: {e}")

    # Start task queue workers
    await task_queue.start_workers()
    print("[OfficePlane] Task queue workers started")

    yield

    # Shutdown
    print("[OfficePlane] Shutting down...")

    # Stop task queue workers
    await task_queue.stop_workers()
    print("[OfficePlane] Task queue workers stopped")

    # Disconnect broker
    await close_broker()
    print("[OfficePlane] Broker disconnected")

    # Disconnect database
    await disconnect_db()
    print("[OfficePlane] Database disconnected")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="OfficePlane",
        version=os.getenv("OFFICEPLANE_VERSION", "0.2.0"),
        lifespan=lifespan,
    )

    # IMPORTANT: Add CORS middleware FIRST so it can handle all responses
    # Middleware is executed in reverse order, so this runs last
    app.add_middleware(RequestIdMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins in development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(router)           # Original render routes
    app.include_router(management_router)  # Management system routes
    app.include_router(generate_router)  # Legacy content generation (kept for compat)
    app.include_router(team_router)      # Legacy agent team routes (kept for compat)
    app.include_router(skills_router)          # Skill discovery
    app.include_router(jobs_router)            # Agent run + skill-based jobs
    app.include_router(sessions_router)        # ECM atomic sessions
    app.include_router(ecm_instances_router)   # ECM: instance lifecycle + agent actions
    app.include_router(ecm_documents_router)   # ECM: metadata, permissions, audit, lifecycle
    app.include_router(ecm_collections_router) # ECM: collections/folders
    app.include_router(ecm_search_router)      # ECM: search + similarity
    app.include_router(ecm_workflows_router)   # ECM: approval workflows
    app.include_router(lineage_router)         # Lineage / provenance graph
    app.include_router(workspace_router)       # Workspace document JSON
    app.include_router(search_router)          # Semantic search
    from officeplane.api.diff_routes import router as diff_router
    app.include_router(diff_router)            # Revision diff
    from officeplane.api.categorize_routes import router as categorize_router
    app.include_router(categorize_router)      # Auto-categorize skill
    from officeplane.api.signed_download import router as signed_download_router
    app.include_router(signed_download_router)

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": os.getenv("OFFICEPLANE_VERSION", "0.2.0"),
            "service": "OfficePlane API"
        }

    # WebSocket endpoint for real-time updates
    @app.websocket("/ws")
    async def websocket_route(websocket: WebSocket):
        await websocket_endpoint(websocket)

    return app


app = create_app()

from officeplane.api.chat_routes import router as chat_router  # noqa: E402
app.include_router(chat_router)
from officeplane.api.validator_routes import router as validator_router  # noqa: E402
app.include_router(validator_router)
from officeplane.api.lifecycle_routes import router as lifecycle_router  # noqa: E402
app.include_router(lifecycle_router)
