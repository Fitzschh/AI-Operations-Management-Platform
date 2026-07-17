"""Pure restaurant entities used by ingestion, analytics, and deterministic tools."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from touchorders_core.domain.common import DomainModel, uuid7, utc_now


class InventoryItem(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid7()))
    tenant_id: str = "default"
    sku: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="uncategorized", max_length=80)
    unit: str = Field(default="unit", max_length=24)
    quantity: float
    reorder_threshold: float = 20
    supplier_id: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class Order(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid7()))
    tenant_id: str = "default"
    external_id: str = Field(min_length=1, max_length=120)
    placed_at: datetime = Field(default_factory=utc_now)
    status: str = "PLACED"
    total: Decimal = Decimal("0")
    channel: str = "counter"


class Sale(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid7()))
    tenant_id: str = "default"
    order_external_id: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)
    amount: Decimal
    payment_type: str = "unknown"


class KitchenTicket(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid7()))
    tenant_id: str = "default"
    order_external_id: str | None = None
    opened_at: datetime = Field(default_factory=utc_now)
    closed_at: datetime | None = None
    station: str = "kitchen"


class MenuItem(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid7()))
    tenant_id: str = "default"
    name: str = Field(min_length=1, max_length=120)
    category: str = "uncategorized"
    price: Decimal = Decimal("0")
    available: bool = True
    recipe: dict[str, float] = Field(default_factory=dict)
