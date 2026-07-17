"""READ-tier query tools (§8.7). Side-effect-free; auto-executable; offered as OpenAI functions.

These let the Operations Manager fill information gaps during planning without a second agent
invocation. All arithmetic here is deterministic Python — the model reads results, never computes.
"""

from __future__ import annotations

from datetime import timedelta

from touchorders_core.domain.common import DomainModel
from touchorders_core.domain.enums import RiskTier, SideEffects
from touchorders_core.tools.base import NO_COMPENSATION, ToolContext, tool


# -- get_inventory_status ---------------------------------------------------------------------

class InventoryStatusInput(DomainModel):
    item_ids: list[str] | None = None
    category: str | None = None


class InventoryLevel(DomainModel):
    sku: str
    name: str
    quantity: float
    reorder_threshold: float
    below_threshold: bool


class InventoryStatusOutput(DomainModel):
    items: list[InventoryLevel]


@tool(
    name="get_inventory_status", version=1,
    description="Use to read current stock levels for items or a category. Returns per-item quantity, reorder threshold, and whether it is below threshold.",
    side_effects=SideEffects.READ, risk_tier=RiskTier.LOW, idempotent=True, compensation=NO_COMPENSATION,
    input_model=InventoryStatusInput, output_model=InventoryStatusOutput,
)
def get_inventory_status(args: InventoryStatusInput, ctx: ToolContext) -> InventoryStatusOutput:
    items = ctx.domain.list_inventory(item_ids=args.item_ids, category=args.category, tenant_id=ctx.tenant_id)
    return InventoryStatusOutput(items=[
        InventoryLevel(sku=i.sku, name=i.name, quantity=i.quantity, reorder_threshold=i.reorder_threshold, below_threshold=i.quantity < i.reorder_threshold)
        for i in items
    ])


# -- get_sales_summary ------------------------------------------------------------------------

class SalesSummaryInput(DomainModel):
    period: str  # HOUR | DAY | WEEK
    granularity: str | None = None


class SalesSummaryOutput(DomainModel):
    period: str
    total_revenue: float
    sale_count: int


_PERIODS = {"HOUR": timedelta(hours=1), "DAY": timedelta(days=1), "WEEK": timedelta(weeks=1)}


@tool(
    name="get_sales_summary", version=1,
    description="Use to read revenue and sale counts for the last hour, day, or week. Returns deterministic totals from the sales ledger.",
    side_effects=SideEffects.READ, risk_tier=RiskTier.LOW, idempotent=True, compensation=NO_COMPENSATION,
    input_model=SalesSummaryInput, output_model=SalesSummaryOutput,
)
def get_sales_summary(args: SalesSummaryInput, ctx: ToolContext) -> SalesSummaryOutput:
    window = _PERIODS.get(args.period.upper(), _PERIODS["DAY"])
    sales = ctx.domain.sales_between(ctx.now - window, ctx.now, tenant_id=ctx.tenant_id)
    total = float(sum(s.amount for s in sales))
    return SalesSummaryOutput(period=args.period.upper(), total_revenue=round(total, 2), sale_count=len(sales))


# -- get_active_workflows ---------------------------------------------------------------------

class ActiveWorkflowsInput(DomainModel):
    states: list[str] | None = None


class ActiveWorkflowsOutput(DomainModel):
    workflows: list[dict[str, object]]


@tool(
    name="get_active_workflows", version=1,
    description="Use to see running or pending workflows before proposing another, to avoid duplicate action.",
    side_effects=SideEffects.READ, risk_tier=RiskTier.LOW, idempotent=True, compensation=NO_COMPENSATION,
    input_model=ActiveWorkflowsInput, output_model=ActiveWorkflowsOutput,
)
def get_active_workflows(args: ActiveWorkflowsInput, ctx: ToolContext) -> ActiveWorkflowsOutput:
    active = ctx.workflows.active() if ctx.workflows else []
    if args.states:
        wanted = {s.upper() for s in args.states}
        active = [w for w in active if str(w.get("state")).upper() in wanted]
    return ActiveWorkflowsOutput(workflows=active)
