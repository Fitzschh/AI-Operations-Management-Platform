"""Deterministically normalize source payloads into local domain records and events."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from touchorders_core.datastore.repositories import DomainRepository
from touchorders_core.domain.common import DomainModel, utc_now
from touchorders_core.domain.entities import InventoryItem, KitchenTicket, Order, Sale
from touchorders_core.domain.events import DomainEvent


class InventoryPayload(DomainModel):
    source_id: str
    sku: str
    name: str
    quantity: float
    category: str = "uncategorized"
    unit: str = "unit"
    reorder_threshold: float = 20
    supplier_id: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)


class OrderPayload(DomainModel):
    source_id: str
    external_id: str
    total: Decimal
    status: str = "PLACED"
    channel: str = "counter"
    occurred_at: datetime = Field(default_factory=utc_now)
    payment_type: str = "unknown"


class TicketPayload(DomainModel):
    source_id: str
    ticket_id: str
    order_external_id: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    station: str = "kitchen"


class Normalizer:
    """The only component that accepts heterogeneous source payloads."""

    def __init__(self, domain: DomainRepository, source_name: str = "webhook") -> None:
        self._domain = domain
        self._source_name = source_name

    def inventory(self, raw: dict[str, Any], tenant_id: str = "default") -> list[DomainEvent]:
        payload = InventoryPayload.model_validate(raw)
        if not self._domain.claim_ingestion_receipt(self._source_name, payload.source_id):
            return []
        item = self._domain.upsert_inventory(InventoryItem(tenant_id=tenant_id, sku=payload.sku, name=payload.name, category=payload.category, unit=payload.unit, quantity=payload.quantity, reorder_threshold=payload.reorder_threshold, supplier_id=payload.supplier_id, updated_at=payload.occurred_at))
        return [DomainEvent(event_type="inventory.updated", occurred_at=payload.occurred_at, tenant_id=tenant_id, entity_type="inventory_item", entity_id=item.sku, source_id=payload.source_id, payload={"sku": item.sku, "quantity": item.quantity})]

    def order(self, raw: dict[str, Any], tenant_id: str = "default") -> list[DomainEvent]:
        payload = OrderPayload.model_validate(raw)
        if not self._domain.claim_ingestion_receipt(self._source_name, payload.source_id):
            return []
        order, created = self._domain.upsert_order(Order(tenant_id=tenant_id, external_id=payload.external_id, total=payload.total, status=payload.status, channel=payload.channel, placed_at=payload.occurred_at))
        if not created:
            return []
        events = [DomainEvent(event_type="orders.placed" if payload.status != "CANCELLED" else "orders.cancelled", occurred_at=payload.occurred_at, tenant_id=tenant_id, entity_type="order", entity_id=order.external_id, source_id=payload.source_id, payload={"status": order.status, "total": float(order.total)})]
        if order.status != "CANCELLED":
            sale, _ = self._domain.record_sale(Sale(tenant_id=tenant_id, order_external_id=order.external_id, occurred_at=order.placed_at, amount=order.total, payment_type=payload.payment_type))
            events.append(DomainEvent(event_type="sales.recorded", occurred_at=sale.occurred_at, tenant_id=tenant_id, entity_type="sale", entity_id=sale.id, source_id=f"{payload.source_id}:sale", payload={"amount": float(sale.amount)}))
        return events

    def ticket(self, raw: dict[str, Any], tenant_id: str = "default") -> list[DomainEvent]:
        payload = TicketPayload.model_validate(raw)
        if not self._domain.claim_ingestion_receipt(self._source_name, payload.source_id):
            return []
        ticket, _ = self._domain.upsert_ticket(KitchenTicket(id=payload.ticket_id, tenant_id=tenant_id, order_external_id=payload.order_external_id, opened_at=payload.opened_at, closed_at=payload.closed_at, station=payload.station))
        event_type = "kitchen.ticket_closed" if ticket.closed_at else "kitchen.ticket_opened"
        return [DomainEvent(event_type=event_type, occurred_at=ticket.closed_at or ticket.opened_at, tenant_id=tenant_id, entity_type="kitchen_ticket", entity_id=ticket.id, source_id=payload.source_id, payload={"station": ticket.station})]
