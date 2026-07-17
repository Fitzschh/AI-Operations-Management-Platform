"""Rolling metric computer. All values are deterministic and persisted as metric windows."""

from __future__ import annotations

from datetime import timedelta

from touchorders_core.datastore.repositories import AnalyticsRepository, DomainRepository
from touchorders_core.domain.events import DomainEvent, EventEntity
from touchorders_core.rules_engine.models import MetricObservation


class MetricComputer:
    def __init__(self, domain: DomainRepository, analytics: AnalyticsRepository) -> None:
        self._domain = domain
        self._analytics = analytics

    def observations(self, event: DomainEvent) -> list[MetricObservation]:
        now = event.occurred_at
        values: list[MetricObservation] = []
        if event.event_type == "inventory.updated":
            item = self._domain.get_inventory(event.entity_id, event.tenant_id)
            if item:
                rate = 0.0  # Inventory movements introduce a non-zero deterministic rate in Stage 2 adapter extensions.
                projection = item.quantity / rate * 60 if rate > 0 else 0.0
                metrics = {"remaining_units": item.quantity, "threshold": item.reorder_threshold, "avg_hourly_consumption": rate, "projected_stockout_minutes": projection}
                values.append(MetricObservation(metric_id="inventory.remaining_units", entity=EventEntity(type="inventory_item", id=item.sku, name=item.name), value=item.quantity, metrics=metrics, tenant_id=event.tenant_id))
        elif event.event_type == "sales.recorded":
            revenue = sum(float(sale.amount) for sale in self._domain.sales_between(now - timedelta(minutes=60), now, event.tenant_id))
            values.append(MetricObservation(metric_id="sales.revenue_60m", entity=EventEntity(type="restaurant", id="default", name="Restaurant"), value=revenue, metrics={"revenue_60m": revenue}, tenant_id=event.tenant_id))
        elif event.event_type.startswith("orders."):
            orders_15 = self._domain.orders_between(now - timedelta(minutes=15), now, event.tenant_id)
            orders_30 = self._domain.orders_between(now - timedelta(minutes=30), now, event.tenant_id)
            cancellations = sum(order.status == "CANCELLED" for order in orders_30)
            values.append(MetricObservation(metric_id="orders.count_15m", entity=EventEntity(type="restaurant", id="default", name="Restaurant"), value=float(len(orders_15)), metrics={"count_15m": float(len(orders_15)), "count_30m": float(len(orders_30))}, tenant_id=event.tenant_id))
            values.append(MetricObservation(metric_id="orders.cancellation_rate_30m", entity=EventEntity(type="restaurant", id="default", name="Restaurant"), value=(cancellations / len(orders_30)) if orders_30 else 0.0, metrics={"rate_30m": (cancellations / len(orders_30)) if orders_30 else 0.0, "count_30m": float(len(orders_30))}, tenant_id=event.tenant_id))
        elif event.event_type == "kitchen.ticket_closed":
            tickets = self._domain.closed_tickets_between(now - timedelta(minutes=15), now, event.tenant_id)
            delays = [(ticket.closed_at - ticket.opened_at).total_seconds() / 60 for ticket in tickets if ticket.closed_at]
            value = sum(delays) / len(delays) if delays else 0.0
            values.append(MetricObservation(metric_id="kitchen.avg_ticket_delay_15m", entity=EventEntity(type="restaurant", id="default", name="Restaurant"), value=value, metrics={"avg_ticket_delay_15m": value, "ticket_count": float(len(delays))}, tenant_id=event.tenant_id))
        for observation in values:
            self._analytics.record_metric(tenant_id=observation.tenant_id, metric_id=observation.metric_id, entity_id=observation.entity.id, bucket_start=now.replace(second=0, microsecond=0), value=observation.value)
        return values
