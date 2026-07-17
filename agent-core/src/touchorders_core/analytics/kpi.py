"""KPI snapshot builder: the sole numeric source for business-agent context."""

from __future__ import annotations

from datetime import timedelta
from statistics import mean

from touchorders_core.analytics.forecasts import weekday_seasonal_forecast
from touchorders_core.datastore.repositories import AnalyticsRepository, DomainRepository
from touchorders_core.domain.common import utc_now
from touchorders_core.domain.reports import KPISnapshot


class KPISnapshotBuilder:
    def __init__(self, domain: DomainRepository, analytics: AnalyticsRepository) -> None:
        self._domain = domain
        self._analytics = analytics

    def build(self, tenant_id: str = "default", *, now=None) -> KPISnapshot:
        end = now or utc_now()
        revenue_60 = sum(float(sale.amount) for sale in self._domain.sales_between(end - timedelta(hours=1), end, tenant_id))
        revenue_day = sum(float(sale.amount) for sale in self._domain.sales_between(end - timedelta(days=1), end, tenant_id))
        revenue_week = sum(float(sale.amount) for sale in self._domain.sales_between(end - timedelta(days=7), end, tenant_id))
        orders_15 = self._domain.orders_between(end - timedelta(minutes=15), end, tenant_id)
        orders_30 = self._domain.orders_between(end - timedelta(minutes=30), end, tenant_id)
        tickets = self._domain.closed_tickets_between(end - timedelta(minutes=15), end, tenant_id)
        delays = [(ticket.closed_at - ticket.opened_at).total_seconds() / 60 for ticket in tickets if ticket.closed_at]
        inventory = self._domain.list_inventory(tenant_id=tenant_id)
        last_hours = []
        for offset in range(24, 0, -1):
            hourly_end = end - timedelta(hours=offset - 1)
            hourly_start = hourly_end - timedelta(hours=1)
            last_hours.append(sum(float(sale.amount) for sale in self._domain.sales_between(hourly_start, hourly_end, tenant_id)))
        metrics = {
            "revenue_60m": revenue_60,
            "revenue_day": revenue_day,
            "revenue_week": revenue_week,
            "orders_count_15m": float(len(orders_15)),
            "orders_count_30m": float(len(orders_30)),
            "orders_cancellation_rate_30m": (sum(order.status == "CANCELLED" for order in orders_30) / len(orders_30)) if orders_30 else 0.0,
            "kitchen_avg_ticket_delay_15m": mean(delays) if delays else 0.0,
            "kitchen_ticket_count_15m": float(len(delays)),
            "inventory_low_item_count": float(sum(item.quantity < item.reorder_threshold for item in inventory)),
        }
        snapshot = KPISnapshot(tenant_id=tenant_id, period_start=end - timedelta(hours=1), period_end=end, metrics=metrics, forecasts={"forecast_revenue_next_hour": weekday_seasonal_forecast(last_hours), "forecast_orders_next_hour": weekday_seasonal_forecast([float(len(orders_15))])})
        return self._analytics.save_snapshot(snapshot)
