"""Workflow Engine (§4.5, §10.5): execute an approved plan step-by-step, compensate on failure.

Structural safety (NFR-5): a plan can only be executed here if ``execution_permitted`` holds,
i.e. it reached APPROVED / AUTO_APPROVED through a recorded decision. Each step checkpoints into
``workflow_step_executions``; on a step failure the engine runs registered compensations for the
completed steps in reverse order (the saga).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from touchorders_core.approvals.notifier import ConsoleNotifier, Notification, Notifier
from touchorders_core.datastore.repositories import PlanRepository, WorkflowRepository
from touchorders_core.domain.common import utc_now, uuid7
from touchorders_core.domain.enums import MessageType, PlanState, WorkflowState, WorkflowStepState
from touchorders_core.domain.plans import ActionPlan
from touchorders_core.observability.audit import AuditLogger
from touchorders_core.observability.metrics import get_metrics
from touchorders_core.tools.base import NO_COMPENSATION, NOTIFY_CORRECTION, ToolContext
from touchorders_core.tools.executor import ToolExecutor
from touchorders_core.tools.registry import ToolRegistry
from touchorders_core.workflows.states import PLAN_TRANSITIONS, WORKFLOW_TRANSITIONS, execution_permitted


class OutcomePublisher(Protocol):
    def publish(self, *, type: MessageType, payload: dict[str, object], correlation_id: str, dedup_key: str) -> None: ...


@dataclass
class WorkflowOutcome:
    workflow_id: str
    state: WorkflowState
    completed_steps: list[int] = field(default_factory=list)
    failed_step: int | None = None
    compensated_steps: list[int] = field(default_factory=list)
    uncompensated_steps: list[int] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.state == WorkflowState.COMPLETED


class WorkflowEngine:
    def __init__(
        self,
        workflows: WorkflowRepository,
        plans: PlanRepository,
        executor: ToolExecutor,
        registry: ToolRegistry,
        audit: AuditLogger,
        *,
        publisher: OutcomePublisher | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        self._workflows, self._plans, self._executor = workflows, plans, executor
        self._registry, self._audit = registry, audit
        self._publisher = publisher
        self._notifier = notifier or ConsoleNotifier()
        self._metrics = get_metrics()

    def run_plan(self, plan: ActionPlan, ctx: ToolContext) -> WorkflowOutcome:
        if not execution_permitted(plan.state):
            raise PermissionError(f"Plan {plan.plan_id} is {plan.state}; execution requires a recorded approval (NFR-5).")

        workflow_id = str(uuid7())
        self._workflows.create(workflow_id=workflow_id, plan_id=plan.plan_id, template_name=None, correlation_id=plan.correlation_id, state=WorkflowState.PENDING)
        wf_state = WORKFLOW_TRANSITIONS.next(WorkflowState.PENDING, "start")
        self._workflows.update(workflow_id, state=wf_state)
        plan.state = PLAN_TRANSITIONS.next(plan.state, "start")
        self._plans.save(plan)
        self._audit.write(actor="system:workflow_engine", action="workflow.started", entity_type="workflow", entity_id=workflow_id, correlation_id=plan.correlation_id, payload={"plan_id": plan.plan_id})

        outcome = WorkflowOutcome(workflow_id=workflow_id, state=wf_state)
        completed: list[tuple[int, str, dict, dict]] = []  # (step_no, tool_name, arguments, output)

        for step in sorted(plan.steps, key=lambda s: s.step_no):
            idempotency_key = f"{workflow_id}:{step.step_no}"
            result = self._executor.execute(step.tool_name, step.arguments, ctx, idempotency_key=idempotency_key)
            self._workflows.step(workflow_id=workflow_id, step_no=step.step_no, state=_step_state(result.status), idempotency_key=idempotency_key, output=result.output)
            if result.ok or result.status == "SKIPPED_DUPLICATE":
                self._workflows.update(workflow_id, state=wf_state, current_step=step.step_no)
                if result.ok and result.output is not None:
                    completed.append((step.step_no, step.tool_name, dict(step.arguments), result.output))
                    outcome.completed_steps.append(step.step_no)
                continue
            outcome.failed_step = step.step_no
            return self._compensate(plan, ctx, workflow_id, completed, outcome, error=result.error or {})

        # all steps succeeded
        self._workflows.update(workflow_id, state=WORKFLOW_TRANSITIONS.next(wf_state, "complete"))
        plan.state = PLAN_TRANSITIONS.next(plan.state, "complete")
        self._plans.save(plan)
        outcome.state = WorkflowState.COMPLETED
        self._audit.write(actor="system:workflow_engine", action="workflow.completed", entity_type="workflow", entity_id=workflow_id, correlation_id=plan.correlation_id, payload={"steps": outcome.completed_steps})
        self._metrics.increment("workflows_total", outcome="completed")
        self._publish(MessageType.WORKFLOW_COMPLETED, {"workflow_id": workflow_id, "plan_id": plan.plan_id, "steps": outcome.completed_steps}, plan.correlation_id, f"workflow_completed:{workflow_id}")
        return outcome

    # -- saga compensation --------------------------------------------------------------------

    def _compensate(self, plan: ActionPlan, ctx: ToolContext, workflow_id: str, completed: list[tuple[int, str, dict, dict]], outcome: WorkflowOutcome, *, error: dict) -> WorkflowOutcome:
        self._workflows.update(workflow_id, state=WORKFLOW_TRANSITIONS.next(WorkflowState.EXECUTING, "fail"), failure=error)
        plan.state = PLAN_TRANSITIONS.next(plan.state, "fail")
        self._plans.save(plan)
        comp_state = WORKFLOW_TRANSITIONS.next(WorkflowState.FAILED, "compensate")
        self._workflows.update(workflow_id, state=comp_state)

        for step_no, tool_name, arguments, output in reversed(completed):
            tool = self._registry.get(tool_name)
            strategy = tool.definition.compensation
            if strategy == NO_COMPENSATION:
                continue
            if strategy == NOTIFY_CORRECTION:
                self._notifier.notify(Notification(kind="workflow.correction", entity_id=tool_name, summary=f"Irreversible step {step_no} ({tool_name}) needs a correction notice.", correlation_id=plan.correlation_id))
                outcome.compensated_steps.append(step_no)
                self._audit.write(actor="system:workflow_engine", action="workflow.compensated", entity_type="workflow", entity_id=workflow_id, correlation_id=plan.correlation_id, payload={"step": step_no, "strategy": "NOTIFY_CORRECTION"})
                continue
            comp_args = tool.compensation_args(tool.definition.input_model.model_validate(arguments), output) if tool.compensation_args else {}
            comp_result = self._executor.execute(strategy, comp_args, ctx, idempotency_key=f"{workflow_id}:comp:{step_no}")
            self._workflows.step(workflow_id=workflow_id, step_no=step_no, state=WorkflowStepState.COMPENSATED.value if comp_result.ok else WorkflowStepState.COMPENSATION_FAILED.value, idempotency_key=f"{workflow_id}:comp:{step_no}", output=comp_result.output, compensated=comp_result.ok)
            if comp_result.ok:
                outcome.compensated_steps.append(step_no)
            else:
                outcome.uncompensated_steps.append(step_no)

        if outcome.uncompensated_steps:
            final = WORKFLOW_TRANSITIONS.next(comp_state, "manual_cleanup")
            self._notifier.notify(Notification(kind="workflow.manual_cleanup", entity_id=workflow_id, summary=f"Compensation incomplete; manual cleanup required for steps {outcome.uncompensated_steps}.", correlation_id=plan.correlation_id))
        else:
            final = WORKFLOW_TRANSITIONS.next(comp_state, "complete")
        self._workflows.update(workflow_id, state=final)
        outcome.state = final
        self._notifier.notify(Notification(kind="workflow.failed", entity_id=workflow_id, summary=f"Workflow failed at step {outcome.failed_step}; {final}.", correlation_id=plan.correlation_id))
        self._audit.write(actor="system:workflow_engine", action="workflow.failed", entity_type="workflow", entity_id=workflow_id, correlation_id=plan.correlation_id, payload={"failed_step": outcome.failed_step, "final_state": final, "compensated": outcome.compensated_steps, "uncompensated": outcome.uncompensated_steps})
        self._metrics.increment("workflows_total", outcome="failed")
        self._publish(MessageType.WORKFLOW_FAILED, {"workflow_id": workflow_id, "plan_id": plan.plan_id, "failed_step": outcome.failed_step, "final_state": final, "uncompensated": outcome.uncompensated_steps}, plan.correlation_id, f"workflow_failed:{workflow_id}")
        return outcome

    def _publish(self, message_type: MessageType, payload: dict[str, object], correlation_id: str, dedup_key: str) -> None:
        if self._publisher is not None:
            self._publisher.publish(type=message_type, payload=payload, correlation_id=correlation_id, dedup_key=dedup_key)


def _step_state(status: str) -> str:
    return {
        "COMPLETED": WorkflowStepState.COMPLETED.value,
        "FAILED": WorkflowStepState.FAILED.value,
        "REJECTED": WorkflowStepState.FAILED.value,
        "SKIPPED_DUPLICATE": WorkflowStepState.SKIPPED_DUPLICATE.value,
    }.get(status, WorkflowStepState.FAILED.value)
