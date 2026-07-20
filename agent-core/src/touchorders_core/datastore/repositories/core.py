"""Repositories for the two AI-system-state tables. The only SQL in the codebase.

No restaurant data repositories exist by design: Firebase Realtime Database is the sole
operational datastore, accessed directly by the clients under Firebase Security Rules.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from touchorders_core.datastore.orm import AuditLogRow, LLMCallRow
from touchorders_core.domain.common import uuid7


class Repository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def _session(self) -> Session:
        return self._sessions()


class LLMCallRepository(Repository):
    def add(self, **values: Any) -> None:
        with self._session() as session:
            session.add(LLMCallRow(call_id=str(uuid7()), **values))
            session.commit()


class AuditRepository(Repository):
    def last(self) -> AuditLogRow | None:
        with self._session() as session:
            return session.scalar(select(AuditLogRow).order_by(desc(AuditLogRow.seq)))

    def append(self, row: AuditLogRow) -> None:
        with self._session() as session:
            session.add(row)
            session.commit()

    def entries(self) -> list[AuditLogRow]:
        with self._session() as session:
            return list(session.scalars(select(AuditLogRow).order_by(AuditLogRow.seq)).all())
