"""Realtime Analyst context builder (§3.5, A-2). Carries certified events + their metrics only."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from touchorders_core.domain.events import OperationalEvent
from touchorders_core.domain.incidents import IncidentReport


def build_context(events: Sequence[OperationalEvent], active_incidents: Sequence[IncidentReport] = ()) -> dict[str, Any]:
    return {
        "events": [
            {
                "source_event_id": event.event_id,
                "rule_id": event.rule_id,
                "severity": event.severity.value,
                "entity": event.entity.model_dump(),
                "metrics": event.metrics,  # the only numeric vocabulary the analyst may echo (A-4)
            }
            for event in events
        ],
        "active_incidents": [
            {"incident_id": incident.incident_id, "category": incident.category.value, "severity": incident.severity.value, "fingerprint": incident.dedup_fingerprint}
            for incident in active_incidents
        ],
    }
