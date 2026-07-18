"""Deterministic event dispatcher; policy selects template versus agent analysis."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from touchorders_core.domain.enums import IncidentCategory, Severity
from touchorders_core.domain.events import OperationalEvent
from touchorders_core.domain.incidents import Evidence, IncidentReport
from touchorders_core.rules_engine.queue import EventQueue


RealtimeTrigger = Callable[[list[OperationalEvent]], Awaitable[IncidentReport]]
TemplateConsumer = Callable[[IncidentReport], Awaitable[None]]


class Dispatcher:
    def __init__(self, queue: EventQueue, *, realtime_trigger: RealtimeTrigger | None = None, template_consumer: TemplateConsumer | None = None) -> None:
        self._queue = queue
        self._realtime_trigger = realtime_trigger
        self._template_consumer = template_consumer

    async def dispatch_once(self) -> IncidentReport | None:
        event = await self._queue.claim()
        if event is None:
            return None
        try:
            if event.severity.rank <= Severity.WARNING.rank:
                report = self._template(event)
                if self._template_consumer:
                    await self._template_consumer(report)
            else:
                if self._realtime_trigger is None:
                    raise RuntimeError("Realtime analyst trigger is not wired.")
                report = await self._realtime_trigger([event])
            self._queue.complete(event)
            return report
        except Exception:
            if event.attempts >= 3:
                self._queue.dead_letter(event)
            raise

    @staticmethod
    def _template(event: OperationalEvent) -> IncidentReport:
        # event_type is "operational.<category_lower>.<rule>"; category enum values are uppercase.
        segment = event.event_type.split(".")[1].upper()
        category = IncidentCategory(segment) if segment in IncidentCategory._value2member_map_ else IncidentCategory.COMPOSITE
        first_metric, first_value = next(iter(event.metrics.items()), ("observed_value", 0.0))
        severity = Severity.WARNING if event.severity == Severity.INFO else event.severity
        return IncidentReport(produced_by="system_template", category=category, severity=severity, title=f"{event.rule_id} detected", summary="A deterministic operating threshold was crossed. Review the attached metric evidence.", evidence=[Evidence(metric=first_metric, value=first_value, source_event_id=event.event_id)], correlated_signals=[event.event_type], suspected_causes=[], recommended_focus=["Review the affected operational metric."], requires_manager_attention=severity.rank >= Severity.HIGH.rank, source_event_ids=[event.event_id], dedup_fingerprint=event.dedup_fingerprint, correlation_id=event.correlation_id)
