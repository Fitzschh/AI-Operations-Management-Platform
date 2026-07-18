"""SQLAlchemy persistence models. ORM rows do not leave datastore repositories."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from touchorders_core.domain.common import utc_now


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes across engines.

    SQLite has no native timezone and returns naive datetimes, which then raise ``TypeError`` when
    compared against the aware timestamps the domain produces (e.g. the suppression cooldown check).
    This decorator normalizes values to UTC on the way in and re-attaches UTC on the way out so
    every Python-level time comparison is aware-vs-aware, on both SQLite and PostgreSQL.
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


class TenantRow:
    tenant_id: Mapped[str] = mapped_column(String(80), default="default", index=True)


class InventoryItemRow(Base, TenantRow):
    __tablename__ = "inventory_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sku: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="uncategorized")
    unit: Mapped[str] = mapped_column(String(24), default="unit")
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    reorder_threshold: Mapped[float] = mapped_column(Float, default=20)
    supplier_id: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
    __table_args__ = (UniqueConstraint("tenant_id", "sku", name="uq_inventory_tenant_sku"),)


class OrderRow(Base, TenantRow):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    placed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    channel: Mapped[str] = mapped_column(String(80), nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "external_id", name="uq_order_tenant_external"),)


class SaleRow(Base, TenantRow):
    __tablename__ = "sales"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_external_id: Mapped[str | None] = mapped_column(String(120), index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_type: Mapped[str] = mapped_column(String(80), default="unknown")


class KitchenTicketRow(Base, TenantRow):
    __tablename__ = "kitchen_tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_external_id: Mapped[str | None] = mapped_column(String(120), index=True)
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    station: Mapped[str] = mapped_column(String(80), default="kitchen")


class MenuItemRow(Base, TenantRow):
    __tablename__ = "menu_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="uncategorized")
    price: Mapped[float] = mapped_column(Float, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    recipe: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)


class OperationalEventRow(Base, TenantRow):
    __tablename__ = "operational_events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    entity: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    dedup_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(24), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (Index("ix_events_queue", "status", "severity", "detected_at"),)


class RuleStateRow(Base, TenantRow):
    __tablename__ = "rules_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    cooldown_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    active_fingerprint: Mapped[str | None] = mapped_column(String(128))
    fires_in_window: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cleared: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "rule_id", "entity_id", name="uq_rule_state"),)


class BaselineRow(Base, TenantRow):
    __tablename__ = "baselines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_id: Mapped[str] = mapped_column(String(160), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    hour_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    mean: Mapped[float] = mapped_column(Float, nullable=False)
    trimmed_mean: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    __table_args__ = (UniqueConstraint("tenant_id", "metric_id", "entity_id", "hour_of_week", name="uq_baseline"),)


class MetricWindowRow(Base, TenantRow):
    __tablename__ = "metric_windows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_id: Mapped[str] = mapped_column(String(160), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    bucket_start: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    n: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint("tenant_id", "metric_id", "entity_id", "bucket_start", name="uq_metric_bucket"),)


class IngestionReceiptRow(Base):
    __tablename__ = "ingestion_receipts"
    source: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class KPISnapshotRow(Base, TenantRow):
    __tablename__ = "kpi_snapshots"
    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    period_start: Mapped[datetime] = mapped_column(UTCDateTime())
    period_end: Mapped[datetime] = mapped_column(UTCDateTime())
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class IncidentRow(Base, TenantRow):
    __tablename__ = "incidents"
    incident_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class BusinessReportRow(Base, TenantRow):
    __tablename__ = "business_reports"
    report_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kpi_snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_snapshots.snapshot_id"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ActionPlanRow(Base, TenantRow):
    __tablename__ = "action_plans"
    plan_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False)
    revision_of: Mapped[str | None] = mapped_column(String(36))
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class PlanStepRow(Base):
    __tablename__ = "plan_steps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("action_plans.plan_id"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    tool_version: Mapped[int] = mapped_column(Integer, nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    risk_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    __table_args__ = (UniqueConstraint("plan_id", "step_no", name="uq_plan_step"),)


class ApprovalRequestRow(Base):
    __tablename__ = "approval_requests"
    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("action_plans.plan_id"), unique=True)
    state: Mapped[str] = mapped_column(String(24), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    decided_by: Mapped[str | None] = mapped_column(String(120))
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    decision: Mapped[str | None] = mapped_column(String(24))
    note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


class WorkflowExecutionRow(Base):
    __tablename__ = "workflow_executions"
    workflow_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("action_plans.plan_id"))
    template_name: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(40), index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    failure: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class WorkflowStepExecutionRow(Base):
    __tablename__ = "workflow_step_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflow_executions.workflow_id"))
    step_no: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    compensated: Mapped[bool] = mapped_column(Boolean, default=False)


class ToolInvocationRow(Base):
    __tablename__ = "tool_invocations"
    invocation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tool_name: Mapped[str] = mapped_column(String(80))
    tool_version: Mapped[int] = mapped_column(Integer)
    caller: Mapped[str] = mapped_column(String(120))
    args_hash: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    correlation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class AgentMessageRow(Base):
    __tablename__ = "agent_messages"
    message_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(48), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    dedup_key: Mapped[str] = mapped_column(String(160), unique=True)


class MemoryRow(Base):
    __tablename__ = "agent_memory"
    memory_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    key: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    correlation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    __table_args__ = (UniqueConstraint("agent", "key", name="uq_memory_namespace_key"),)


class LLMCallRow(Base):
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
