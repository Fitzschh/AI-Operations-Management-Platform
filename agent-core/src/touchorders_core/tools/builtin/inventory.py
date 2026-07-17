"""Inventory effect tools (§8.7). Quantities are computed by Python, never the model (ADR-9)."""

from __future__ import annotations

import math

from touchorders_core.domain.common import DomainModel, uuid7
from touchorders_core.domain.enums import RiskTier, SideEffects
from touchorders_core.tools.base import NOTIFY_CORRECTION, InvariantViolation, ToolContext, tool

# Approved-supplier allowlist (config in production, §8.7). The model can never introduce a new
# supplier: a value outside this set fails invariant IV-PO-2 before any draft is created.
APPROVED_SUPPLIERS = frozenset({"supplier_main", "supplier_backup"})


# -- generate_inventory_plan ------------------------------------------------------------------

class InventoryPlanInput(DomainModel):
    horizon_days: int
    item_scope: list[str]


class ReplenishmentLine(DomainModel):
    sku: str
    on_hand: float
    recommended_quantity: float


class InventoryPlanOutput(DomainModel):
    plan_id: str
    horizon_days: int
    lines: list[ReplenishmentLine]


def _iv_horizon_positive(args: InventoryPlanInput, _: ToolContext) -> None:
    if args.horizon_days <= 0:
        raise InvariantViolation("IV-PLAN-1", "horizon_days must be positive.")


@tool(
    name="generate_inventory_plan", version=1,
    description="Use to draft a replenishment plan for at-risk items over a horizon. Python computes the quantities from on-hand levels and reorder thresholds.",
    side_effects=SideEffects.WRITE, risk_tier=RiskTier.MEDIUM, idempotent=False, compensation=NOTIFY_CORRECTION,
    input_model=InventoryPlanInput, output_model=InventoryPlanOutput,
    invariants=(("IV-PLAN-1", _iv_horizon_positive),),
)
def generate_inventory_plan(args: InventoryPlanInput, ctx: ToolContext) -> InventoryPlanOutput:
    items = {i.sku: i for i in ctx.domain.list_inventory(item_ids=args.item_scope, tenant_id=ctx.tenant_id)}
    lines: list[ReplenishmentLine] = []
    for sku in args.item_scope:
        item = items.get(sku)
        if item is None:
            continue
        # Deterministic target: cover the horizon back up to twice the reorder threshold.
        target = item.reorder_threshold * 2
        recommended = max(0.0, math.ceil(target - item.quantity))
        lines.append(ReplenishmentLine(sku=sku, on_hand=item.quantity, recommended_quantity=recommended))
    return InventoryPlanOutput(plan_id=str(uuid7()), horizon_days=args.horizon_days, lines=lines)


# -- draft_purchase_order ---------------------------------------------------------------------

class PurchaseOrderLine(DomainModel):
    sku: str
    quantity: float


class PurchaseOrderInput(DomainModel):
    supplier_id: str
    lines: list[PurchaseOrderLine]
    needed_by: str


class PurchaseOrderOutput(DomainModel):
    po_id: str
    supplier_id: str
    status: str
    lines: list[PurchaseOrderLine]


def _iv_quantities_positive(args: PurchaseOrderInput, _: ToolContext) -> None:
    if not args.lines:
        raise InvariantViolation("IV-PO-1", "A purchase order must contain at least one line.")
    if any(line.quantity <= 0 for line in args.lines):
        raise InvariantViolation("IV-PO-1", "purchase-order line quantities must be greater than zero.")


def _iv_supplier_approved(args: PurchaseOrderInput, _: ToolContext) -> None:
    if args.supplier_id not in APPROVED_SUPPLIERS:
        raise InvariantViolation("IV-PO-2", f"supplier_id {args.supplier_id!r} is not an approved supplier.")


@tool(
    name="draft_purchase_order", version=1,
    description="Use to draft (never auto-send) a supplier purchase order for specific SKUs and quantities. Requires an approved supplier.",
    side_effects=SideEffects.WRITE, risk_tier=RiskTier.MEDIUM, idempotent=False,
    compensation="void_purchase_order_draft",
    input_model=PurchaseOrderInput, output_model=PurchaseOrderOutput,
    invariants=(("IV-PO-1", _iv_quantities_positive), ("IV-PO-2", _iv_supplier_approved)),
    compensation_args=lambda args, output: {"po_id": output["po_id"]},
)
def draft_purchase_order(args: PurchaseOrderInput, ctx: ToolContext) -> PurchaseOrderOutput:
    return PurchaseOrderOutput(po_id=str(uuid7()), supplier_id=args.supplier_id, status="DRAFT", lines=list(args.lines))


# -- void_purchase_order_draft (compensation) -------------------------------------------------

class VoidPurchaseOrderInput(DomainModel):
    po_id: str


class VoidPurchaseOrderOutput(DomainModel):
    po_id: str
    status: str


@tool(
    name="void_purchase_order_draft", version=1,
    description="Compensation: void a previously drafted purchase order.",
    side_effects=SideEffects.WRITE, risk_tier=RiskTier.MEDIUM, idempotent=True, compensation=NOTIFY_CORRECTION,
    input_model=VoidPurchaseOrderInput, output_model=VoidPurchaseOrderOutput,
)
def void_purchase_order_draft(args: VoidPurchaseOrderInput, ctx: ToolContext) -> VoidPurchaseOrderOutput:
    return VoidPurchaseOrderOutput(po_id=args.po_id, status="VOIDED")
