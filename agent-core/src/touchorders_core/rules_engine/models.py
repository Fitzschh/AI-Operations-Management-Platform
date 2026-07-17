"""Validated declarative rules and deterministic metric observations."""

from __future__ import annotations

from pydantic import Field

from touchorders_core.domain.common import DomainModel
from touchorders_core.domain.enums import IncidentCategory, Severity
from touchorders_core.domain.events import EventEntity


class SeverityBand(DomainModel):
    when: str
    severity: Severity


class Hysteresis(DomainModel):
    clear_when: str


class Escalation(DomainModel):
    fires_within_cooldown: int = 3
    action: str = "bump_severity"


class Suppression(DomainModel):
    cooldown_minutes: int = Field(default=30, ge=0)
    hysteresis: Hysteresis | None = None
    escalation: Escalation = Field(default_factory=Escalation)


class Rule(DomainModel):
    rule_id: str
    enabled: bool = True
    category: IncidentCategory
    evaluator: str
    scope: str = "per_entity"
    metric: str
    operator: str | None = None
    value: float | None = None
    severity_bands: list[SeverityBand]
    suppression: Suppression = Field(default_factory=Suppression)
    analyst_policy: str = "LLM_IF_SEVERITY_AT_LEAST_HIGH"
    extra_metrics: list[str] = Field(default_factory=list)
    version: int = 1


class RulePack(DomainModel):
    pack: str
    version: int
    rules: list[Rule]


class MetricObservation(DomainModel):
    metric_id: str
    entity: EventEntity
    value: float
    metrics: dict[str, float]
    tenant_id: str = "default"
