"""FastAPI application factory and Stage 0 liveness endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from touchorders_core import __version__
from touchorders_core.observability.logging import configure_logging, get_logger
from touchorders_core.settings import Settings, get_settings


class HealthResponse(BaseModel):
    """Liveness response; readiness checks are introduced with persistence in Stage 1."""

    status: str
    service: str
    version: str
    environment: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the application without constructing future runtime services."""

    runtime_settings = settings or get_settings()
    configure_logging(level=runtime_settings.log_level, json_output=runtime_settings.log_json)
    logger = get_logger(__name__)

    app = FastAPI(
        title="TouchOrders Agent Core",
        version=__version__,
        description="Deterministic restaurant operations core with schema-constrained AI edges.",
    )

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        """Return process liveness without touching future dependencies."""

        logger.debug("health_checked")
        return HealthResponse(
            status="ok",
            service=runtime_settings.service_name,
            version=__version__,
            environment=runtime_settings.environment,
        )

    return app
