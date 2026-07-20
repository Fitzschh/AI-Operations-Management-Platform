"""§14 LLM Gateway: structured outputs, cache, numeric-echo (A-4), budget, circuit breaker."""

from __future__ import annotations

import pytest
from pydantic import Field
from sqlalchemy import select

from touchorders_core.datastore.orm import LLMCallRow
from touchorders_core.domain.common import DomainModel
from touchorders_core.domain.enums import AgentName
from touchorders_core.llm.budget import BudgetExceeded, BudgetTracker, DailyBudget, LLMUnavailable
from touchorders_core.llm.cache import ResponseCache
from touchorders_core.llm.gateway import AgentCallConfig, FakeLLMClient, LLMGateway, OutputRejected

AGENT = AgentName.REALTIME_ANALYST


class Evidence(DomainModel):
    metric: str
    value: float
    source_event_id: str


class AnalysisOutput(DomainModel):
    """Local test schema; the gateway is agnostic to the concrete output contract."""

    title: str = Field(max_length=80)
    summary: str
    evidence: list[Evidence] = Field(min_length=1)


def _config() -> dict[AgentName, AgentCallConfig]:
    return {AGENT: AgentCallConfig(model="fake-gpt-5.6", temperature=0.1, max_output_tokens=800, prompt_version="realtime@v1", system_prompt="You are a test analyst.")}


def _bundle(remaining: float = 14.0) -> dict:
    return {"event": {"metrics": {"remaining_units": remaining, "threshold": 20.0}}, "entity": {"id": "sku-chicken"}}


def _analysis(value: float = 14.0) -> dict:
    return {
        "title": "Low chicken stock",
        "summary": "Chicken stock is below threshold before the dinner rush.",
        "evidence": [{"metric": "remaining_units", "value": value, "source_event_id": "evt-1"}],
    }


def _gateway(repos, client, *, budget=None, cache=None) -> LLMGateway:
    return LLMGateway(_config(), client, repos.llm_calls, repos.audit, cache=cache or ResponseCache(), budget=budget or BudgetTracker(_generous()))


def _generous():
    return {AGENT: DailyBudget(input=1_000_000, output=1_000_000)}


def _ledger_rows(repos) -> list[LLMCallRow]:
    with repos.factory() as session:
        return list(session.scalars(select(LLMCallRow)).all())


def test_structured_call_returns_validated_output_and_writes_ledger(repos) -> None:
    client = FakeLLMClient()
    client.register("realtime_incident", _analysis(), input_tokens=1600, output_tokens=450)
    result = _gateway(repos, client).structured_call(agent=AGENT, purpose="realtime_incident", bundle=_bundle(), output_schema=AnalysisOutput)

    assert isinstance(result.output, AnalysisOutput)
    assert result.output.evidence[0].value == 14.0
    rows = _ledger_rows(repos)
    assert len(rows) == 1 and rows[0].outcome == "SUCCESS" and rows[0].input_tokens == 1600


def test_identical_bundle_is_served_from_cache_for_zero_tokens(repos) -> None:
    client = FakeLLMClient()
    client.register("realtime_incident", _analysis())
    gateway = _gateway(repos, client)

    first = gateway.structured_call(agent=AGENT, purpose="realtime_incident", bundle=_bundle(), output_schema=AnalysisOutput)
    second = gateway.structured_call(agent=AGENT, purpose="realtime_incident", bundle=_bundle(), output_schema=AnalysisOutput)

    assert first.cached is False and second.cached is True
    assert second.input_tokens == 0 and second.output_tokens == 0
    outcomes = sorted(r.outcome for r in _ledger_rows(repos))
    assert outcomes == ["CACHE_HIT", "SUCCESS"]


def test_numeric_echo_violation_is_rejected(repos) -> None:
    client = FakeLLMClient()
    client.register("realtime_incident", _analysis(value=999.0))  # 999 is not in the bundle
    with pytest.raises(OutputRejected):
        _gateway(repos, client).structured_call(agent=AGENT, purpose="realtime_incident", bundle=_bundle(), output_schema=AnalysisOutput)
    assert _ledger_rows(repos)[0].outcome == "REJECTED"


def test_corrective_reprompt_recovers_a_bad_first_response(repos) -> None:
    client = FakeLLMClient()
    client.register("realtime_incident", _analysis(value=999.0))  # first: bad echo
    client.register("realtime_incident", _analysis(value=14.0))   # re-prompt: corrected
    result = _gateway(repos, client).structured_call(agent=AGENT, purpose="realtime_incident", bundle=_bundle(), output_schema=AnalysisOutput)
    assert result.output.evidence[0].value == 14.0


def test_budget_exhaustion_raises_before_calling_the_model(repos) -> None:
    client = FakeLLMClient()
    # Echo the constant threshold (20.0) so varying the bundle to defeat the cache keeps echo valid.
    client.register("realtime_incident", _analysis(value=20.0), input_tokens=1000, output_tokens=300)
    budget = BudgetTracker({AGENT: DailyBudget(input=1500, output=400)})
    gateway = _gateway(repos, client, budget=budget)

    gateway.structured_call(agent=AGENT, purpose="realtime_incident", bundle=_bundle(1.0), output_schema=AnalysisOutput)
    gateway.structured_call(agent=AGENT, purpose="realtime_incident", bundle=_bundle(2.0), output_schema=AnalysisOutput)
    with pytest.raises(BudgetExceeded):
        gateway.structured_call(agent=AGENT, purpose="realtime_incident", bundle=_bundle(3.0), output_schema=AnalysisOutput)


def test_circuit_breaker_opens_after_consecutive_transport_failures(repos) -> None:
    class _Failing:
        def complete(self, **_):
            raise RuntimeError("provider 503")

    budget = BudgetTracker(_generous(), failure_threshold=3, cooldown_seconds=999)
    gateway = _gateway(repos, _Failing(), budget=budget)

    for nonce in range(3):
        with pytest.raises(RuntimeError):
            gateway.structured_call(agent=AGENT, purpose="realtime_incident", bundle=_bundle(float(nonce)), output_schema=AnalysisOutput)
    with pytest.raises(LLMUnavailable):
        gateway.structured_call(agent=AGENT, purpose="realtime_incident", bundle=_bundle(99.0), output_schema=AnalysisOutput)
    assert gateway.budget_status(AGENT).circuit_open is True
