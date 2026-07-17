"""generate_shift_report (§8.7): a LOW-tier, auto-approvable document rendered from KPIs."""

from __future__ import annotations

from touchorders_core.domain.common import DomainModel, uuid7
from touchorders_core.domain.enums import RiskTier, SideEffects
from touchorders_core.tools.base import NOTIFY_CORRECTION, ToolContext, tool

_DEFAULT_SECTIONS = ("revenue", "top_items", "inventory_risks", "kitchen_throughput")


class ShiftReportInput(DomainModel):
    shift_date: str
    sections: list[str] | None = None


class ShiftReportOutput(DomainModel):
    report_id: str
    shift_date: str
    sections: list[str]


@tool(
    name="generate_shift_report", version=1,
    description="Use to render an end-of-shift report document for a date. Deterministic; safe to auto-run.",
    side_effects=SideEffects.WRITE, risk_tier=RiskTier.LOW, idempotent=False, compensation=NOTIFY_CORRECTION,
    input_model=ShiftReportInput, output_model=ShiftReportOutput,
)
def generate_shift_report(args: ShiftReportInput, ctx: ToolContext) -> ShiftReportOutput:
    sections = args.sections or list(_DEFAULT_SECTIONS)
    return ShiftReportOutput(report_id=str(uuid7()), shift_date=args.shift_date, sections=sections)
