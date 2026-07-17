"""Composition root for the TouchOrders Agent Core process."""

from __future__ import annotations

import uvicorn

from touchorders_core.api.app import create_app
from touchorders_core.settings import get_settings


app = create_app()


def main() -> None:
    """Start the Stage 0 HTTP process using validated runtime settings."""

    settings = get_settings()
    uvicorn.run(
        "touchorders_core.main:app",
        host="0.0.0.0",
        port=8000,
        log_config=None,
        reload=settings.environment == "development",
    )
