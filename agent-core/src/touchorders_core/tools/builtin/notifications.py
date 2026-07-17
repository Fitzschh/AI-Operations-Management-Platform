"""send_notification (§8.7): the only external-send tool, hard-bounded by a channel allowlist.

The model can never introduce a new destination (anti-exfiltration, §15.3): an out-of-allowlist
channel fails invariant IV-NOTIF-1 before anything is sent.
"""

from __future__ import annotations

from touchorders_core.approvals.notifier import Notification
from touchorders_core.domain.common import DomainModel, uuid7
from touchorders_core.domain.enums import RiskTier, SideEffects
from touchorders_core.tools.base import NOTIFY_CORRECTION, InvariantViolation, ToolContext, tool

ALLOWED_CHANNELS = frozenset({"staff_ops", "kitchen", "front_of_house", "manager_broadcast"})


class NotificationInput(DomainModel):
    channel: str
    audience: str
    template_id: str
    variables: dict[str, str] = {}


class NotificationOutput(DomainModel):
    channel: str
    delivered: bool
    receipt: str


def _iv_channel_allowed(args: NotificationInput, _: ToolContext) -> None:
    if args.channel not in ALLOWED_CHANNELS:
        raise InvariantViolation("IV-NOTIF-1", f"channel {args.channel!r} is not on the allowlist.")


@tool(
    name="send_notification", version=1,
    description="Use to notify staff via an allowlisted channel using a named template. Cannot send free-form text or to arbitrary destinations.",
    side_effects=SideEffects.EXTERNAL, risk_tier=RiskTier.LOW, idempotent=False, compensation=NOTIFY_CORRECTION,
    input_model=NotificationInput, output_model=NotificationOutput,
    invariants=(("IV-NOTIF-1", _iv_channel_allowed),),
)
def send_notification(args: NotificationInput, ctx: ToolContext) -> NotificationOutput:
    receipt = str(uuid7())
    ctx.notifier.notify(Notification(
        kind="staff.notification", entity_id=args.template_id, summary=f"[{args.channel}] {args.template_id}",
        correlation_id=ctx.correlation_id, audience=args.audience,
    ))
    return NotificationOutput(channel=args.channel, delivered=True, receipt=receipt)
