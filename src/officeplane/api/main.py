import os
from fastapi import FastAPI
from officeplane.api.routes import router
from officeplane.api.middleware import RequestIdMiddleware
from officeplane.observability.logging import configure_logging

def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="OfficePlane", version=os.getenv("OFFICEPLANE_VERSION", "0.1.0"))
    app.add_middleware(RequestIdMiddleware)
    app.include_router(router)
    return app

app = create_app()
