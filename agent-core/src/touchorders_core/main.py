"""Composition root for the TouchOrders Agent Core process (FastAPI on Railway)."""

from __future__ import annotations

import os

import uvicorn

from touchorders_core.api.app import create_app
from touchorders_core.api.auth import FirebaseIdentityVerifier
from touchorders_core.datastore.engine import create_database_engine, create_session_factory, initialize_schema
from touchorders_core.datastore.repositories import AuditRepository, LLMCallRepository
from touchorders_core.llm.budget import BudgetTracker
from touchorders_core.llm.gateway import LLMGateway, OpenAIClient, default_daily_budgets
from touchorders_core.observability.audit import AuditLogger
from touchorders_core.observability.logging import configure_logging, get_logger
from touchorders_core.settings import Settings, get_settings


def build_app(settings: Settings | None = None):
    """Wire the production BFF: real LLM Gateway + Firebase verifier when their credentials are
    present (Railway env), otherwise a healthy app whose AI routes return 503 until configured."""

    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)
    logger = get_logger(__name__)

    gateway = None
    if os.environ.get("OPENAI_API_KEY"):  # the key is read by OpenAIClient, never a Settings field (§14.1)
        try:
            engine = create_database_engine(settings.database_url)
            initialize_schema(engine)  # hackathon; production runs Alembic (§12.1)
            sessions = create_session_factory(engine)
            gateway = LLMGateway(
                {}, OpenAIClient(), LLMCallRepository(sessions), AuditLogger(AuditRepository(sessions)),
                budget=BudgetTracker(default_daily_budgets()),
            )
        except Exception as exc:  # noqa: BLE001 - degrade to AI-disabled rather than crash boot
            logger.warning("llm_gateway_unconfigured", error=str(exc))
    else:
        logger.warning("openai_api_key_absent", detail="AI routes disabled until OPENAI_API_KEY is set on Railway")

    verifier = None
    try:
        credential = settings.firebase_service_account_json.get_secret_value() if settings.firebase_service_account_json else None
        verifier = FirebaseIdentityVerifier(credential)
    except Exception as exc:  # noqa: BLE001 - firebase-admin/cred absent -> auth-gated routes 503
        logger.warning("firebase_verifier_unconfigured", error=str(exc))

    return create_app(settings, gateway=gateway, identity_verifier=verifier)


app = build_app()


def main() -> None:
    """Start the FastAPI process; Railway supplies PORT."""

    settings = get_settings()
    uvicorn.run(
        "touchorders_core.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        log_config=None,
        reload=settings.environment == "development",
    )
