"""Authoritative declarative lifecycle transition tables."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

from touchorders_core.domain.enums import ApprovalState, IncidentState, PlanState, WorkflowState


S = TypeVar("S")


class InvalidTransition(ValueError):
    pass


class TransitionTable:
    def __init__(self, transitions: Mapping[tuple[S, str], S]) -> None:
        self._transitions = dict(transitions)

    def next(self, current: S, event: str) -> S:
        try:
            return self._transitions[(current, event)]
        except KeyError as exc:
            raise InvalidTransition(f"Cannot transition {current} using {event}.") from exc


PLAN_TRANSITIONS = TransitionTable({
    (PlanState.DRAFT, "submit"): PlanState.PENDING_APPROVAL,
    (PlanState.DRAFT, "auto_approve"): PlanState.AUTO_APPROVED,
    (PlanState.PENDING_APPROVAL, "approve"): PlanState.APPROVED,
    (PlanState.PENDING_APPROVAL, "reject"): PlanState.REJECTED,
    (PlanState.PENDING_APPROVAL, "expire"): PlanState.EXPIRED,
    (PlanState.APPROVED, "start"): PlanState.EXECUTING,
    (PlanState.AUTO_APPROVED, "start"): PlanState.EXECUTING,
    (PlanState.EXECUTING, "complete"): PlanState.COMPLETED,
    (PlanState.EXECUTING, "fail"): PlanState.FAILED,
})

APPROVAL_TRANSITIONS = TransitionTable({
    (ApprovalState.PENDING, "approve"): ApprovalState.APPROVED,
    (ApprovalState.PENDING, "reject"): ApprovalState.REJECTED,
    (ApprovalState.PENDING, "escalate"): ApprovalState.ESCALATED,
    (ApprovalState.PENDING, "expire"): ApprovalState.EXPIRED,
    (ApprovalState.ESCALATED, "approve"): ApprovalState.APPROVED,
    (ApprovalState.ESCALATED, "reject"): ApprovalState.REJECTED,
    (ApprovalState.ESCALATED, "expire"): ApprovalState.EXPIRED,
})

WORKFLOW_TRANSITIONS = TransitionTable({
    (WorkflowState.PENDING, "start"): WorkflowState.EXECUTING,
    (WorkflowState.EXECUTING, "complete"): WorkflowState.COMPLETED,
    (WorkflowState.EXECUTING, "fail"): WorkflowState.FAILED,
    (WorkflowState.EXECUTING, "compensate"): WorkflowState.COMPENSATING,
    (WorkflowState.FAILED, "compensate"): WorkflowState.COMPENSATING,
    (WorkflowState.COMPENSATING, "complete"): WorkflowState.COMPENSATED,
    (WorkflowState.COMPENSATING, "manual_cleanup"): WorkflowState.REQUIRES_MANUAL_CLEANUP,
})

# §11.2 Incident lifecycle. The manager drives OPEN -> PLANNING -> PLANNED; the rules engine's
# hysteresis clear_when can self-heal OPEN/PLANNED -> RESOLVED without any human or LLM action.
INCIDENT_TRANSITIONS = TransitionTable({
    (IncidentState.OPEN, "triage"): IncidentState.PLANNING,
    (IncidentState.OPEN, "self_heal"): IncidentState.RESOLVED,
    (IncidentState.OPEN, "escalate"): IncidentState.MANUAL_HANDLING_REQUIRED,
    (IncidentState.PLANNING, "plan_submitted"): IncidentState.PLANNED,
    (IncidentState.PLANNING, "defer"): IncidentState.DEFERRED,
    (IncidentState.PLANNING, "escalate"): IncidentState.MANUAL_HANDLING_REQUIRED,
    (IncidentState.PLANNED, "resolved"): IncidentState.RESOLVED,
    (IncidentState.PLANNED, "reopen"): IncidentState.OPEN,
    (IncidentState.PLANNED, "self_heal"): IncidentState.RESOLVED,
    (IncidentState.DEFERRED, "triage"): IncidentState.PLANNING,
    (IncidentState.MANUAL_HANDLING_REQUIRED, "resolved"): IncidentState.RESOLVED,
})


def execution_permitted(plan_state: PlanState) -> bool:
    """NFR-5: no path reaches execution other than recorded human/LOW policy approval."""

    return plan_state in {PlanState.APPROVED, PlanState.AUTO_APPROVED}
