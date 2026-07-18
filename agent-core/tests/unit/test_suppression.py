"""§7.4 suppression firewall exercised across a DB round-trip.

Regression guard: rule state is persisted, so the cooldown comparison happens against a datetime
read back from SQLite. That value must be timezone-aware (UTCDateTime) or the comparison raises.
"""

from __future__ import annotations

from touchorders_core.domain.enums import IncidentCategory, Severity
from touchorders_core.rules_engine.models import Rule, SeverityBand
from touchorders_core.rules_engine.suppression import Suppressor


def _rule() -> Rule:
    return Rule(
        rule_id="inventory.low_stock", category=IncidentCategory.INVENTORY_RISK, evaluator="threshold",
        metric="inventory.remaining_units", operator="<", value=20,
        severity_bands=[SeverityBand(when="< 20", severity=Severity.WARNING), SeverityBand(when="< 10", severity=Severity.HIGH)],
    )


def _decide(sup: Suppressor, rule: Rule):
    return sup.decide(rule=rule, entity_id="chicken", value=8.0, severity=Severity.HIGH, tenant_id="default")


def test_first_fire_emits_then_duplicate_is_suppressed(repos) -> None:
    sup = Suppressor(repos.rule_state)
    rule = _rule()

    first = _decide(sup, rule)
    assert first.emit is True and first.fingerprint is not None

    # This second call reads cooldown_until back from the DB and compares it to now — the exact
    # aware/naive comparison that used to raise TypeError.
    second = _decide(sup, rule)
    assert second.emit is False and second.reason == "SUPPRESSED_DUPLICATE"


def test_escalation_bypasses_suppression_after_repeated_fires(repos) -> None:
    sup = Suppressor(repos.rule_state)
    rule = _rule()

    _decide(sup, rule)        # emit (fingerprint armed)
    _decide(sup, rule)        # fires_in_window -> 1, suppressed
    _decide(sup, rule)        # fires_in_window -> 2, suppressed
    escalated = _decide(sup, rule)  # 3rd suppressed fire in cooldown -> escalate

    assert escalated.emit is True and escalated.reason == "ESCALATED"
    assert escalated.severity == Severity.CRITICAL  # HIGH bumped one band
