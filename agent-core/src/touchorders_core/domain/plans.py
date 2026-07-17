"""Action-plan proposal contracts; they contain no executable capability."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from touchorders_core.domain.common import DomainModel, uuid7, utc_now
from touchorders_core.domain.enums import PlanState, Priority, RiskTier


class IncidentPriority(DomainModel):
    incident_id: str
    priority: Priority
    reason: str = Field(max_length=160)


class PlanStep(DomainModel):
    step_no: int = Field(ge=1)
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{2,48}$")
    arguments: dict[str, object] = Field(default_factory=dict)
    expected_outcome: str = Field(max_length=160)
    depends_on: list[int] = Field(default_factory=list)
    tool_version: int | None = None
    risk_tier: RiskTier | None = None


class ActionPlanOutput(DomainModel):
    kind: Literal["ACTION_PLAN", "PRIORITIZATION_ONLY", "NO_ACTION_NEEDED"]
    priority: Priority
    objective: str = Field(max_length=200)
    rationale: str = Field(max_length=900)
    expected_impact: str = Field(max_length=300)
    risk_assessment: str = Field(max_length=300)
    steps: list[PlanStep] = Field(default_factory=list, max_length=8)
    incident_priorities: list[IncidentPriority] = Field(default_factory=list)

    @model_validator(mode="after")
    def action_kind_controls_steps(self) -> "ActionPlanOutput":
        if self.kind == "ACTION_PLAN" and not self.steps:
            raise ValueError("ACTION_PLAN must contain at least one step.")
        if self.kind != "ACTION_PLAN" and self.steps:
            raise ValueError("Only ACTION_PLAN output may contain steps.")
        if len(self.rationale.split()) > 150:
            raise ValueError("Action-plan rationale must contain at most 150 words.")
        return self


class ActionPlan(ActionPlanOutput):
    plan_id: str = Field(default_factory=lambda: str(uuid7()))
    correlation_id: str
    state: PlanState = PlanState.DRAFT
    requires_approval: bool = True
    revision_of: str | None = None
    revision_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
