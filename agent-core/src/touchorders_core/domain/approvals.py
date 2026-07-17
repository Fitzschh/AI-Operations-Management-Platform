"""Approval request contract. Human identity enforcement happens in the service."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from touchorders_core.domain.common import DomainModel, uuid7, utc_now
from touchorders_core.domain.enums import ApprovalState


class ApprovalRequest(DomainModel):
    approval_id: str = Field(default_factory=lambda: str(uuid7()))
    plan_id: str
    state: ApprovalState = ApprovalState.PENDING
    expires_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
