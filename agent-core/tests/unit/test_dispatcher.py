"""§7.7 dispatcher: cheapest-adequate routing and correct template categorization."""

from __future__ import annotations

import asyncio

from touchorders_core.domain.common import utc_now
from touchorders_core.domain.enums import IncidentCategory, Severity
from touchorders_core.domain.events import EventEntity, OperationalEvent
from touchorders_core.rules_engine.dispatcher import Dispatcher
from touchorders_core.rules_engine.queue import EventQueue


def _event(severity: Severity) -> OperationalEvent:
    return OperationalEvent(
        event_type="operational.inventory_risk.low_stock", rule_id="inventory.low_stock", rule_version=1,
        severity=severity, occurred_at=utc_now(), entity=EventEntity(type="inventory_item", id="chicken", name="Chicken"),
        metrics={"remaining_units": 15.0, "threshold": 20.0}, dedup_fingerprint="fp", correlation_id="corr-d",
    )


def test_warning_event_takes_the_zero_token_template_path_with_real_category(repos) -> None:
    queue = EventQueue(repos.events)
    captured = []

    async def consumer(report):
        captured.append(report)

    dispatcher = Dispatcher(queue, template_consumer=consumer)

    async def drive():
        await queue.publish(_event(Severity.WARNING))
        return await dispatcher.dispatch_once()

    asyncio.run(drive())

    assert captured[0].produced_by == "system_template"
    # regression: was always COMPOSITE because the lowercase event_type segment never matched.
    assert captured[0].category == IncidentCategory.INVENTORY_RISK


def test_high_event_is_routed_to_the_realtime_analyst(repos) -> None:
    queue = EventQueue(repos.events)
    seen = []

    async def trigger(events):
        seen.append(events)
        return _template_stub(events[0])

    dispatcher = Dispatcher(queue, realtime_trigger=trigger)

    async def drive():
        await queue.publish(_event(Severity.HIGH))
        await dispatcher.dispatch_once()

    asyncio.run(drive())
    assert len(seen) == 1 and seen[0][0].severity == Severity.HIGH


def _template_stub(event):
    from touchorders_core.domain.incidents import Evidence, IncidentReport
    return IncidentReport(
        produced_by="realtime_analyst", category=IncidentCategory.INVENTORY_RISK, severity=event.severity,
        title="t", summary="s", evidence=[Evidence(metric="remaining_units", value=15.0, source_event_id=event.event_id)],
        suspected_causes=[], requires_manager_attention=True, source_event_ids=[event.event_id],
        dedup_fingerprint=event.dedup_fingerprint, correlation_id=event.correlation_id,
    )
