"""Menu availability effect tool (HIGH tier) and its state-restoring compensation (§8.7, §10.5)."""

from __future__ import annotations

from touchorders_core.domain.common import DomainModel
from touchorders_core.domain.enums import RiskTier, SideEffects
from touchorders_core.tools.base import NOTIFY_CORRECTION, InvariantViolation, ToolContext, tool


class MenuAvailabilityInput(DomainModel):
    menu_item_id: str
    available: bool
    reason: str


class MenuAvailabilityOutput(DomainModel):
    menu_item_id: str
    previous_available: bool
    new_available: bool


def _iv_menu_item_exists(args: MenuAvailabilityInput, ctx: ToolContext) -> None:
    if ctx.domain.get_menu_item(args.menu_item_id, tenant_id=ctx.tenant_id) is None:
        raise InvariantViolation("IV-MENU-1", f"menu_item_id {args.menu_item_id!r} does not exist.")


@tool(
    name="set_menu_item_availability", version=1,
    description="Use to 86 (make unavailable) or restore a menu item. High-risk: always requires human approval.",
    side_effects=SideEffects.WRITE, risk_tier=RiskTier.HIGH, idempotent=False,
    compensation="restore_menu_item_availability",
    input_model=MenuAvailabilityInput, output_model=MenuAvailabilityOutput,
    invariants=(("IV-MENU-1", _iv_menu_item_exists),),
    compensation_args=lambda args, output: {"menu_item_id": output["menu_item_id"], "available": output["previous_available"]},
)
def set_menu_item_availability(args: MenuAvailabilityInput, ctx: ToolContext) -> MenuAvailabilityOutput:
    previous = ctx.domain.set_menu_availability(args.menu_item_id, args.available, tenant_id=ctx.tenant_id)
    if previous is None:  # defensive: invariant already checked existence
        raise RuntimeError(f"menu item {args.menu_item_id!r} vanished during execution")
    return MenuAvailabilityOutput(menu_item_id=args.menu_item_id, previous_available=previous, new_available=args.available)


class RestoreMenuInput(DomainModel):
    menu_item_id: str
    available: bool


class RestoreMenuOutput(DomainModel):
    menu_item_id: str
    restored_to: bool


@tool(
    name="restore_menu_item_availability", version=1,
    description="Compensation: restore a menu item to its previously captured availability.",
    side_effects=SideEffects.WRITE, risk_tier=RiskTier.HIGH, idempotent=True, compensation=NOTIFY_CORRECTION,
    input_model=RestoreMenuInput, output_model=RestoreMenuOutput,
)
def restore_menu_item_availability(args: RestoreMenuInput, ctx: ToolContext) -> RestoreMenuOutput:
    ctx.domain.set_menu_availability(args.menu_item_id, args.available, tenant_id=ctx.tenant_id)
    return RestoreMenuOutput(menu_item_id=args.menu_item_id, restored_to=args.available)
