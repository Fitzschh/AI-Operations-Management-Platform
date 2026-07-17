"""Agent runtime (§3.1–3.5): stateless, schema-bounded invocation patterns.

Each agent is: deterministic trigger -> deterministic context bundle -> one gateway call with a
strict output schema -> deterministic post-validation -> typed message to the Coordinator. The
generic :class:`AgentRuntime` is the single round-trip; the three role classes add only context
assembly, provenance wrapping, memory writes, and coordinator publication (§19.1).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from touchorders_core.agents.context import business as business_ctx
from touchorders_core.agents.context import manager as manager_ctx
from touchorders_core.agents.context import realtime as realtime_ctx
from touchorders_core.agents.coordinator import Coordinator
from touchorders_core.agents.definitions import AgentDefinition
from touchorders_core.agents.validators.incident import enforce_severity_monotonicity
from touchorders_core.agents.validators.plan import enrich_steps, requires_approval
from touchorders_core.datastore.repositories import IncidentRepository, PlanRepository, ReportRepository
from touchorders_core.domain.common import uuid7
from touchorders_core.domain.enums import MessageType
from touchorders_core.domain.events import OperationalEvent
from touchorders_core.domain.incidents import IncidentReport
from touchorders_core.domain.plans import ActionPlan
from touchorders_core.domain.reports import BusinessReport, KPISnapshot
from touchorders_core.llm.gateway import LLMGateway, ReadToolRunner
from touchorders_core.memory.store import MemoryStore
from touchorders_core.tools.registry import ToolRegistry

_ECHO_VALUES = frozenset({"value"})
_NO_ECHO: frozenset[str] = frozenset()


class AgentRuntime:
    """The generic BaseAgent executor: exactly one gateway round-trip per invocation (§3.2)."""

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    def invoke(
        self,
        definition: AgentDefinition,
        purpose: str,
        bundle: dict[str, Any],
        *,
        read_tool_specs: Sequence[dict[str, Any]] = (),
        read_tool_runner: ReadToolRunner | None = None,
        echo_keys: frozenset[str] = _ECHO_VALUES,
        correlation_id: str | None = None,
    ):
        return self._gateway.structured_call(
            agent=definition.name, purpose=purpose, bundle=bundle, output_schema=definition.output_schema,
            read_tool_specs=list(read_tool_specs), read_tool_runner=read_tool_runner,
            echo_keys=echo_keys, correlation_id=correlation_id,
        ).output


class RealtimeAnalyst:
    def __init__(self, definition: AgentDefinition, runtime: AgentRuntime, incidents: IncidentRepository, memory: MemoryStore, coordinator: Coordinator) -> None:
        self._definition, self._runtime = definition, runtime
        self._incidents, self._memory, self._coordinator = incidents, memory, coordinator

    def analyze(self, events: Sequence[OperationalEvent]) -> IncidentReport:
        if not events:
            raise ValueError("Realtime analyst requires at least one operational event.")
        bundle = realtime_ctx.build_context(events, self._incidents.active())
        output = self._runtime.invoke(self._definition, "realtime_incident", bundle, echo_keys=_ECHO_VALUES, correlation_id=events[0].correlation_id)
        enforce_severity_monotonicity(output, events)  # §3.5: confirm or raise, never lower
        report = IncidentReport(
            **output.model_dump(), produced_by="realtime_analyst",
            source_event_ids=[e.event_id for e in events], dedup_fingerprint=events[0].dedup_fingerprint,
            correlation_id=events[0].correlation_id,
        )
        self._incidents.save(report)
        self._memory.remember(kind="active_incident", key=f"incident:{events[0].entity.id}:{events[0].rule_id}", payload={"incident_id": report.incident_id, "severity": report.severity.value, "status": "OPEN"}, summary=report.title, correlation_id=report.correlation_id)
        self._coordinator.publish(type=MessageType.INCIDENT_REPORT_READY, payload={"incident_id": report.incident_id, "severity": report.severity.value, "category": report.category.value}, correlation_id=report.correlation_id, dedup_key=f"incident_ready:{report.incident_id}")
        return report


class BusinessAnalyst:
    def __init__(self, definition: AgentDefinition, runtime: AgentRuntime, reports: ReportRepository, memory: MemoryStore, coordinator: Coordinator) -> None:
        self._definition, self._runtime = definition, runtime
        self._reports, self._memory, self._coordinator = reports, memory, coordinator

    def analyze(self, snapshot: KPISnapshot, prior_report_summary: str | None = None) -> BusinessReport:
        bundle = business_ctx.build_context(snapshot, prior_report_summary)
        output = self._runtime.invoke(self._definition, "business_report", bundle, echo_keys=_NO_ECHO)
        report = BusinessReport(**output.model_dump(), kpi_snapshot_id=snapshot.snapshot_id)
        self._reports.save(report)
        self._memory.remember(kind="report", key=f"report:{snapshot.period_end.isoformat()}", payload=report.model_dump(mode="json"), summary=report.headline, correlation_id=report.correlation_id)
        if self._coordinator.business_report_relevant(report):  # §3.4 relevance filter
            self._coordinator.publish(type=MessageType.BUSINESS_REPORT_RELEVANT, payload={"report_id": report.report_id}, correlation_id=report.correlation_id, dedup_key=f"business_report:{report.report_id}")
        return report


class OperationsManager:
    def __init__(self, definition: AgentDefinition, runtime: AgentRuntime, registry: ToolRegistry, plans: PlanRepository, memory: MemoryStore, *, read_tool_runner: ReadToolRunner | None = None) -> None:
        self._definition, self._runtime, self._registry = definition, runtime, registry
        self._plans, self._memory, self._read_tool_runner = plans, memory, read_tool_runner

    def plan(self, incidents: Sequence[IncidentReport], *, restaurant_status: dict[str, Any] | None = None) -> ActionPlan:
        correlation_id = incidents[0].correlation_id if incidents else str(uuid7())
        bundle = manager_ctx.build_context(
            incidents, restaurant_status=restaurant_status,
            recent_outcomes=self._memory.recall(kinds=["approval_outcome"], limit=10),
            lessons=self._memory.recall(kinds=["lesson"], limit=10),
        )
        output = self._runtime.invoke(
            self._definition, "manager_plan", bundle,
            read_tool_specs=self._registry.openai_read_tool_specs(), read_tool_runner=self._read_tool_runner,
            echo_keys=_NO_ECHO, correlation_id=correlation_id,
        )
        if output.kind == "ACTION_PLAN":
            steps = enrich_steps(output, self._registry)
            needs_approval = requires_approval(steps)  # never model-authored (A.4)
        else:
            steps, needs_approval = [], False
        plan = ActionPlan(
            kind=output.kind, priority=output.priority, objective=output.objective, rationale=output.rationale,
            expected_impact=output.expected_impact, risk_assessment=output.risk_assessment,
            steps=steps, incident_priorities=output.incident_priorities,
            correlation_id=correlation_id, requires_approval=needs_approval,
        )
        self._plans.save(plan)
        self._memory.remember(kind="plan", key=f"plan:{plan.plan_id}", payload={"objective": plan.objective, "state": plan.state.value}, summary=plan.objective, correlation_id=correlation_id)
        return plan


def make_realtime_trigger(analyst: RealtimeAnalyst) -> Callable[[list[OperationalEvent]], Awaitable[IncidentReport]]:
    """Adapt the analyst to the Dispatcher's async ``realtime_trigger`` seam (§7.7)."""

    async def trigger(events: list[OperationalEvent]) -> IncidentReport:
        return analyst.analyze(events)

    return trigger
