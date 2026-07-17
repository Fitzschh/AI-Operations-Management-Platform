"""Durable outbox backed by an in-process priority queue for low latency."""

from __future__ import annotations

import asyncio
from itertools import count

from touchorders_core.datastore.repositories import OperationalEventRepository
from touchorders_core.domain.enums import OperationalEventStatus
from touchorders_core.domain.events import OperationalEvent


class EventQueue:
    def __init__(self, repository: OperationalEventRepository) -> None:
        self._repository = repository
        self._queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
        self._counter = count()

    async def publish(self, event: OperationalEvent) -> None:
        self._repository.add(event)
        await self._queue.put((-event.severity.rank, next(self._counter), event.event_id))

    async def recover(self) -> None:
        for event in self._repository.queued():
            await self._queue.put((-event.severity.rank, next(self._counter), event.event_id))

    async def claim(self) -> OperationalEvent | None:
        while not self._queue.empty():
            _, _, event_id = await self._queue.get()
            for event in self._repository.queued(limit=500):
                if event.event_id == event_id:
                    self._repository.set_status(event_id, OperationalEventStatus.DISPATCHED, increment_attempts=True)
                    event.status = OperationalEventStatus.DISPATCHED
                    event.attempts += 1
                    return event
        return None

    def complete(self, event: OperationalEvent) -> None:
        self._repository.set_status(event.event_id, OperationalEventStatus.CONSUMED)

    def dead_letter(self, event: OperationalEvent) -> None:
        self._repository.set_status(event.event_id, OperationalEventStatus.DEAD_LETTER)
