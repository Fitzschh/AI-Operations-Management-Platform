"""Typed domain and operational event contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field, field_validator

from touchorders_core.domain.common import DomainModel, uuid7, utc_now
from touchorders_core.domain.enums import OperationalEventStatus, Severity


class DomainEvent(DomainModel):
    event_id: str = Field(default_factory=lambda: str(uuid7()))
    event_type: str = Field(pattern=r"^[a-z_]+\.[a-z_]+$")
    occurred_at: datetime = Field(default_factory=utc_now)
    tenant_id: str = "default"
    entity_type: str
    entity_id: str
    source_id: str
    payload: dict[str, object] = Field(default_factory=dict)
    correlation_id: str = Field(default_factory=lambda: str(uuid7()))
    causation_id: str | None = None


class EventEntity(DomainModel):
    type: str
    id: str
    name: str = Field(max_length=120)


class OperationalEvent(DomainModel):
    event_id: str = Field(default_factory=lambda: str(uuid7()))
    event_type: str = Field(pattern=r"^operational\.[a-z_]+\.[a-z_]+$")
    rule_id: str
    rule_version: int = Field(ge=1)
    severity: Severity
    occurred_at: datetime
    detected_at: datetime = Field(default_factory=utc_now)
    entity: EventEntity
    metrics: dict[str, float] = Field(default_factory=dict)
    dedup_fingerprint: str
    correlation_id: str = Field(default_factory=lambda: str(uuid7()))
    causation_id: str | None = None
    tenant_id: str = "default"
    status: OperationalEventStatus = OperationalEventStatus.QUEUED
    attempts: int = 0

    @field_validator("metrics")
    @classmethod
    def metric_keys_are_stable(cls, values: dict[str, float]) -> dict[str, float]:
        if any(not key.replace("_", "").replace(".", "").isalnum() for key in values):
            raise ValueError("Operational-event metric keys must be stable snake_case identifiers.")
        return values
