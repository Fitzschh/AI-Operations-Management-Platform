"""Shared fixtures: an isolated SQLite database with the AI-system-state repositories wired.

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
from touchorders_core.datastore.repositories import AuditRepository, LLMCallRepository
from touchorders_core.observability.audit import AuditLogger


@dataclass
class Repositories:
    factory: sessionmaker[Session]
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
        llm_calls=LLMCallRepository(session_factory),
        audit_repo=audit_repo,
        audit=AuditLogger(audit_repo),
    )
