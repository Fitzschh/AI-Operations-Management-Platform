"""Human-facing notification fan-out for the approval lifecycle (§10.2).

Channels are pluggable behind ``Notifier``; adding Slack/SMS/WebSocket is registration, not a
core change (§19.5). The default composite writes to the structured log so a hackathon run is
observable with zero external wiring, and ``CollectingNotifier`` gives tests a delivery record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from touchorders_core.domain.common import utc_now
from touchorders_core.observability.logging import get_logger


@dataclass(frozen=True)
class Notification:
    kind: str  # approval.requested | approval.reminder | approval.decided | plan.expired ...
    entity_id: str
    summary: str
    correlation_id: str | None = None
    audience: str = "manager"


class Notifier(Protocol):
    def notify(self, notification: Notification) -> None: ...


class ConsoleNotifier:
    """Structured-log channel; always safe, always available (dev default)."""

    def __init__(self) -> None:
        self._logger = get_logger("approvals.notifier")

    def notify(self, notification: Notification) -> None:
        self._logger.info(
            "notification",
            kind=notification.kind,
            entity_id=notification.entity_id,
            audience=notification.audience,
            summary=notification.summary,
            correlation_id=notification.correlation_id,
        )


@dataclass
class CollectingNotifier:
    """Test/double channel that records deliveries in order."""

    delivered: list[Notification] = field(default_factory=list)

    def notify(self, notification: Notification) -> None:
        self.delivered.append(notification)


class CompositeNotifier:
    """Fan-out to every configured channel; one channel failing never blocks the others."""

    def __init__(self, channels: list[Notifier]) -> None:
        self._channels = channels
        self._logger = get_logger("approvals.notifier")

    def notify(self, notification: Notification) -> None:
        for channel in self._channels:
            try:
                channel.notify(notification)
            except Exception:  # noqa: BLE001 - a broken channel must not stall approvals
                self._logger.warning(
                    "notification_channel_failed",
                    channel=type(channel).__name__,
                    kind=notification.kind,
                    at=utc_now().isoformat(),
                )
