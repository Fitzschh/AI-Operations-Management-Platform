"""Business Analyst context builder (§3.4, A-2). KPI snapshot keys + prior-report continuity."""

from __future__ import annotations

from typing import Any

from touchorders_core.domain.reports import KPISnapshot


def build_context(snapshot: KPISnapshot, prior_report_summary: str | None = None) -> dict[str, Any]:
    return {
        "snapshot": {
            "period_start": snapshot.period_start.isoformat(),
            "period_end": snapshot.period_end.isoformat(),
            "metrics": snapshot.metrics,
            "forecasts": snapshot.forecasts,
        },
        "prior_report_summary": prior_report_summary,
    }
