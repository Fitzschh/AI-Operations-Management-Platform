"""/health/ready reports dependency wiring for deploy verification (Railway checklist step)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from touchorders_core.api.app import create_app
from touchorders_core.api.auth import FakeIdentityVerifier
from touchorders_core.domain.enums import AgentName
from touchorders_core.llm.budget import BudgetTracker, DailyBudget
from touchorders_core.llm.gateway import FakeLLMClient, LLMGateway
from touchorders_core.settings import Settings


def _settings() -> Settings:
    return Settings(environment="test", log_json=False)


def test_ready_reports_degraded_when_nothing_is_wired() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        body = client.get("/health/ready").json()
    assert body == {"status": "degraded", "database": "unconfigured", "firebase": "unconfigured", "openai": "unconfigured"}


def test_ready_reports_healthy_when_all_dependencies_are_wired(repos) -> None:
    gateway = LLMGateway({}, FakeLLMClient(), repos.llm_calls, repos.audit, budget=BudgetTracker({AgentName.BUSINESS_ANALYST: DailyBudget(input=1, output=1)}))
    app = create_app(_settings(), gateway=gateway, identity_verifier=FakeIdentityVerifier(), db_ping=lambda: True)
    with TestClient(app) as client:
        body = client.get("/health/ready").json()
    assert body == {"status": "healthy", "database": "ok", "firebase": "ok", "openai": "ok"}


def test_ready_reports_database_error_without_raising() -> None:
    def broken_ping() -> bool:
        raise RuntimeError("db down")

    app = create_app(_settings(), db_ping=broken_ping)
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "error"
