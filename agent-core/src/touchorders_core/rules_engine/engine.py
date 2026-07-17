"""The deterministic rule-engine pipeline: metrics, rules, suppression, outbox."""

from __future__ import annotations

from touchorders_core.domain.common import utc_now
from touchorders_core.domain.events import DomainEvent, OperationalEvent
from touchorders_core.rules_engine.evaluators import evaluate, severity_for
from touchorders_core.rules_engine.loader import RuleLoader
from touchorders_core.rules_engine.metrics import MetricComputer
from touchorders_core.rules_engine.queue import EventQueue
from touchorders_core.rules_engine.suppression import Suppressor


class RulesEngine:
    def __init__(self, metrics: MetricComputer, loader: RuleLoader, suppressor: Suppressor, queue: EventQueue) -> None:
        self._metrics = metrics
        self._loader = loader
        self._suppressor = suppressor
        self._queue = queue

    async def process(self, event: DomainEvent) -> list[OperationalEvent]:
        rules = self._loader.rules or self._loader.load()
        certified: list[OperationalEvent] = []
        for observation in self._metrics.observations(event):
            for rule in rules.values():
                if not rule.enabled or rule.metric != observation.metric_id:
                    continue
                if not evaluate(rule, observation.value):
                    continue
                severity = severity_for(rule, observation.value)
                if severity is None:
                    continue
                decision = self._suppressor.decide(rule=rule, entity_id=observation.entity.id, value=observation.value, severity=severity, tenant_id=event.tenant_id)
                if not decision.emit or decision.severity is None or decision.fingerprint is None:
                    continue
                metrics = {**observation.metrics, rule.metric.replace(".", "_"): observation.value}
                operational = OperationalEvent(event_type=f"operational.{rule.category.value.lower()}.{rule.rule_id.rsplit('.', 1)[-1]}", rule_id=rule.rule_id, rule_version=rule.version, severity=decision.severity, occurred_at=event.occurred_at, detected_at=utc_now(), entity=observation.entity, metrics=metrics, dedup_fingerprint=decision.fingerprint, correlation_id=event.correlation_id, causation_id=event.event_id, tenant_id=event.tenant_id)
                await self._queue.publish(operational)
                certified.append(operational)
        return certified
