"""Incident report contracts, including runtime provenance."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from touchorders_core.domain.common import DomainModel, uuid7, utc_now
from touchorders_core.domain.enums import Confidence, IncidentCategory, IncidentState, Severity


class Evidence(DomainModel):
    metric: str
    value: float
    source_event_id: str


class SuspectedCause(DomainModel):
    cause: str = Field(max_length=200)
    confidence: Confidence


class IncidentReportOutput(DomainModel):
    category: IncidentCategory
    severity: Severity
    title: str = Field(max_length=80)
    summary: str = Field(max_length=700)
    evidence: list[Evidence] = Field(min_length=1, max_length=8)
    correlated_signals: list[str] = Field(default_factory=list, max_length=5)
    suspected_causes: list[SuspectedCause] = Field(default_factory=list, max_length=3)
    recommended_focus: list[str] = Field(default_factory=list, max_length=3)
    requires_manager_attention: bool

    @model_validator(mode="after")
    def keep_summary_bounded(self) -> "IncidentReportOutput":
        if len(self.summary.split()) > 120:
            raise ValueError("Incident summary must contain at most 120 words.")
        return self


class IncidentReport(IncidentReportOutput):
    incident_id: str = Field(default_factory=lambda: str(uuid7()))
    produced_by: str = Field(pattern=r"^(realtime_analyst|system_template)$")
    source_event_ids: list[str] = Field(min_length=1)
    dedup_fingerprint: str
    correlation_id: str
    state: IncidentState = IncidentState.OPEN
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
