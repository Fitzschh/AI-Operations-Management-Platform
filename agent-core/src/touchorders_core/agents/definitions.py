"""AgentDefinition loading (§3.2, Appendix C.2).

An agent is fully described by one declarative definition plus a context builder and a
post-validator. Adding an agent is registration, not new control flow (§19.1): the loader turns
YAML + a prompt file into an :class:`AgentDefinition`, and :func:`build_gateway_config` derives the
gateway's per-agent call config from the same source.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from touchorders_core.domain.enums import AgentName
from touchorders_core.domain.incidents import IncidentReportOutput
from touchorders_core.domain.plans import ActionPlanOutput
from touchorders_core.domain.reports import BusinessReportOutput
from touchorders_core.llm.budget import DailyBudget
from touchorders_core.llm.gateway import AgentCallConfig

# Schema id (Appendix A) -> the Pydantic output contract the agent must satisfy.
OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "touchorders/incident-report.v1": IncidentReportOutput,
    "touchorders/business-report.v1": BusinessReportOutput,
    "touchorders/action-plan.v1": ActionPlanOutput,
}


@dataclass(frozen=True)
class AgentDefinition:
    name: AgentName
    model: str
    temperature: float
    max_output_tokens: int
    context_budget_tokens: int
    daily_budget: DailyBudget
    prompt_version: str
    system_prompt: str
    output_schema: type[BaseModel]
    tools_read: tuple[str, ...]
    read_tool_max_rounds: int
    debounce_seconds: int

    def call_config(self) -> AgentCallConfig:
        return AgentCallConfig(
            model=self.model, temperature=self.temperature, max_output_tokens=self.max_output_tokens,
            prompt_version=self.prompt_version, system_prompt=self.system_prompt,
            read_tool_max_rounds=max(1, self.read_tool_max_rounds),
        )


def _load_prompt(config_dir: Path, ref: str) -> tuple[str, str]:
    # ref looks like "prompts/operations_manager@v1"
    rel, _, _version = ref.partition("@")
    name = rel.split("/", 1)[-1]
    text = (config_dir / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    return ref, text


def load_agent_definition(path: Path, config_dir: Path) -> AgentDefinition:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    budget = data["daily_token_budget"]
    prompt_version, system_prompt = _load_prompt(config_dir, data["system_prompt_ref"])
    return AgentDefinition(
        name=AgentName(data["agent"]),
        model=data["model"],
        temperature=float(data["temperature"]),
        max_output_tokens=int(data["max_output_tokens"]),
        context_budget_tokens=int(data["context_budget_tokens"]),
        daily_budget=DailyBudget(input=int(budget["input"]), output=int(budget["output"])),
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        output_schema=OUTPUT_SCHEMAS[data["output_schema"]],
        tools_read=tuple(data.get("tools_read", [])),
        read_tool_max_rounds=int(data.get("read_tool_max_rounds", 0)),
        debounce_seconds=int(data.get("debounce_seconds", 0)),
    )


def load_agent_definitions(config_dir: str | Path) -> dict[AgentName, AgentDefinition]:
    config_dir = Path(config_dir)
    definitions: dict[AgentName, AgentDefinition] = {}
    for path in sorted((config_dir / "agents").glob("*.yaml")):
        definition = load_agent_definition(path, config_dir)
        definitions[definition.name] = definition
    return definitions


def build_gateway_config(definitions: dict[AgentName, AgentDefinition]) -> dict[AgentName, AgentCallConfig]:
    return {name: definition.call_config() for name, definition in definitions.items()}


def build_daily_budgets(definitions: dict[AgentName, AgentDefinition]) -> dict[AgentName, DailyBudget]:
    return {name: definition.daily_budget for name, definition in definitions.items()}
