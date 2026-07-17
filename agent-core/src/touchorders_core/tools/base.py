"""Tool anatomy (§8.2) and the capability model's core types (A.5).

A tool is the ONLY mechanism by which model output becomes a real-world effect (P5). Each is a
deterministic Python callable with a strict Pydantic input/output contract, a risk tier, and —
for every non-READ tool — a declared compensation strategy. The model may name a tool and propose
arguments; deterministic code (the executor, §8.5) decides whether that proposal is valid.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel

from touchorders_core.approvals.notifier import ConsoleNotifier, Notifier
from touchorders_core.datastore.repositories import DomainRepository, WorkflowRepository
from touchorders_core.domain.common import utc_now
from touchorders_core.domain.enums import RiskTier, SideEffects

NOTIFY_CORRECTION = "NOTIFY_CORRECTION"
NO_COMPENSATION = "NONE"


class InvariantViolation(Exception):
    """A machine-checkable business precondition (G2) failed against live data."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class ToolContext:
    """Everything a deterministic tool may touch. Tools never reach further than this."""

    domain: DomainRepository
    workflows: WorkflowRepository | None = None
    notifier: Notifier = field(default_factory=ConsoleNotifier)
    correlation_id: str | None = None
    caller: str = "system"
    tenant_id: str = "default"
    now: datetime = field(default_factory=utc_now)
    # Optional launcher injected for execute_workflow, avoiding a tools -> workflows import cycle.
    launch_template: Callable[[str, dict[str, object]], str] | None = None


ToolHandler = Callable[[BaseModel, ToolContext], BaseModel]
Invariant = Callable[[BaseModel, ToolContext], None]
CompensationArgs = Callable[[BaseModel, dict[str, object]], dict[str, object]]


@dataclass(frozen=True)
class ToolDefinition:
    """Serializes to touchorders/tool-definition.v1 (A.5)."""

    name: str
    version: int
    description: str
    side_effects: SideEffects
    risk_tier: RiskTier
    idempotent: bool
    compensation: str  # registered tool name | NOTIFY_CORRECTION | NONE
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    invariant_codes: tuple[str, ...] = ()
    timeout_seconds: float = 15.0
    max_retries: int = 0
    precondition_max_age_seconds: int | None = None

    def metadata(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "side_effects": self.side_effects.value,
            "risk_tier": self.risk_tier.value,
            "idempotent": self.idempotent,
            "compensation": self.compensation,
            "invariants": list(self.invariant_codes),
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "precondition_max_age_seconds": self.precondition_max_age_seconds,
            "input_schema": self.input_model.model_json_schema(),
            "output_schema": self.output_model.model_json_schema(),
        }


@dataclass(frozen=True)
class RegisteredTool:
    definition: ToolDefinition
    handler: ToolHandler
    invariants: tuple[Invariant, ...] = ()
    compensation_args: CompensationArgs | None = None


def tool(
    *,
    name: str,
    version: int,
    description: str,
    side_effects: SideEffects,
    risk_tier: RiskTier,
    idempotent: bool,
    compensation: str = NO_COMPENSATION,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    invariants: tuple[tuple[str, Invariant], ...] = (),
    compensation_args: CompensationArgs | None = None,
    timeout_seconds: float = 15.0,
    max_retries: int = 0,
    precondition_max_age_seconds: int | None = None,
) -> Callable[[ToolHandler], RegisteredTool]:
    """Decorate a ``(args, ctx) -> output`` function into a :class:`RegisteredTool`."""

    def decorate(handler: ToolHandler) -> RegisteredTool:
        definition = ToolDefinition(
            name=name, version=version, description=description, side_effects=side_effects,
            risk_tier=risk_tier, idempotent=idempotent, compensation=compensation,
            input_model=input_model, output_model=output_model,
            invariant_codes=tuple(code for code, _ in invariants),
            timeout_seconds=timeout_seconds, max_retries=max_retries,
            precondition_max_age_seconds=precondition_max_age_seconds,
        )
        return RegisteredTool(
            definition=definition, handler=handler,
            invariants=tuple(check for _, check in invariants),
            compensation_args=compensation_args,
        )

    return decorate
