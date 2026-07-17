"""Scripted, deterministic demo data source for the hackathon scenarios."""

from __future__ import annotations

from datetime import timedelta

from touchorders_core.domain.common import utc_now
from touchorders_core.domain.events import DomainEvent
from touchorders_core.ingestion.normalizer import Normalizer


class Simulator:
    def __init__(self, normalizer: Normalizer) -> None:
        self._normalizer = normalizer

    def run(self, scenario: str, tenant_id: str = "default") -> list[DomainEvent]:
        if scenario == "friday_rush":
            return self._friday_rush(tenant_id)
        if scenario == "quiet_tuesday":
            return self._quiet_tuesday(tenant_id)
        raise ValueError(f"Unknown simulator scenario: {scenario}")

    def _friday_rush(self, tenant_id: str) -> list[DomainEvent]:
        now = utc_now()
        events = self._normalizer.inventory({"source_id": "sim:friday:inventory:chicken", "sku": "chicken-breast", "name": "Chicken Breast", "quantity": 7, "category": "protein", "occurred_at": now.isoformat()}, tenant_id)
        for index in range(10):
            events.extend(self._normalizer.order({"source_id": f"sim:friday:order:{index}", "external_id": f"friday-{index}", "total": "25.00", "occurred_at": (now - timedelta(minutes=index)).isoformat()}, tenant_id))
        events.extend(self._normalizer.ticket({"source_id": "sim:friday:ticket:1", "ticket_id": "friday-ticket-1", "opened_at": (now - timedelta(minutes=35)).isoformat(), "closed_at": now.isoformat()}, tenant_id))
        return events

    def _quiet_tuesday(self, tenant_id: str) -> list[DomainEvent]:
        now = utc_now()
        return self._normalizer.inventory({"source_id": "sim:quiet:inventory:rice", "sku": "rice", "name": "Rice", "quantity": 80, "category": "dry", "occurred_at": now.isoformat()}, tenant_id)
