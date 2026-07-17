"""Shared fixtures: an isolated SQLite database with every repository wired.

A file-backed database per test (not ``:memory:``) is used deliberately so the repositories'
session-per-operation pattern sees a single shared database across sessions, exactly as it does
in the running process.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from touchorders_core.datastore.engine import create_database_engine, create_session_factory, initialize_schema
from touchorders_core.datastore.repositories import (
    AnalyticsRepository, ApprovalRepository, AuditRepository, DomainRepository, IncidentRepository,
    LLMCallRepository, MemoryRepository, MessageRepository, OperationalEventRepository,
    PlanRepository, ReportRepository, RuleStateRepository, ToolInvocationRepository, WorkflowRepository,
)
from touchorders_core.observability.audit import AuditLogger


@dataclass
class Repositories:
    factory: sessionmaker[Session]
    domain: DomainRepository
    events: OperationalEventRepository
    rule_state: RuleStateRepository
    analytics: AnalyticsRepository
    incidents: IncidentRepository
    reports: ReportRepository
    plans: PlanRepository
    approvals: ApprovalRepository
    workflows: WorkflowRepository
    tool_invocations: ToolInvocationRepository
    messages: MessageRepository
    memory: MemoryRepository
    llm_calls: LLMCallRepository
    audit_repo: AuditRepository
    audit: AuditLogger


@pytest.fixture()
def session_factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    initialize_schema(engine)
    return create_session_factory(engine)


@pytest.fixture()
def repos(session_factory: sessionmaker[Session]) -> Repositories:
    audit_repo = AuditRepository(session_factory)
    return Repositories(
        factory=session_factory,
        domain=DomainRepository(session_factory),
        events=OperationalEventRepository(session_factory),
        rule_state=RuleStateRepository(session_factory),
        analytics=AnalyticsRepository(session_factory),
        incidents=IncidentRepository(session_factory),
        reports=ReportRepository(session_factory),
        plans=PlanRepository(session_factory),
        approvals=ApprovalRepository(session_factory),
        workflows=WorkflowRepository(session_factory),
        tool_invocations=ToolInvocationRepository(session_factory),
        messages=MessageRepository(session_factory),
        memory=MemoryRepository(session_factory),
        llm_calls=LLMCallRepository(session_factory),
        audit_repo=audit_repo,
        audit=AuditLogger(audit_repo),
    )
