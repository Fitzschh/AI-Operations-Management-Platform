"""Realtime Analyst post-validation (§3.5): the analyst may confirm or raise severity, never lower."""

from __future__ import annotations

from collections.abc import Sequence

from touchorders_core.domain.enums import Severity
from touchorders_core.domain.events import OperationalEvent
from touchorders_core.domain.incidents import IncidentReportOutput


class SeverityMonotonicityError(ValueError):
    pass


def enforce_severity_monotonicity(output: IncidentReportOutput, source_events: Sequence[OperationalEvent]) -> None:
    if not source_events:
        return
    max_source = max(event.severity for event in source_events)
    if output.severity.rank < max_source.rank:
        raise SeverityMonotonicityError(
            f"Analyst lowered severity to {output.severity} below source {max_source} (§3.5)."
        )
