"""Approval lifecycle service; only a human manager can decide a plan."""

from __future__ import annotations

from datetime import timedelta

from touchorders_core.datastore.repositories import ApprovalRepository, PlanRepository
from touchorders_core.domain.approvals import ApprovalRequest
from touchorders_core.domain.common import utc_now
from touchorders_core.domain.enums import ApprovalState, PlanState
from touchorders_core.domain.plans import ActionPlan
from touchorders_core.observability.audit import AuditLogger
from touchorders_core.workflows.states import APPROVAL_TRANSITIONS, PLAN_TRANSITIONS


class ApprovalService:
    def __init__(self, approvals: ApprovalRepository, plans: PlanRepository, audit: AuditLogger) -> None:
        self._approvals, self._plans, self._audit = approvals, plans, audit

    def submit(self, plan: ActionPlan, ttl_minutes: int = 60) -> ApprovalRequest | None:
        if not plan.requires_approval:
            plan.state = PLAN_TRANSITIONS.next(plan.state, "auto_approve")
            self._plans.save(plan)
            self._audit.write(actor="system:approval_service", action="plan.auto_approved", entity_type="action_plan", entity_id=plan.plan_id, correlation_id=plan.correlation_id, payload={"policy": "LOW_RISK"})
            return None
        plan.state = PLAN_TRANSITIONS.next(plan.state, "submit")
        self._plans.save(plan)
        request = ApprovalRequest(plan_id=plan.plan_id, expires_at=utc_now() + timedelta(minutes=ttl_minutes))
        self._approvals.save(request)
        self._audit.write(actor="system:approval_service", action="plan.submitted", entity_type="action_plan", entity_id=plan.plan_id, correlation_id=plan.correlation_id, payload={"approval_id": request.approval_id})
        return request

    def decide(self, *, plan_id: str, approve: bool, actor_id: str, is_human_manager: bool, note: str | None = None) -> ApprovalRequest:
        if not is_human_manager:
            raise PermissionError("Only a human manager may decide an approval request.")
        if not approve and not note:
            raise ValueError("A rejection note is mandatory.")
        plan = self._plans.get(plan_id)
        request = self._approvals.get_by_plan(plan_id)
        if not plan or not request:
            raise KeyError(plan_id)
        if request.state not in {ApprovalState.PENDING, ApprovalState.ESCALATED}:
            raise ValueError("Approval request has already been decided.")
        event = "approve" if approve else "reject"
        request.state = APPROVAL_TRANSITIONS.next(request.state, event)
        request.decision, request.note, request.decided_by, request.decided_at = event.upper(), note, actor_id, utc_now()
        plan.state = PLAN_TRANSITIONS.next(plan.state, event)
        self._approvals.save(request)
        self._plans.save(plan)
        self._audit.write(actor=f"human:{actor_id}", action="approval.decided", entity_type="approval_request", entity_id=request.approval_id, correlation_id=plan.correlation_id, payload={"decision": request.decision, "note": note})
        return request
