"""Tool Registry (§8.3): the closed, validated action space.

The model can never emit an unregistered tool name — effect tools appear only as an enum inside
the ActionPlan output schema, and READ tools only as OpenAI function specs. Both are derived here
from the registered set, so an unknown name fails schema validation at the gateway, never at
execution (P5).
"""

from __future__ import annotations

from touchorders_core.domain.enums import RiskTier, SideEffects
from touchorders_core.tools.base import NO_COMPENSATION, RegisteredTool


class ToolRegistryError(RuntimeError):
    """Raised at startup when the registry is incomplete or inconsistent."""


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        name = tool.definition.name
        if name in self._tools:
            raise ToolRegistryError(f"Tool {name!r} is already registered.")
        self._tools[name] = tool

    def get(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolRegistryError(f"Unknown tool {name!r}.") from exc

    def has(self, name: str) -> bool:
        return name in self._tools

    def list(self, *, risk_tier: RiskTier | None = None, side_effects: SideEffects | None = None) -> list[RegisteredTool]:
        tools = list(self._tools.values())
        if risk_tier is not None:
            tools = [t for t in tools if t.definition.risk_tier == risk_tier]
        if side_effects is not None:
            tools = [t for t in tools if t.definition.side_effects == side_effects]
        return sorted(tools, key=lambda t: t.definition.name)

    def read_tools(self) -> list[RegisteredTool]:
        return self.list(side_effects=SideEffects.READ)

    def effect_tool_names(self) -> list[str]:
        """The enum injected into the ActionPlan step schema (WRITE/EXTERNAL only, §8.3/§8.4)."""
        return sorted(
            t.definition.name for t in self._tools.values()
            if t.definition.side_effects != SideEffects.READ
        )

    def catalog(self) -> list[dict[str, object]]:
        """Registry rendering for ``GET /api/v1/tools`` and audit review."""
        return [t.definition.metadata() for t in self.list()]

    def openai_read_tool_specs(self) -> list[dict[str, object]]:
        """READ tools as OpenAI function-calling specs (native calling, §8.4)."""
        specs: list[dict[str, object]] = []
        for tool in self.read_tools():
            definition = tool.definition
            specs.append({
                "type": "function",
                "function": {
                    "name": definition.name,
                    "description": definition.description,
                    "parameters": definition.input_model.model_json_schema(),
                },
            })
        return specs

    def validate_completeness(self) -> None:
        """Startup gate (§8.2): every non-READ tool declares a resolvable compensation strategy."""
        errors: list[str] = []
        for tool in self._tools.values():
            definition = tool.definition
            if definition.side_effects == SideEffects.READ:
                if definition.compensation != NO_COMPENSATION:
                    errors.append(f"{definition.name}: READ tools must declare compensation NONE.")
                continue
            compensation = definition.compensation
            if compensation == NO_COMPENSATION:
                errors.append(f"{definition.name}: non-READ tool must declare a compensation strategy.")
            elif compensation not in {"NOTIFY_CORRECTION"} and compensation not in self._tools:
                errors.append(f"{definition.name}: compensation {compensation!r} is not a registered tool.")
        if errors:
            raise ToolRegistryError("Tool registry failed completeness validation: " + "; ".join(errors))
