"""execute_workflow (§8.7): launch a named declarative template.

Kept out of the tools -> workflows import graph: the actual launcher is injected via
ToolContext.launch_template (wired at the composition root), so this module depends only on the
domain. HIGH tier: always human-approved.
"""

from __future__ import annotations

from touchorders_core.domain.common import DomainModel, uuid7
from touchorders_core.domain.enums import RiskTier, SideEffects
from touchorders_core.tools.base import NOTIFY_CORRECTION, InvariantViolation, ToolContext, tool


class ExecuteWorkflowInput(DomainModel):
    template_name: str
    parameters: dict[str, str] = {}


class ExecuteWorkflowOutput(DomainModel):
    workflow_id: str
    template_name: str
    status: str


def _iv_template_named(args: ExecuteWorkflowInput, _: ToolContext) -> None:
    if not args.template_name:
        raise InvariantViolation("IV-WF-1", "template_name is required.")


@tool(
    name="execute_workflow", version=1,
    description="Use to launch a pre-approved declarative workflow template by name with parameters. High-risk: always requires human approval.",
    side_effects=SideEffects.EXTERNAL, risk_tier=RiskTier.HIGH, idempotent=False, compensation=NOTIFY_CORRECTION,
    input_model=ExecuteWorkflowInput, output_model=ExecuteWorkflowOutput,
    invariants=(("IV-WF-1", _iv_template_named),),
)
def execute_workflow(args: ExecuteWorkflowInput, ctx: ToolContext) -> ExecuteWorkflowOutput:
    if ctx.launch_template is not None:
        workflow_id = ctx.launch_template(args.template_name, dict(args.parameters))
        return ExecuteWorkflowOutput(workflow_id=workflow_id, template_name=args.template_name, status="LAUNCHED")
    return ExecuteWorkflowOutput(workflow_id=str(uuid7()), template_name=args.template_name, status="SCHEDULED")
