"""§10 approval lifecycle: human-only decisions, mandatory reject notes, expiry, escalation."""

from __future__ import annotations

import pytest

from touchorders_core.approvals.notifier import CollectingNotifier
from touchorders_core.approvals.service import ApprovalService
from touchorders_core.domain.enums import ApprovalState, MessageType, PlanState
from touchorders_core.domain.plans import ActionPlan, PlanStep


class _CollectingPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[MessageType, dict]] = []

    def publish(self, *, type: MessageType, payload: dict, correlation_id: str, dedup_key: str) -> None:
        self.published.append((type, payload))


def _plan(*, requires_approval: bool, tool: str = "draft_purchase_order") -> ActionPlan:
    return ActionPlan(
        kind="ACTION_PLAN", priority="P1", objective="Reorder critical stock",
        rationale="Projected stockout before the dinner rush.", expected_impact="Avoid an 86.",
        risk_assessment="Medium: a supplier PO draft.", correlation_id="corr-1",
        requires_approval=requires_approval,
        steps=[PlanStep(step_no=1, tool_name=tool, expected_outcome="PO drafted")],
    )


def _service(repos, notifier=None, publisher=None) -> ApprovalService:
    return ApprovalService(repos.approvals, repos.plans, repos.audit, notifier=notifier, publisher=publisher)


def test_all_low_plan_auto_approves_without_a_request(repos) -> None:
    plan = _plan(requires_approval=False)
    repos.plans.save(plan)
    service = _service(repos)

    assert service.submit(plan) is None
    assert repos.plans.get(plan.plan_id).state == PlanState.AUTO_APPROVED


def test_submit_opens_pending_request_and_notifies(repos) -> None:
    plan = _plan(requires_approval=True)
    repos.plans.save(plan)
    notifier = CollectingNotifier()
    request = _service(repos, notifier=notifier).submit(plan)

    assert request is not None and request.state == ApprovalState.PENDING
    assert repos.plans.get(plan.plan_id).state == PlanState.PENDING_APPROVAL
    assert [n.kind for n in notifier.delivered] == ["approval.requested"]


def test_human_approve_advances_plan_and_publishes_outcome(repos) -> None:
    plan = _plan(requires_approval=True)
    repos.plans.save(plan)
    publisher = _CollectingPublisher()
    service = _service(repos, publisher=publisher)
    service.submit(plan)

    request = service.decide(plan_id=plan.plan_id, approve=True, actor_id="mgr", is_human_manager=True)

    assert request.state == ApprovalState.APPROVED
    assert repos.plans.get(plan.plan_id).state == PlanState.APPROVED
    assert publisher.published[0][0] == MessageType.APPROVAL_DECIDED


def test_rejection_requires_a_note(repos) -> None:
    plan = _plan(requires_approval=True)
    repos.plans.save(plan)
    service = _service(repos)
    service.submit(plan)
    with pytest.raises(ValueError):
        service.decide(plan_id=plan.plan_id, approve=False, actor_id="mgr", is_human_manager=True)


def test_machine_identities_cannot_decide(repos) -> None:
    plan = _plan(requires_approval=True)
    repos.plans.save(plan)
    service = _service(repos)
    service.submit(plan)
    with pytest.raises(PermissionError):
        service.decide(plan_id=plan.plan_id, approve=True, actor_id="ingest-key", is_human_manager=False)


def test_second_decision_is_rejected(repos) -> None:
    plan = _plan(requires_approval=True)
    repos.plans.save(plan)
    service = _service(repos)
    service.submit(plan)
    service.decide(plan_id=plan.plan_id, approve=True, actor_id="mgr", is_human_manager=True, note=None)
    with pytest.raises(ValueError):
        service.decide(plan_id=plan.plan_id, approve=False, actor_id="mgr", is_human_manager=True, note="changed mind")


def test_expiry_returns_plan_to_open_and_notifies_manager(repos) -> None:
    plan = _plan(requires_approval=True)
    repos.plans.save(plan)
    publisher = _CollectingPublisher()
    service = _service(repos, publisher=publisher)
    service.submit(plan, ttl_minutes=-1)  # already past its window

    expired = service.expire_due()

    assert expired == [plan.plan_id]
    assert repos.plans.get(plan.plan_id).state == PlanState.EXPIRED
    assert repos.approvals.get_by_plan(plan.plan_id).state == ApprovalState.EXPIRED
    assert publisher.published[-1][0] == MessageType.PLAN_EXPIRED


def test_escalation_moves_request_to_fallback(repos) -> None:
    plan = _plan(requires_approval=True)
    repos.plans.save(plan)
    service = _service(repos)
    service.submit(plan)

    request = service.escalate(plan.plan_id)

    assert request.state == ApprovalState.ESCALATED
