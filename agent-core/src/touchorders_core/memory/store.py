"""Namespaced agent memory (§9.1). Each agent sees only its own namespace.

Agents touch memory only through a :class:`MemoryStore` bound to their name — an agent MUST NOT
read another agent's namespace (§9.1). Cross-agent knowledge flows through Coordinator messages,
not shared memory.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from touchorders_core.datastore.repositories import MemoryRepository
from touchorders_core.domain.enums import AgentName


class MemoryStore:
    def __init__(self, repository: MemoryRepository, agent: AgentName) -> None:
        self._repository = repository
        self._agent = agent

    def remember(self, *, kind: str, key: str, payload: dict[str, Any], summary: str, expires_at: datetime | None = None, correlation_id: str | None = None) -> None:
        self._repository.upsert(agent=self._agent, kind=kind, key=key, payload=payload, summary=summary[:240], expires_at=expires_at, correlation_id=correlation_id)

    def recall(self, *, kinds: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
        return self._repository.recall(agent=self._agent, kinds=kinds, limit=limit)
