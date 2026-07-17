"""Built-in tool catalog registration (§8.7)."""

from __future__ import annotations

from touchorders_core.tools.builtin.inventory import draft_purchase_order, generate_inventory_plan, void_purchase_order_draft
from touchorders_core.tools.builtin.menu import restore_menu_item_availability, set_menu_item_availability
from touchorders_core.tools.builtin.notifications import send_notification
from touchorders_core.tools.builtin.queries import get_active_workflows, get_inventory_status, get_sales_summary
from touchorders_core.tools.builtin.reporting import generate_shift_report
from touchorders_core.tools.builtin.workflows import execute_workflow
from touchorders_core.tools.registry import ToolRegistry

BUILTIN_TOOLS = (
    get_inventory_status, get_sales_summary, get_active_workflows,
    generate_inventory_plan, draft_purchase_order, void_purchase_order_draft,
    set_menu_item_availability, restore_menu_item_availability,
    generate_shift_report, send_notification, execute_workflow,
)


def build_registry() -> ToolRegistry:
    """Return a fresh registry with the built-in catalog registered and validated (§8.2)."""

    registry = ToolRegistry()
    for tool in BUILTIN_TOOLS:
        registry.register(tool)
    registry.validate_completeness()
    return registry


__all__ = ["BUILTIN_TOOLS", "build_registry"]
