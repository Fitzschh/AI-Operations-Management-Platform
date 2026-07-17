"""Typed, durable coordinator message envelope."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from touchorders_core.domain.common import DomainModel, uuid7, utc_now
from touchorders_core.domain.enums import MessageType


class AgentMessage(DomainModel):
    message_id: str = Field(default_factory=lambda: str(uuid7()))
    type: MessageType
    payload: dict[str, object]
    correlation_id: str
    created_at: datetime = Field(default_factory=utc_now)
    dedup_key: str
