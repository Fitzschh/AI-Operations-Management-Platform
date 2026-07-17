"""Deterministic KPI and schema-constrained business report contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from touchorders_core.domain.common import DomainModel, uuid7, utc_now
from touchorders_core.domain.enums import Confidence, Horizon, RiskTier


class KPISnapshot(DomainModel):
    snapshot_id: str = Field(default_factory=lambda: str(uuid7()))
    tenant_id: str = "default"
    period_start: datetime
    period_end: datetime
    metrics: dict[str, float]
    forecasts: dict[str, float] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=utc_now)

    @property
    def numeric_vocabulary(self) -> dict[str, float]:
        return {**self.metrics, **self.forecasts}


class BusinessInsight(DomainModel):
    text: str = Field(max_length=280)
    supporting_metrics: list[str] = Field(min_length=1, max_length=4)
    confidence: Confidence


class BusinessRisk(DomainModel):
    text: str = Field(max_length=280)
    actionable: bool
    supporting_metrics: list[str]


class BusinessRecommendation(DomainModel):
    text: str = Field(max_length=280)
    priority: RiskTier
    horizon: Horizon


class ForecastAnnotation(DomainModel):
    forecast_key: str
    annotation: str = Field(max_length=200)


class BusinessReportOutput(DomainModel):
    headline: str = Field(max_length=140)
    insights: list[BusinessInsight] = Field(default_factory=list, max_length=6)
    risks: list[BusinessRisk] = Field(default_factory=list, max_length=4)
    recommendations: list[BusinessRecommendation] = Field(default_factory=list, max_length=5)
    forecast_annotations: list[ForecastAnnotation] = Field(default_factory=list, max_length=4)


class BusinessReport(BusinessReportOutput):
    report_id: str = Field(default_factory=lambda: str(uuid7()))
    kpi_snapshot_id: str
    correlation_id: str = Field(default_factory=lambda: str(uuid7()))
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
