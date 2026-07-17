"""§4.5 / §10.5 workflow execution: completion, NFR-5 guard, and saga compensation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from touchorders_core.domain.entities import InventoryItem, MenuItem
from touchorders_core.domain.enums import MessageType, PlanState, WorkflowState
from touchorders_core.domain.plans import ActionPlan, PlanStep
from touchorders_core.tools.base import ToolContext
from touchorders_core.tools.builtin import build_registry
from touchorders_core.tools.executor import ToolExecutor
from touchorders_core.workflows.engine import WorkflowEngine


class _Publisher:
    def __init__(self) -> None:
        self.messages: list[MessageType] = []

    def publish(self, *, type: MessageType, payload: dict, correlation_id: str, dedup_key: str) -> None:
        self.messages.append(type)


@pytest.fixture()
def registry():
    return build_registry()


@pytest.fixture()
def ctx(repos):
    repos.domain.upsert_inventory(InventoryItem(sku="chicken", name="Chicken", quantity=8, reorder_threshold=20))
    repos.domain.upsert_menu_item(MenuItem(id="m1", name="Wings", price=Decimal("10"), available=True))
    return ToolContext(domain=repos.domain, workflows=repos.workflows, correlation_id="corr-1", caller="workflow")


def _engine(registry, repos, publisher):
    executor = ToolExecutor(registry, repos.tool_invocations, repos.audit)
    return WorkflowEngine(repos.workflows, repos.plans, executor, registry, repos.audit, publisher=publisher)


def _plan(*, state: PlanState, steps: list[PlanStep]) -> ActionPlan:
    return ActionPlan(
        kind="ACTION_PLAN", priority="P1", objective="Handle stockout", rationale="Low stock.",
        expected_impact="Avoid 86.", risk_assessment="Medium.", correlation_id="corr-1",
        state=state, steps=steps,
    )


def _po_step(step_no=1):
    return PlanStep(step_no=step_no, tool_name="draft_purchase_order", expected_outcome="PO drafted",
                    arguments={"supplier_id": "supplier_main", "lines": [{"sku": "chicken", "quantity": 40}], "needed_by": "2026-07-18T00:00:00Z"})


def test_approved_plan_runs_to_completion(registry, repos, ctx) -> None:
    publisher = _Publisher()
    plan = _plan(state=PlanState.APPROVED, steps=[
        _po_step(1),
        PlanStep(step_no=2, tool_name="send_notification", expected_outcome="staff told",
                 arguments={"channel": "staff_ops", "audience": "kitchen", "template_id": "reorder_initiated"}),
    ])
    repos.plans.save(plan)

    outcome = _engine(registry, repos, publisher).run_plan(plan, ctx)

    assert outcome.state == WorkflowState.COMPLETED
    assert outcome.completed_steps == [1, 2]
    assert repos.plans.get(plan.plan_id).state == PlanState.COMPLETED
    assert MessageType.WORKFLOW_COMPLETED in publisher.messages
    assert repos.audit.verify() is True


def test_unapproved_plan_cannot_execute(registry, repos, ctx) -> None:
    plan = _plan(state=PlanState.DRAFT, steps=[_po_step(1)])
    repos.plans.save(plan)
    with pytest.raises(PermissionError):
        _engine(registry, repos, _Publisher()).run_plan(plan, ctx)


def test_midworkflow_failure_triggers_reverse_order_compensation(registry, repos, ctx) -> None:
    publisher = _Publisher()
    plan = _plan(state=PlanState.APPROVED, steps=[
        _po_step(1),  # -> compensated by void_purchase_order_draft
        PlanStep(step_no=2, tool_name="set_menu_item_availability", expected_outcome="86 wings",
                 arguments={"menu_item_id": "m1", "available": False, "reason": "rush"}),  # -> restored
        PlanStep(step_no=3, tool_name="send_notification", expected_outcome="fails",
                 arguments={"channel": "not_an_allowlisted_channel", "audience": "x", "template_id": "t"}),  # fails G2
    ])
    repos.plans.save(plan)

    outcome = _engine(registry, repos, publisher).run_plan(plan, ctx)

    assert outcome.state == WorkflowState.COMPENSATED
    assert outcome.failed_step == 3
    assert outcome.compensated_steps == [2, 1]  # reverse order
    assert outcome.uncompensated_steps == []
    # step 2 flipped the menu item to unavailable; compensation restored it exactly.
    assert repos.domain.get_menu_item("m1").available is True
    assert repos.plans.get(plan.plan_id).state == PlanState.FAILED
    assert MessageType.WORKFLOW_FAILED in publisher.messages
    assert repos.audit.verify() is True
