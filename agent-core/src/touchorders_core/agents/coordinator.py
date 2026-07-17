"""Agent Coordinator (§3.7): the deterministic typed message bus.

Agents never call each other — all inter-agent communication is a typed, durable message on the
``agent_messages`` inbox, of which the Coordinator is the single writer (§2.4). It coalesces pending
incident reports into one manager triage, and applies the deterministic relevance filter that keeps
informational business reports from waking the manager (token discipline).
"""

from __future__ import annotations

from collections.abc import Iterable

from touchorders_core.datastore.repositories import MessageRepository
from touchorders_core.domain.enums import MessageType, RiskTier
from touchorders_core.domain.messages import AgentMessage
from touchorders_core.domain.reports import BusinessReport

_TRIAGE_TYPES = {
    MessageType.INCIDENT_REPORT_READY,
    MessageType.BUSINESS_REPORT_RELEVANT,
    MessageType.APPROVAL_DECIDED,
    MessageType.WORKFLOW_COMPLETED,
    MessageType.WORKFLOW_FAILED,
    MessageType.PLAN_EXPIRED,
}


class Coordinator:
    def __init__(self, messages: MessageRepository) -> None:
        self._messages = messages

    def publish(self, *, type: MessageType, payload: dict[str, object], correlation_id: str, dedup_key: str) -> bool:
        """Single-writer entry point for every coordinator message (also OutcomePublisher)."""
        return self._messages.publish(AgentMessage(type=type, payload=payload, correlation_id=correlation_id, dedup_key=dedup_key))

    def pending(self, limit: int = 100) -> list[AgentMessage]:
        return self._messages.pending(limit)

    def consume(self, message_ids: Iterable[str]) -> None:
        self._messages.consume(message_ids)

    def drain_triage(self) -> tuple[list[str], list[str], list[AgentMessage]]:
        """Coalesce pending manager-bound messages into one triage set.

        Returns (incident_ids, consumed_message_ids, all_triage_messages). Incident-report messages
        merge into a single set; the caller loads the incidents and invokes the manager once.
        """
        messages = [m for m in self._messages.pending() if MessageType(m.type) in _TRIAGE_TYPES]
        incident_ids: list[str] = []
        for message in messages:
            if MessageType(message.type) == MessageType.INCIDENT_REPORT_READY:
                incident_id = message.payload.get("incident_id")
                if isinstance(incident_id, str) and incident_id not in incident_ids:
                    incident_ids.append(incident_id)
        return incident_ids, [m.message_id for m in messages], messages

    @staticmethod
    def business_report_relevant(report: BusinessReport) -> bool:
        """§3.4 relevance filter: only a HIGH recommendation or an actionable risk wakes the manager."""
        high_recommendation = any(rec.priority == RiskTier.HIGH for rec in report.recommendations)
        actionable_risk = any(risk.actionable for risk in report.risks)
        return high_recommendation or actionable_risk
