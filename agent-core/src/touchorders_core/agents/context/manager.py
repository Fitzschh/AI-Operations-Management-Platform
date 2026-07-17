"""Operations Manager context builder (§3.3, A-2).

Assembles the coalesced triage set: pending incidents (full), a current restaurant status
snapshot, active plans, recent approval outcomes with human notes, and recalled rejection lessons.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from touchorders_core.domain.incidents import IncidentReport


def build_context(
    incidents: Sequence[IncidentReport],
    *,
    restaurant_status: dict[str, Any] | None = None,
    active_plans: Sequence[dict[str, Any]] = (),
    recent_outcomes: Sequence[dict[str, Any]] = (),
    lessons: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "incidents": [
            {
                "incident_id": incident.incident_id,
                "category": incident.category.value,
                "severity": incident.severity.value,
                "title": incident.title,
                "summary": incident.summary,
                "evidence": [ev.model_dump() for ev in incident.evidence],
            }
            for incident in incidents
        ],
        "restaurant_status": restaurant_status or {},
        "active_plans": list(active_plans),
        "recent_approval_outcomes": list(recent_outcomes),
        "lessons": list(lessons),
    }
