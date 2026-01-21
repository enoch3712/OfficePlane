import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from officeplane.api.routes import router
from officeplane.api.management_routes import router as management_router
from officeplane.api.middleware import RequestIdMiddleware
from officeplane.api.websocket import websocket_endpoint
from officeplane.observability.logging import configure_logging
from officeplane.management.db import get_db, disconnect_db
from officeplane.management.task_queue import task_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events: startup and shutdown"""
    # Startup
    print("[OfficePlane] Starting up...")

    # Connect to database
    await get_db()
    print("[OfficePlane] Database connected")

    # Start task queue workers
    await task_queue.start_workers()
    print("[OfficePlane] Task queue workers started")

    yield

    # Shutdown
    print("[OfficePlane] Shutting down...")

    # Stop task queue workers
    await task_queue.stop_workers()
    print("[OfficePlane] Task queue workers stopped")

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
    app.include_router(router)  # Original render routes
    app.include_router(management_router)  # Management system routes

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
