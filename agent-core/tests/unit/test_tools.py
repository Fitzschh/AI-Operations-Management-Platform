"""§8 tool layer: registry safety and the five validation gates."""

from __future__ import annotations

from decimal import Decimal

import pytest

from touchorders_core.domain.entities import InventoryItem, MenuItem
from touchorders_core.tools.base import ToolContext
from touchorders_core.tools.builtin import build_registry
from touchorders_core.tools.executor import ToolExecutor, ToolValidationError
from touchorders_core.tools.registry import ToolRegistryError


@pytest.fixture()
def registry():
    return build_registry()


@pytest.fixture()
def executor(registry, repos):
    return ToolExecutor(registry, repos.tool_invocations, repos.audit)


@pytest.fixture()
def ctx(repos):
    repos.domain.upsert_inventory(InventoryItem(sku="chicken", name="Chicken", quantity=8, reorder_threshold=20))
    repos.domain.upsert_menu_item(MenuItem(id="m1", name="Wings", price=Decimal("10"), available=True))
    return ToolContext(domain=repos.domain, workflows=repos.workflows, correlation_id="corr-1", caller="test")


def _po_args(**overrides):
    args = {"supplier_id": "supplier_main", "lines": [{"sku": "chicken", "quantity": 40}], "needed_by": "2026-07-18T00:00:00Z"}
    args.update(overrides)
    return args


def test_registry_validates_completeness_and_hides_read_tools_from_plan_enum(registry) -> None:
    effect_names = registry.effect_tool_names()
    assert "draft_purchase_order" in effect_names
    assert "get_inventory_status" not in effect_names  # READ tools are never planned as steps
    assert {s["function"]["name"] for s in registry.openai_read_tool_specs()} == {
        "get_inventory_status", "get_sales_summary", "get_active_workflows",
    }


def test_unregistered_tool_is_unrepresentable(registry) -> None:
    assert not registry.has("wire_money")
    with pytest.raises(ToolRegistryError):
        registry.get("wire_money")


def test_read_tool_executes_and_is_audited(executor, ctx, repos) -> None:
    result = executor.execute("get_inventory_status", {"item_ids": ["chicken"]}, ctx)
    assert result.ok
    assert result.output["items"][0]["below_threshold"] is True
    assert repos.audit.verify() is True


def test_g1_schema_gate_rejects_malformed_arguments(executor, ctx) -> None:
    result = executor.execute("draft_purchase_order", {"supplier_id": "supplier_main"}, ctx)  # missing lines/needed_by
    assert result.status == "REJECTED"
    assert result.error["errors"][0]["gate"] == "G1"


def test_g2_invariant_gate_blocks_negative_quantity_and_bad_supplier(executor, ctx) -> None:
    negative = executor.execute("draft_purchase_order", _po_args(lines=[{"sku": "chicken", "quantity": -5}]), ctx)
    assert negative.status == "REJECTED" and negative.error["errors"][0]["code"] == "IV-PO-1"

    bad_supplier = executor.execute("draft_purchase_order", _po_args(supplier_id="cash_only_bob"), ctx)
    assert bad_supplier.status == "REJECTED" and bad_supplier.error["errors"][0]["code"] == "IV-PO-2"


def test_g2_channel_allowlist_blocks_exfiltration(executor, ctx) -> None:
    result = executor.execute("send_notification", {"channel": "attacker.example.com", "audience": "x", "template_id": "t"}, ctx)
    assert result.status == "REJECTED" and result.error["errors"][0]["code"] == "IV-NOTIF-1"


def test_validate_raises_structured_errors_for_reprompt(executor, ctx) -> None:
    with pytest.raises(ToolValidationError) as exc:
        executor.validate("draft_purchase_order", _po_args(lines=[]), ctx)
    assert exc.value.errors[0]["code"] == "IV-PO-1"


def test_g5_idempotency_dedup_skips_a_repeated_effect(executor, ctx) -> None:
    first = executor.execute("generate_shift_report", {"shift_date": "2026-07-17"}, ctx)
    second = executor.execute("generate_shift_report", {"shift_date": "2026-07-17"}, ctx)
    assert first.ok
    assert second.status == "SKIPPED_DUPLICATE"


def test_happy_path_effect_produces_output(executor, ctx) -> None:
    result = executor.execute("draft_purchase_order", _po_args(), ctx)
    assert result.ok
    assert result.output["status"] == "DRAFT" and result.output["supplier_id"] == "supplier_main"
