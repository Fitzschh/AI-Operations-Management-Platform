"""Approval lifecycle service; only a human manager can decide a plan (§10).

The service is the single writer of ``approval_requests`` and the driver of the plan machine's
approval edges. It never imports agents: outcomes leave through an injected ``OutcomePublisher``
so the Coordinator (the single writer of ``agent_messages``) reacts without a reverse dependency.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from touchorders_core.approvals.notifier import ConsoleNotifier, Notification, Notifier
from touchorders_core.datastore.repositories import ApprovalRepository, PlanRepository
from touchorders_core.domain.approvals import ApprovalRequest
from touchorders_core.domain.common import utc_now
from touchorders_core.domain.enums import ApprovalState, MessageType, PlanState
from touchorders_core.domain.plans import ActionPlan
from touchorders_core.observability.audit import AuditLogger
from touchorders_core.workflows.states import APPROVAL_TRANSITIONS, PLAN_TRANSITIONS


class OutcomePublisher(Protocol):
    """Emits a coordinator message. Implemented by the Coordinator in Stage 8."""

    def publish(self, *, type: MessageType, payload: dict[str, object], correlation_id: str, dedup_key: str) -> None: ...


class ApprovalService:
    def __init__(
        self,
        approvals: ApprovalRepository,
        plans: PlanRepository,
        audit: AuditLogger,
        *,
        notifier: Notifier | None = None,
        publisher: OutcomePublisher | None = None,
    ) -> None:
        self._approvals, self._plans, self._audit = approvals, plans, audit
        self._notifier = notifier or ConsoleNotifier()
        self._publisher = publisher

    # -- submission ---------------------------------------------------------------------------

    def submit(self, plan: ActionPlan, ttl_minutes: int = 60) -> ApprovalRequest | None:
        """Route a validated plan: all-LOW auto-approves; otherwise open a PENDING request."""
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
        self._notifier.notify(Notification(kind="approval.requested", entity_id=plan.plan_id, summary=plan.objective, correlation_id=plan.correlation_id))
        return request

    # -- decisions ----------------------------------------------------------------------------

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
        self._notifier.notify(Notification(kind="approval.decided", entity_id=plan.plan_id, summary=f"{request.decision} by {actor_id}", correlation_id=plan.correlation_id))
        self._publish(MessageType.APPROVAL_DECIDED, {"plan_id": plan.plan_id, "decision": request.decision, "note": note}, plan.correlation_id, f"approval:{request.approval_id}:{request.decision}")
        return request

    # -- expiry & escalation (§10.2) ----------------------------------------------------------

    def escalate(self, plan_id: str) -> ApprovalRequest:
        """Move an unacknowledged request to the fallback contact (T+30, CRITICAL)."""
        request = self._approvals.get_by_plan(plan_id)
        if request is None:
            raise KeyError(plan_id)
        request.state = APPROVAL_TRANSITIONS.next(request.state, "escalate")
        self._approvals.save(request)
        plan = self._plans.get(plan_id)
        correlation_id = plan.correlation_id if plan else request.plan_id
        self._audit.write(actor="system:approval_service", action="approval.escalated", entity_type="approval_request", entity_id=request.approval_id, correlation_id=correlation_id, payload={})
        self._notifier.notify(Notification(kind="approval.reminder", entity_id=plan_id, summary="Approval unacknowledged; escalated to fallback contact.", correlation_id=correlation_id, audience="fallback"))
        return request

    def expire_due(self, now: datetime | None = None) -> list[str]:
        """Expire every PENDING/ESCALATED request past its TTL; return the affected plan IDs."""
        now = now or utc_now()
        expired: list[str] = []
        for request in self._approvals.due(now):
            request.state = APPROVAL_TRANSITIONS.next(request.state, "expire")
            self._approvals.save(request)
            plan = self._plans.get(request.plan_id)
            correlation_id = plan.correlation_id if plan else request.plan_id
            if plan and plan.state == PlanState.PENDING_APPROVAL:
                plan.state = PLAN_TRANSITIONS.next(plan.state, "expire")
                self._plans.save(plan)
            self._audit.write(actor="system:approval_service", action="approval.expired", entity_type="approval_request", entity_id=request.approval_id, correlation_id=correlation_id, payload={"plan_id": request.plan_id})
            self._notifier.notify(Notification(kind="plan.expired", entity_id=request.plan_id, summary="Approval window elapsed; incident remains open.", correlation_id=correlation_id))
            self._publish(MessageType.PLAN_EXPIRED, {"plan_id": request.plan_id}, correlation_id, f"plan_expired:{request.approval_id}")
            expired.append(request.plan_id)
        return expired

    # -- internals ----------------------------------------------------------------------------

    def _publish(self, message_type: MessageType, payload: dict[str, object], correlation_id: str, dedup_key: str) -> None:
        if self._publisher is not None:
            self._publisher.publish(type=message_type, payload=payload, correlation_id=correlation_id, dedup_key=dedup_key)
