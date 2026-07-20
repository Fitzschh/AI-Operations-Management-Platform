"""SQLAlchemy persistence models for AI system state ONLY.

Firebase Realtime Database is the one and only source of truth for restaurant data. This backend
persists exactly two things, both AI-related system state: the LLM token/cost ledger and the
hash-chained audit log. No restaurant operational data (inventory, orders, sales, menus,
analytics) may ever be stored here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from touchorders_core.domain.common import utc_now


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes across engines.

    SQLite has no native timezone and returns naive datetimes, which then raise ``TypeError`` when
    compared against the aware timestamps the domain produces. This decorator normalizes values to
    UTC on the way in and re-attaches UTC on the way out so every Python-level time comparison is
    aware-vs-aware, on both SQLite and PostgreSQL.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    pass


class LLMCallRow(Base):
    """Token/cost ledger: one row per gateway call (§14.3 accounting spine)."""

    __tablename__ = "llm_calls"
    call_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(String(32))
    request_hash: Mapped[str] = mapped_column(String(128), index=True)
    prompt_version: Mapped[str] = mapped_column(String(128))
    correlation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class AuditLogRow(Base):
    """Append-only, hash-chained audit record (tamper-evident; fail-closed writer)."""

    __tablename__ = "audit_log"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(120))
    correlation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64))
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    record_hash: Mapped[str] = mapped_column(String(64), unique=True)
