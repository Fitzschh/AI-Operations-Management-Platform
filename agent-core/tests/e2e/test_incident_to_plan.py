"""Stage 8 end-to-end (§4.1) on FakeLLM: certified event -> incident -> coalesced triage -> plan
-> human approval -> workflow execution. No network, no API key.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from touchorders_core.agents.coordinator import Coordinator
from touchorders_core.agents.definitions import build_daily_budgets, build_gateway_config, load_agent_definitions
from touchorders_core.agents.runtime import AgentRuntime, OperationsManager, RealtimeAnalyst, make_realtime_trigger
from touchorders_core.approvals.service import ApprovalService
from touchorders_core.domain.common import utc_now
from touchorders_core.domain.entities import InventoryItem, MenuItem
from touchorders_core.domain.enums import AgentName, MessageType, PlanState, Severity, WorkflowState
from touchorders_core.domain.events import EventEntity, OperationalEvent
from touchorders_core.llm.budget import BudgetTracker
from touchorders_core.llm.gateway import FakeLLMClient, LLMGateway
from touchorders_core.memory.store import MemoryStore
from touchorders_core.rules_engine.dispatcher import Dispatcher
from touchorders_core.rules_engine.queue import EventQueue
from touchorders_core.tools.base import ToolContext
from touchorders_core.tools.builtin import build_registry
from touchorders_core.workflows.engine import WorkflowEngine
from touchorders_core.tools.executor import ToolExecutor

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _canned_incident() -> dict:
    return {
        "category": "INVENTORY_RISK", "severity": "HIGH", "title": "Chicken stockout risk",
        "summary": "Chicken is below reorder threshold with a projected stockout before the dinner rush.",
        "evidence": [{"metric": "remaining_units", "value": 8.0, "source_event_id": "evt"}],
        "correlated_signals": ["operational.inventory_risk.low_stock"],
        "suspected_causes": [{"cause": "Higher-than-baseline wings demand", "confidence": "MEDIUM"}],
        "recommended_focus": ["Chicken replenishment lead time"], "requires_manager_attention": True,
    }


def _canned_plan() -> dict:
    return {
        "kind": "ACTION_PLAN", "priority": "P1", "objective": "Reorder chicken before the rush",
        "rationale": "Chicken is below threshold and projected to run out this shift; draft a supplier PO and alert the kitchen.",
        "expected_impact": "Avoid an 86 during dinner service.", "risk_assessment": "Medium: a supplier PO draft and a staff alert.",
        "incident_priorities": [{"incident_id": "i-1", "priority": "P1", "reason": "Projected stockout this shift."}],
        "steps": [
            {"step_no": 1, "tool_name": "draft_purchase_order", "expected_outcome": "PO drafted", "depends_on": [],
             "arguments": {"supplier_id": "supplier_main", "lines": [{"sku": "chicken", "quantity": 40}], "needed_by": "2026-07-18T00:00:00Z"}},
            {"step_no": 2, "tool_name": "send_notification", "expected_outcome": "Kitchen alerted", "depends_on": [1],
             "arguments": {"channel": "staff_ops", "audience": "kitchen", "template_id": "reorder_initiated", "variables": {"sku": "chicken"}}},
        ],
    }


def test_event_to_incident_to_plan_to_execution(repos) -> None:
    import asyncio

    # --- wiring (the composition root, in miniature) --------------------------------------
    repos.domain.upsert_inventory(InventoryItem(sku="chicken", name="Chicken", quantity=8, reorder_threshold=20))
    repos.domain.upsert_menu_item(MenuItem(id="wings", name="Wings", price=Decimal("12"), available=True))

    registry = build_registry()
    definitions = load_agent_definitions(CONFIG_DIR)
    client = FakeLLMClient()
    client.register("realtime_incident", _canned_incident())
    client.register("manager_plan", _canned_plan())
    gateway = LLMGateway(build_gateway_config(definitions), client, repos.llm_calls, repos.audit, budget=BudgetTracker(build_daily_budgets(definitions)))
    runtime = AgentRuntime(gateway)
    coordinator = Coordinator(repos.messages)

    analyst = RealtimeAnalyst(definitions[AgentName.REALTIME_ANALYST], runtime, repos.incidents, MemoryStore(repos.memory, AgentName.REALTIME_ANALYST), coordinator)
    manager = OperationsManager(definitions[AgentName.OPERATIONS_MANAGER], runtime, registry, repos.plans, MemoryStore(repos.memory, AgentName.OPERATIONS_MANAGER))

    # --- 1) a certified HIGH event flows through the dispatcher to the analyst -------------
    queue = EventQueue(repos.events)
    event = OperationalEvent(
        event_type="operational.inventory_risk.low_stock", rule_id="inventory.low_stock", rule_version=1,
        severity=Severity.HIGH, occurred_at=utc_now(), entity=EventEntity(type="inventory_item", id="chicken", name="Chicken"),
        metrics={"remaining_units": 8.0, "threshold": 20.0, "projected_stockout_minutes": 45.0},
        dedup_fingerprint="fp-chicken-high", correlation_id="corr-e2e",
    )
    dispatcher = Dispatcher(queue, realtime_trigger=make_realtime_trigger(analyst))

    async def drive() -> None:
        await queue.publish(event)
        await dispatcher.dispatch_once()

    asyncio.run(drive())

    incident = repos.incidents.active()[0]
    assert incident.produced_by == "realtime_analyst" and incident.severity == Severity.HIGH
    assert incident.correlation_id == "corr-e2e"

    # --- 2) coordinator coalesces the triage; the manager plans once ----------------------
    incident_ids, consumed, _ = coordinator.drain_triage()
    assert incident_ids == [incident.incident_id]
    plan = manager.plan([repos.incidents.get(i) for i in incident_ids])
    coordinator.consume(consumed)

    assert plan.kind == "ACTION_PLAN" and plan.correlation_id == "corr-e2e"
    assert plan.requires_approval is True  # PO draft is MEDIUM -> human approval required
    assert [s.tool_name for s in plan.steps] == ["draft_purchase_order", "send_notification"]

    # exactly two LLM calls billed (analyst + manager), both successful
    from sqlalchemy import select
    from touchorders_core.datastore.orm import LLMCallRow
    with repos.factory() as session:
        outcomes = [r.outcome for r in session.scalars(select(LLMCallRow)).all()]
    assert outcomes == ["SUCCESS", "SUCCESS"]

    # --- 3) human approves; workflow executes to completion (§4.1 tail) --------------------
    approvals = ApprovalService(repos.approvals, repos.plans, repos.audit, publisher=coordinator)
    approvals.submit(plan)
    approvals.decide(plan_id=plan.plan_id, approve=True, actor_id="manager-jo", is_human_manager=True)

    approved_plan = repos.plans.get(plan.plan_id)
    assert approved_plan.state == PlanState.APPROVED

    executor = ToolExecutor(registry, repos.tool_invocations, repos.audit)
    engine = WorkflowEngine(repos.workflows, repos.plans, executor, registry, repos.audit, publisher=coordinator)
    ctx = ToolContext(domain=repos.domain, workflows=repos.workflows, correlation_id=plan.correlation_id, caller="workflow")
    outcome = engine.run_plan(approved_plan, ctx)

    assert outcome.state == WorkflowState.COMPLETED
    assert repos.plans.get(plan.plan_id).state == PlanState.COMPLETED
    assert repos.audit.verify() is True
