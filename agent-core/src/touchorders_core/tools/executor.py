"""Tool Executor (§8.5): five validation gates, sandboxed execution, ledger + audit.

Every effect passes G1 schema -> G2 invariants -> G3 policy -> G4 approval -> G5 runtime. G3/G4
are structural: effect tools are only reachable from an APPROVED plan via the Workflow Engine
(NFR-5), so they cannot be executed here without a recorded decision. This module owns G1, G2,
and G5, and is the single place any tool actually runs.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from touchorders_core.datastore.repositories import ToolInvocationRepository
from touchorders_core.observability.audit import AuditLogger, canonical_json
from touchorders_core.observability.metrics import get_metrics
from touchorders_core.domain.common import uuid7
from touchorders_core.domain.enums import SideEffects
from touchorders_core.tools.base import InvariantViolation, RegisteredTool, ToolContext
from touchorders_core.tools.registry import ToolRegistry


class ToolValidationError(Exception):
    """G1/G2 failure carrying machine-readable errors for the single manager re-prompt (§8.6)."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("; ".join(f"{e['code']}: {e['message']}" for e in errors))
        self.errors = errors


@dataclass(frozen=True)
class ToolResult:
    status: str  # COMPLETED | FAILED | REJECTED | SKIPPED_DUPLICATE
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.status == "COMPLETED"


def _args_hash(tool: RegisteredTool, arguments: dict[str, Any], idempotency_key: str | None = None) -> str:
    # Include the idempotency key so dedup is per-step (exactly-once, NFR-6): retrying the same
    # workflow step dedups, but the same tool+args in a different step/workflow does not collide.
    material = f"{tool.definition.name}|{tool.definition.version}|{canonical_json(arguments)}|{idempotency_key or ''}"
    return hashlib.sha256(material.encode()).hexdigest()


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, invocations: ToolInvocationRepository, audit: AuditLogger) -> None:
        self._registry = registry
        self._invocations = invocations
        self._audit = audit
        self._metrics = get_metrics()

    def validate(self, tool_name: str, arguments: dict[str, Any], ctx: ToolContext) -> BaseModel:
        """G1 (schema) + G2 (invariants) only. Raises ToolValidationError with structured errors."""
        tool = self._registry.get(tool_name)
        try:
            args = tool.definition.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolValidationError([
                {"gate": "G1", "code": "SCHEMA", "loc": list(err["loc"]), "message": err["msg"]}
                for err in exc.errors()
            ]) from exc
        try:
            for invariant in tool.invariants:
                invariant(args, ctx)
        except InvariantViolation as exc:
            raise ToolValidationError([{"gate": "G2", "code": exc.code, "message": exc.message}]) from exc
        return args

    def execute(self, tool_name: str, arguments: dict[str, Any], ctx: ToolContext, *, idempotency_key: str | None = None) -> ToolResult:
        tool = self._registry.get(tool_name)
        args_hash = _args_hash(tool, arguments, idempotency_key)

        # G1 + G2
        try:
            args = self.validate(tool_name, arguments, ctx)
        except ToolValidationError as exc:
            self._record(tool, args_hash, ctx, status="REJECTED", output={"errors": exc.errors})
            return ToolResult(status="REJECTED", error={"type": "VALIDATION", "errors": exc.errors})

        # G5 runtime: idempotency dedup for non-idempotent effect tools
        if not tool.definition.idempotent and self._invocations.seen(args_hash):
            self._record(tool, args_hash, ctx, status="SKIPPED_DUPLICATE", output=None)
            return ToolResult(status="SKIPPED_DUPLICATE")

        # G5 runtime: sandboxed execution
        started = time.perf_counter()
        try:
            output_model = tool.handler(args, ctx)
            output = output_model.model_dump(mode="json") if isinstance(output_model, BaseModel) else dict(output_model)
        except Exception as exc:  # noqa: BLE001 - a tool exception fails a step, never a loop
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._record(tool, args_hash, ctx, status="FAILED", output=None, duration_ms=duration_ms)
            self._metrics.increment("tool_invocations_total", tool=tool.definition.name, status="FAILED")
            return ToolResult(status="FAILED", error={"type": type(exc).__name__, "message": str(exc), "retryable": False})

        duration_ms = int((time.perf_counter() - started) * 1000)
        self._record(tool, args_hash, ctx, status="COMPLETED", output=output, duration_ms=duration_ms)
        self._metrics.increment("tool_invocations_total", tool=tool.definition.name, status="COMPLETED")
        return ToolResult(status="COMPLETED", output=output)

    def _record(self, tool: RegisteredTool, args_hash: str, ctx: ToolContext, *, status: str, output: dict[str, Any] | None, duration_ms: int = 0) -> None:
        invocation_id = str(uuid7())
        self._invocations.add(
            invocation_id=invocation_id, tool_name=tool.definition.name, tool_version=tool.definition.version,
            caller=ctx.caller, args_hash=args_hash, status=status, duration_ms=duration_ms,
            output=output, correlation_id=ctx.correlation_id,
        )
        self._audit.write(
            actor="system:tool_executor", action="tool.executed", entity_type="tool", entity_id=tool.definition.name,
            correlation_id=ctx.correlation_id,
            payload={"invocation_id": invocation_id, "status": status, "args_hash": args_hash, "side_effects": tool.definition.side_effects.value},
        )
