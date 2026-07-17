"""Aggregate repositories; ORM rows stay inside this module."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session, sessionmaker

from touchorders_core.domain.common import uuid7, utc_now
from touchorders_core.domain.entities import InventoryItem, KitchenTicket, MenuItem, Order, Sale
from touchorders_core.domain.enums import AgentName, OperationalEventStatus
from touchorders_core.domain.events import OperationalEvent
from touchorders_core.domain.incidents import IncidentReport
from touchorders_core.domain.messages import AgentMessage
from touchorders_core.domain.plans import ActionPlan
from touchorders_core.domain.reports import BusinessReport, KPISnapshot
from touchorders_core.datastore.orm import (
    ActionPlanRow, AgentMessageRow, AuditLogRow, BaselineRow, BusinessReportRow, IncidentRow,
    InventoryItemRow, KPISnapshotRow, KitchenTicketRow, LLMCallRow, MemoryRow, MenuItemRow,
    MetricWindowRow, OperationalEventRow, OrderRow, RuleStateRow, SaleRow, IngestionReceiptRow,
    ApprovalRequestRow, WorkflowExecutionRow, WorkflowStepExecutionRow, ToolInvocationRow,
)


class Repository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def _session(self) -> Session:
        return self._sessions()


class DomainRepository(Repository):
    def claim_ingestion_receipt(self, source: str, source_id: str) -> bool:
        with self._session() as session:
            if session.get(IngestionReceiptRow, {"source": source, "source_id": source_id}):
                return False
            session.add(IngestionReceiptRow(source=source, source_id=source_id))
            session.commit()
            return True
    def upsert_inventory(self, item: InventoryItem) -> InventoryItem:
        with self._session() as session:
            row = session.scalar(select(InventoryItemRow).where(InventoryItemRow.tenant_id == item.tenant_id, InventoryItemRow.sku == item.sku))
            if row is None:
                row = InventoryItemRow(id=item.id, tenant_id=item.tenant_id, sku=item.sku, name=item.name, category=item.category, unit=item.unit, quantity=item.quantity, reorder_threshold=item.reorder_threshold, supplier_id=item.supplier_id, updated_at=item.updated_at)
                session.add(row)
            else:
                row.name, row.category, row.unit = item.name, item.category, item.unit
                row.quantity, row.reorder_threshold, row.supplier_id, row.updated_at = item.quantity, item.reorder_threshold, item.supplier_id, item.updated_at
            session.commit()
            return self._inventory(row)

    def get_inventory(self, sku: str, tenant_id: str = "default") -> InventoryItem | None:
        with self._session() as session:
            row = session.scalar(select(InventoryItemRow).where(InventoryItemRow.tenant_id == tenant_id, InventoryItemRow.sku == sku))
            return self._inventory(row) if row else None

    def list_inventory(self, *, item_ids: list[str] | None = None, category: str | None = None, tenant_id: str = "default") -> list[InventoryItem]:
        with self._session() as session:
            statement = select(InventoryItemRow).where(InventoryItemRow.tenant_id == tenant_id)
            if item_ids:
                statement = statement.where(InventoryItemRow.sku.in_(item_ids))
            if category:
                statement = statement.where(InventoryItemRow.category == category)
            return [self._inventory(row) for row in session.scalars(statement).all()]

    def upsert_order(self, order: Order) -> tuple[Order, bool]:
        with self._session() as session:
            row = session.scalar(select(OrderRow).where(OrderRow.tenant_id == order.tenant_id, OrderRow.external_id == order.external_id))
            created = row is None
            if row is None:
                row = OrderRow(id=order.id, tenant_id=order.tenant_id, external_id=order.external_id, placed_at=order.placed_at, status=order.status, total=float(order.total), channel=order.channel)
                session.add(row)
            else:
                row.status, row.total, row.channel = order.status, float(order.total), order.channel
            session.commit()
            return self._order(row), created

    def record_sale(self, sale: Sale) -> tuple[Sale, bool]:
        with self._session() as session:
            row = session.get(SaleRow, sale.id)
            if row is None:
                row = SaleRow(id=sale.id, tenant_id=sale.tenant_id, order_external_id=sale.order_external_id, occurred_at=sale.occurred_at, amount=float(sale.amount), payment_type=sale.payment_type)
                session.add(row)
                created = True
            else:
                created = False
            session.commit()
            return self._sale(row), created

    def upsert_ticket(self, ticket: KitchenTicket) -> tuple[KitchenTicket, bool]:
        with self._session() as session:
            row = session.get(KitchenTicketRow, ticket.id)
            created = row is None
            if row is None:
                row = KitchenTicketRow(id=ticket.id, tenant_id=ticket.tenant_id, order_external_id=ticket.order_external_id, opened_at=ticket.opened_at, closed_at=ticket.closed_at, station=ticket.station)
                session.add(row)
            else:
                row.closed_at, row.station = ticket.closed_at, ticket.station
            session.commit()
            return self._ticket(row), created

    def upsert_menu_item(self, item: MenuItem) -> MenuItem:
        with self._session() as session:
            row = session.get(MenuItemRow, item.id)
            if row is None:
                row = MenuItemRow(id=item.id, tenant_id=item.tenant_id, name=item.name, category=item.category, price=float(item.price), available=item.available, recipe=item.recipe)
                session.add(row)
            else:
                row.name, row.category, row.price, row.available, row.recipe = item.name, item.category, float(item.price), item.available, item.recipe
            session.commit()
            return self._menu(row)

    def sales_between(self, start: datetime, end: datetime, tenant_id: str = "default") -> list[Sale]:
        with self._session() as session:
            rows = session.scalars(select(SaleRow).where(SaleRow.tenant_id == tenant_id, SaleRow.occurred_at >= start, SaleRow.occurred_at < end)).all()
            return [self._sale(row) for row in rows]

    def orders_between(self, start: datetime, end: datetime, tenant_id: str = "default") -> list[Order]:
        with self._session() as session:
            rows = session.scalars(select(OrderRow).where(OrderRow.tenant_id == tenant_id, OrderRow.placed_at >= start, OrderRow.placed_at < end)).all()
            return [self._order(row) for row in rows]

    def closed_tickets_between(self, start: datetime, end: datetime, tenant_id: str = "default") -> list[KitchenTicket]:
        with self._session() as session:
            rows = session.scalars(select(KitchenTicketRow).where(KitchenTicketRow.tenant_id == tenant_id, KitchenTicketRow.closed_at.is_not(None), KitchenTicketRow.closed_at >= start, KitchenTicketRow.closed_at < end)).all()
            return [self._ticket(row) for row in rows]

    @staticmethod
    def _inventory(row: InventoryItemRow) -> InventoryItem:
        return InventoryItem(id=row.id, tenant_id=row.tenant_id, sku=row.sku, name=row.name, category=row.category, unit=row.unit, quantity=row.quantity, reorder_threshold=row.reorder_threshold, supplier_id=row.supplier_id, updated_at=row.updated_at)

    @staticmethod
    def _order(row: OrderRow) -> Order:
        return Order(id=row.id, tenant_id=row.tenant_id, external_id=row.external_id, placed_at=row.placed_at, status=row.status, total=Decimal(str(row.total)), channel=row.channel)

    @staticmethod
    def _sale(row: SaleRow) -> Sale:
        return Sale(id=row.id, tenant_id=row.tenant_id, order_external_id=row.order_external_id, occurred_at=row.occurred_at, amount=Decimal(str(row.amount)), payment_type=row.payment_type)

    @staticmethod
    def _ticket(row: KitchenTicketRow) -> KitchenTicket:
        return KitchenTicket(id=row.id, tenant_id=row.tenant_id, order_external_id=row.order_external_id, opened_at=row.opened_at, closed_at=row.closed_at, station=row.station)

    @staticmethod
    def _menu(row: MenuItemRow) -> MenuItem:
        return MenuItem(id=row.id, tenant_id=row.tenant_id, name=row.name, category=row.category, price=Decimal(str(row.price)), available=row.available, recipe=row.recipe)


class OperationalEventRepository(Repository):
    def add(self, event: OperationalEvent) -> OperationalEvent:
        with self._session() as session:
            row = OperationalEventRow(event_id=event.event_id, event_type=event.event_type, rule_id=event.rule_id, rule_version=event.rule_version, severity=event.severity, occurred_at=event.occurred_at, detected_at=event.detected_at, entity=event.entity.model_dump(), metrics=event.metrics, dedup_fingerprint=event.dedup_fingerprint, correlation_id=event.correlation_id, causation_id=event.causation_id, tenant_id=event.tenant_id, status=event.status, attempts=event.attempts)
            session.add(row)
            session.commit()
        return event

    def queued(self, limit: int = 100) -> list[OperationalEvent]:
        with self._session() as session:
            rows = session.scalars(select(OperationalEventRow).where(OperationalEventRow.status == OperationalEventStatus.QUEUED).order_by(desc(OperationalEventRow.severity), OperationalEventRow.detected_at).limit(limit)).all()
            return [self._event(row) for row in rows]

    def set_status(self, event_id: str, status: OperationalEventStatus, *, increment_attempts: bool = False) -> None:
        with self._session() as session:
            row = session.get(OperationalEventRow, event_id)
            if row is None:
                raise KeyError(event_id)
            row.status = status
            if increment_attempts:
                row.attempts += 1
            session.commit()

    @staticmethod
    def _event(row: OperationalEventRow) -> OperationalEvent:
        return OperationalEvent.model_validate({"event_id": row.event_id, "event_type": row.event_type, "rule_id": row.rule_id, "rule_version": row.rule_version, "severity": row.severity, "occurred_at": row.occurred_at, "detected_at": row.detected_at, "entity": row.entity, "metrics": row.metrics, "dedup_fingerprint": row.dedup_fingerprint, "correlation_id": row.correlation_id, "causation_id": row.causation_id, "tenant_id": row.tenant_id, "status": row.status, "attempts": row.attempts})


class RuleStateRepository(Repository):
    def get(self, rule_id: str, entity_id: str, tenant_id: str = "default") -> RuleStateRow | None:
        with self._session() as session:
            return session.scalar(select(RuleStateRow).where(RuleStateRow.tenant_id == tenant_id, RuleStateRow.rule_id == rule_id, RuleStateRow.entity_id == entity_id))

    def save(self, *, rule_id: str, entity_id: str, tenant_id: str, cooldown_until: datetime | None, active_fingerprint: str | None, fires_in_window: int, window_started_at: datetime | None, cleared: bool) -> None:
        with self._session() as session:
            row = session.scalar(select(RuleStateRow).where(RuleStateRow.tenant_id == tenant_id, RuleStateRow.rule_id == rule_id, RuleStateRow.entity_id == entity_id))
            values = dict(cooldown_until=cooldown_until, active_fingerprint=active_fingerprint, fires_in_window=fires_in_window, window_started_at=window_started_at, cleared=cleared)
            if row is None:
                session.add(RuleStateRow(rule_id=rule_id, entity_id=entity_id, tenant_id=tenant_id, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.commit()


class AnalyticsRepository(Repository):
    def record_metric(self, *, tenant_id: str, metric_id: str, entity_id: str, bucket_start: datetime, value: float, n: int = 1) -> None:
        with self._session() as session:
            row = session.scalar(select(MetricWindowRow).where(MetricWindowRow.tenant_id == tenant_id, MetricWindowRow.metric_id == metric_id, MetricWindowRow.entity_id == entity_id, MetricWindowRow.bucket_start == bucket_start))
            if row is None:
                session.add(MetricWindowRow(tenant_id=tenant_id, metric_id=metric_id, entity_id=entity_id, bucket_start=bucket_start, value=value, n=n))
            else:
                row.value, row.n = value, n
            session.commit()
    def save_snapshot(self, snapshot: KPISnapshot) -> KPISnapshot:
        payload = snapshot.model_dump(mode="json")
        with self._session() as session:
            session.merge(KPISnapshotRow(snapshot_id=snapshot.snapshot_id, tenant_id=snapshot.tenant_id, period_start=snapshot.period_start, period_end=snapshot.period_end, payload=payload, computed_at=snapshot.computed_at))
            session.commit()
        return snapshot

    def latest_snapshot(self, tenant_id: str = "default") -> KPISnapshot | None:
        with self._session() as session:
            row = session.scalar(select(KPISnapshotRow).where(KPISnapshotRow.tenant_id == tenant_id).order_by(desc(KPISnapshotRow.computed_at)))
            return KPISnapshot.model_validate(row.payload) if row else None

    def upsert_baseline(self, *, tenant_id: str, metric_id: str, entity_id: str, hour_of_week: int, mean: float, trimmed_mean: float, sample_count: int) -> None:
        with self._session() as session:
            row = session.scalar(select(BaselineRow).where(BaselineRow.tenant_id == tenant_id, BaselineRow.metric_id == metric_id, BaselineRow.entity_id == entity_id, BaselineRow.hour_of_week == hour_of_week))
            if row is None:
                session.add(BaselineRow(tenant_id=tenant_id, metric_id=metric_id, entity_id=entity_id, hour_of_week=hour_of_week, mean=mean, trimmed_mean=trimmed_mean, sample_count=sample_count))
            else:
                row.mean, row.trimmed_mean, row.sample_count, row.computed_at = mean, trimmed_mean, sample_count, utc_now()
            session.commit()

    def baseline(self, metric_id: str, entity_id: str, hour_of_week: int, tenant_id: str = "default") -> tuple[float, int] | None:
        with self._session() as session:
            row = session.scalar(select(BaselineRow).where(BaselineRow.tenant_id == tenant_id, BaselineRow.metric_id == metric_id, BaselineRow.entity_id == entity_id, BaselineRow.hour_of_week == hour_of_week))
            return (row.trimmed_mean, row.sample_count) if row else None


class IncidentRepository(Repository):
    def save(self, report: IncidentReport, tenant_id: str = "default") -> IncidentReport:
        with self._session() as session:
            session.merge(IncidentRow(incident_id=report.incident_id, tenant_id=tenant_id, payload=report.model_dump(mode="json"), state=report.state, fingerprint=report.dedup_fingerprint, correlation_id=report.correlation_id, created_at=report.created_at))
            session.commit()
        return report

    def active(self, tenant_id: str = "default") -> list[IncidentReport]:
        with self._session() as session:
            rows = session.scalars(select(IncidentRow).where(IncidentRow.tenant_id == tenant_id, IncidentRow.state != "RESOLVED").order_by(desc(IncidentRow.created_at))).all()
            return [IncidentReport.model_validate(row.payload) for row in rows]


class ReportRepository(Repository):
    def save(self, report: BusinessReport, tenant_id: str = "default") -> BusinessReport:
        with self._session() as session:
            session.merge(BusinessReportRow(report_id=report.report_id, tenant_id=tenant_id, kpi_snapshot_id=report.kpi_snapshot_id, payload=report.model_dump(mode="json"), correlation_id=report.correlation_id, created_at=report.created_at, expires_at=report.expires_at))
            session.commit()
        return report


class PlanRepository(Repository):
    def save(self, plan: ActionPlan, tenant_id: str = "default") -> ActionPlan:
        with self._session() as session:
            session.merge(ActionPlanRow(plan_id=plan.plan_id, tenant_id=tenant_id, payload=plan.model_dump(mode="json"), state=plan.state, correlation_id=plan.correlation_id, requires_approval=plan.requires_approval, revision_of=plan.revision_of, revision_count=plan.revision_count, created_at=plan.created_at, expires_at=plan.expires_at))
            session.commit()
        return plan

    def get(self, plan_id: str) -> ActionPlan | None:
        with self._session() as session:
            row = session.get(ActionPlanRow, plan_id)
            return ActionPlan.model_validate(row.payload) if row else None

    def set_state(self, plan: ActionPlan) -> None:
        self.save(plan)


class ApprovalRepository(Repository):
    def save(self, approval) -> object:
        with self._session() as session:
            session.merge(ApprovalRequestRow(approval_id=approval.approval_id, plan_id=approval.plan_id, state=approval.state, expires_at=approval.expires_at, decided_by=approval.decided_by, decided_at=approval.decided_at, decision=approval.decision, note=approval.note))
            session.commit()
        return approval

    def get_by_plan(self, plan_id: str):
        from touchorders_core.domain.approvals import ApprovalRequest
        with self._session() as session:
            row = session.scalar(select(ApprovalRequestRow).where(ApprovalRequestRow.plan_id == plan_id))
            if row is None:
                return None
            return ApprovalRequest(approval_id=row.approval_id, plan_id=row.plan_id, state=row.state, expires_at=row.expires_at, decided_by=row.decided_by, decided_at=row.decided_at, decision=row.decision, note=row.note)


class WorkflowRepository(Repository):
    def create(self, *, workflow_id: str, plan_id: str | None, template_name: str | None, correlation_id: str, state: str) -> None:
        with self._session() as session:
            session.add(WorkflowExecutionRow(workflow_id=workflow_id, plan_id=plan_id, template_name=template_name, state=state, correlation_id=correlation_id))
            session.commit()

    def update(self, workflow_id: str, *, state: str, current_step: int | None = None, failure: dict[str, Any] | None = None) -> None:
        with self._session() as session:
            row = session.get(WorkflowExecutionRow, workflow_id)
            if not row:
                raise KeyError(workflow_id)
            row.state, row.failure = state, failure
            if current_step is not None:
                row.current_step = current_step
            session.commit()

    def active(self) -> list[dict[str, Any]]:
        with self._session() as session:
            rows = session.scalars(select(WorkflowExecutionRow).where(WorkflowExecutionRow.state.in_(["PENDING", "EXECUTING", "COMPENSATING"]))).all()
            return [{"workflow_id": row.workflow_id, "plan_id": row.plan_id, "state": row.state, "current_step": row.current_step} for row in rows]

    def step(self, *, workflow_id: str, step_no: int, state: str, idempotency_key: str, output: dict[str, Any] | None = None, compensated: bool = False) -> None:
        with self._session() as session:
            row = session.scalar(select(WorkflowStepExecutionRow).where(WorkflowStepExecutionRow.idempotency_key == idempotency_key))
            if row is None:
                session.add(WorkflowStepExecutionRow(workflow_id=workflow_id, step_no=step_no, state=state, idempotency_key=idempotency_key, output=output, compensated=compensated))
            else:
                row.state, row.output, row.compensated, row.attempts = state, output, compensated, row.attempts + 1
            session.commit()


class ToolInvocationRepository(Repository):
    def seen(self, args_hash: str) -> bool:
        with self._session() as session:
            return session.scalar(select(ToolInvocationRow).where(ToolInvocationRow.args_hash == args_hash, ToolInvocationRow.status == "COMPLETED")) is not None

    def add(self, *, invocation_id: str, tool_name: str, tool_version: int, caller: str, args_hash: str, status: str, duration_ms: int, output: dict[str, Any] | None, correlation_id: str | None) -> None:
        with self._session() as session:
            session.add(ToolInvocationRow(invocation_id=invocation_id, tool_name=tool_name, tool_version=tool_version, caller=caller, args_hash=args_hash, status=status, duration_ms=duration_ms, output=output, correlation_id=correlation_id))
            session.commit()


class MessageRepository(Repository):
    def publish(self, message: AgentMessage) -> bool:
        with self._session() as session:
            if session.scalar(select(AgentMessageRow).where(AgentMessageRow.dedup_key == message.dedup_key)):
                return False
            session.add(AgentMessageRow(message_id=message.message_id, type=message.type, payload=message.payload, correlation_id=message.correlation_id, created_at=message.created_at, dedup_key=message.dedup_key))
            session.commit()
            return True

    def pending(self, limit: int = 100) -> list[AgentMessage]:
        with self._session() as session:
            rows = session.scalars(select(AgentMessageRow).where(AgentMessageRow.consumed_at.is_(None)).order_by(AgentMessageRow.created_at).limit(limit)).all()
            return [AgentMessage(message_id=row.message_id, type=row.type, payload=row.payload, correlation_id=row.correlation_id, created_at=row.created_at, dedup_key=row.dedup_key) for row in rows]

    def consume(self, message_ids: Iterable[str]) -> None:
        with self._session() as session:
            for message_id in message_ids:
                row = session.get(AgentMessageRow, message_id)
                if row:
                    row.consumed_at = utc_now()
            session.commit()


class MemoryRepository(Repository):
    def upsert(self, *, agent: AgentName, kind: str, key: str, payload: dict[str, Any], summary: str, expires_at: datetime | None, correlation_id: str | None) -> None:
        with self._session() as session:
            row = session.scalar(select(MemoryRow).where(MemoryRow.agent == agent, MemoryRow.key == key))
            if row is None:
                session.add(MemoryRow(memory_id=str(uuid7()), agent=agent, kind=kind, key=key, payload=payload, summary=summary, expires_at=expires_at, correlation_id=correlation_id))
            else:
                row.kind, row.payload, row.summary, row.expires_at, row.correlation_id, row.version = kind, payload, summary, expires_at, correlation_id, row.version + 1
            session.commit()

    def recall(self, *, agent: AgentName, kinds: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
        with self._session() as session:
            statement: Select[tuple[MemoryRow]] = select(MemoryRow).where(MemoryRow.agent == agent, (MemoryRow.expires_at.is_(None)) | (MemoryRow.expires_at > utc_now()))
            if kinds:
                statement = statement.where(MemoryRow.kind.in_(kinds))
            rows = session.scalars(statement.order_by(desc(MemoryRow.updated_at)).limit(limit)).all()
            return [{"kind": row.kind, "key": row.key, "payload": row.payload, "summary": row.summary, "correlation_id": row.correlation_id} for row in rows]


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
