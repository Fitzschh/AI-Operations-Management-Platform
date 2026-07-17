"""Operations Manager plan post-validation (§8.3, §10.6).

Enriches each proposed step with its registered tool version and risk tier, and computes
``requires_approval`` from those tiers — never from model output (A.4 runtime attaches it). The HIGH
tier floor means any HIGH step forces human approval regardless of policy.
"""

from __future__ import annotations

from touchorders_core.domain.enums import RiskTier
from touchorders_core.domain.plans import ActionPlanOutput, PlanStep
from touchorders_core.tools.registry import ToolRegistry


class UnknownToolError(ValueError):
    pass


def enrich_steps(output: ActionPlanOutput, registry: ToolRegistry) -> list[PlanStep]:
    enriched: list[PlanStep] = []
    for step in output.steps:
        if not registry.has(step.tool_name):
            raise UnknownToolError(f"Plan references unregistered tool {step.tool_name!r}.")
        definition = registry.get(step.tool_name).definition
        enriched.append(step.model_copy(update={"tool_version": definition.version, "risk_tier": definition.risk_tier}))
    return enriched


def requires_approval(steps: list[PlanStep]) -> bool:
    """True unless every step is LOW-risk (§10.6 auto-approval is all-LOW only)."""
    return any((step.risk_tier or RiskTier.HIGH) != RiskTier.LOW for step in steps)
