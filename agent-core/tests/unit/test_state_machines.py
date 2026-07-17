"""§11 transition tables are authoritative data; invalid moves must raise, not silently pass."""

from __future__ import annotations

import pytest

from touchorders_core.domain.enums import ApprovalState, IncidentState, PlanState, WorkflowState
from touchorders_core.workflows.states import (
    APPROVAL_TRANSITIONS, INCIDENT_TRANSITIONS, PLAN_TRANSITIONS, WORKFLOW_TRANSITIONS,
    InvalidTransition, execution_permitted,
)


def test_valid_plan_transition_advances_state() -> None:
    assert PLAN_TRANSITIONS.next(PlanState.DRAFT, "submit") == PlanState.PENDING_APPROVAL
    assert PLAN_TRANSITIONS.next(PlanState.PENDING_APPROVAL, "approve") == PlanState.APPROVED


def test_invalid_plan_transition_raises() -> None:
    # There is deliberately no DRAFT -> EXECUTING edge (NFR-5): planning cannot skip approval.
    with pytest.raises(InvalidTransition):
        PLAN_TRANSITIONS.next(PlanState.DRAFT, "start")
    with pytest.raises(InvalidTransition):
        PLAN_TRANSITIONS.next(PlanState.REJECTED, "approve")


def test_nfr5_execution_only_reachable_from_approval() -> None:
    # EXECUTING is reachable ONLY from APPROVED / AUTO_APPROVED, and only those states permit it.
    permitting = {state for state in PlanState if execution_permitted(state)}
    assert permitting == {PlanState.APPROVED, PlanState.AUTO_APPROVED}
    reaches_executing = {
        current for (current, _event), nxt in PLAN_TRANSITIONS._transitions.items()
        if nxt == PlanState.EXECUTING
    }
    assert reaches_executing == {PlanState.APPROVED, PlanState.AUTO_APPROVED}


def test_approval_and_workflow_reject_bad_moves() -> None:
    assert APPROVAL_TRANSITIONS.next(ApprovalState.PENDING, "escalate") == ApprovalState.ESCALATED
    with pytest.raises(InvalidTransition):
        APPROVAL_TRANSITIONS.next(ApprovalState.APPROVED, "reject")
    assert WORKFLOW_TRANSITIONS.next(WorkflowState.EXECUTING, "compensate") == WorkflowState.COMPENSATING
    with pytest.raises(InvalidTransition):
        WORKFLOW_TRANSITIONS.next(WorkflowState.COMPLETED, "start")


def test_incident_lifecycle_supports_self_heal_and_escalation() -> None:
    assert INCIDENT_TRANSITIONS.next(IncidentState.OPEN, "triage") == IncidentState.PLANNING
    assert INCIDENT_TRANSITIONS.next(IncidentState.PLANNING, "plan_submitted") == IncidentState.PLANNED
    assert INCIDENT_TRANSITIONS.next(IncidentState.OPEN, "self_heal") == IncidentState.RESOLVED
    assert INCIDENT_TRANSITIONS.next(IncidentState.PLANNING, "escalate") == IncidentState.MANUAL_HANDLING_REQUIRED
    with pytest.raises(InvalidTransition):
        INCIDENT_TRANSITIONS.next(IncidentState.RESOLVED, "triage")
