"""§3 agent building blocks: definition loading, relevance filter, severity monotonicity."""

from __future__ import annotations

from pathlib import Path

import pytest

from touchorders_core.agents.coordinator import Coordinator
from touchorders_core.agents.definitions import load_agent_definitions
from touchorders_core.agents.validators.incident import SeverityMonotonicityError, enforce_severity_monotonicity
from touchorders_core.domain.common import utc_now
from touchorders_core.domain.enums import AgentName, Horizon, RiskTier, Severity
from touchorders_core.domain.events import EventEntity, OperationalEvent
from touchorders_core.domain.incidents import Evidence, IncidentReportOutput
from touchorders_core.domain.reports import BusinessRecommendation, BusinessReport, BusinessRisk

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def test_agent_definitions_load_from_config() -> None:
    definitions = load_agent_definitions(CONFIG_DIR)
    assert set(definitions) == {AgentName.REALTIME_ANALYST, AgentName.BUSINESS_ANALYST, AgentName.OPERATIONS_MANAGER}
    manager = definitions[AgentName.OPERATIONS_MANAGER]
    assert "get_inventory_status" in manager.tools_read
    assert manager.daily_budget.input == 60000
    assert definitions[AgentName.REALTIME_ANALYST].output_schema is IncidentReportOutput
    assert "[S1 ROLE]" in manager.system_prompt  # prompt file was loaded


def _report(*, rec_priority: RiskTier, risk_actionable: bool) -> BusinessReport:
    return BusinessReport(
        kpi_snapshot_id="snap-1", headline="Weekly revenue steady",
        insights=[], risks=[BusinessRisk(text="Supplier delay", actionable=risk_actionable, supporting_metrics=["lead_time"])],
        recommendations=[BusinessRecommendation(text="Renegotiate supplier terms", priority=rec_priority, horizon=Horizon.THIS_WEEK)],
    )


def test_relevance_filter_only_wakes_manager_for_high_or_actionable() -> None:
    assert Coordinator.business_report_relevant(_report(rec_priority=RiskTier.HIGH, risk_actionable=False)) is True
    assert Coordinator.business_report_relevant(_report(rec_priority=RiskTier.LOW, risk_actionable=True)) is True
    assert Coordinator.business_report_relevant(_report(rec_priority=RiskTier.LOW, risk_actionable=False)) is False


def _event(severity: Severity) -> OperationalEvent:
    return OperationalEvent(
        event_type="operational.inventory_risk.low_stock", rule_id="inventory.low_stock", rule_version=1,
        severity=severity, occurred_at=utc_now(),
        entity=EventEntity(type="inventory_item", id="chicken", name="Chicken"), metrics={"remaining_units": 8.0},
        dedup_fingerprint="fp",
    )


def _incident(severity: Severity) -> IncidentReportOutput:
    return IncidentReportOutput(
        category="INVENTORY_RISK", severity=severity, title="t", summary="s",
        evidence=[Evidence(metric="remaining_units", value=8.0, source_event_id="e")],
        suspected_causes=[], requires_manager_attention=True,
    )


def test_analyst_cannot_lower_severity() -> None:
    with pytest.raises(SeverityMonotonicityError):
        enforce_severity_monotonicity(_incident(Severity.WARNING), [_event(Severity.HIGH)])
    # confirming or raising is fine
    enforce_severity_monotonicity(_incident(Severity.CRITICAL), [_event(Severity.HIGH)])
