"""Appendix C.3 workflow templates load and validate from config/."""

from __future__ import annotations

from pathlib import Path

import pytest

from touchorders_core.workflows.templates import TemplateLibrary, TemplateLoadError

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "workflows"


def test_shipped_templates_load_and_are_named() -> None:
    library = TemplateLibrary.from_directory(CONFIG_DIR)
    assert set(library.names()) == {"reorder_critical_stock", "rush_hour_protocol"}
    reorder = library.get("reorder_critical_stock")
    assert reorder.on_step_failure == "halt_and_compensate"
    assert [s.tool for s in reorder.steps] == ["generate_inventory_plan", "draft_purchase_order", "send_notification"]


def test_unknown_template_raises() -> None:
    library = TemplateLibrary.from_directory(CONFIG_DIR)
    with pytest.raises(TemplateLoadError):
        library.get("delete_everything")
