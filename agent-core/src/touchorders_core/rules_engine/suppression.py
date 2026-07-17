"""Deterministic deduplication, cooldown, escalation, and hysteresis firewall."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from touchorders_core.datastore.repositories import RuleStateRepository
from touchorders_core.domain.common import utc_now
from touchorders_core.domain.enums import Severity
from touchorders_core.rules_engine.evaluators import compare
from touchorders_core.rules_engine.models import Rule


@dataclass(frozen=True)
class SuppressionDecision:
    emit: bool
    reason: str | None = None
    severity: Severity | None = None
    fingerprint: str | None = None


def fingerprint(rule_id: str, entity_id: str, severity: Severity) -> str:
    raw = f"{rule_id}|{entity_id}|{severity}".encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def bump_severity(severity: Severity) -> Severity:
    return {Severity.INFO: Severity.WARNING, Severity.WARNING: Severity.HIGH, Severity.HIGH: Severity.CRITICAL, Severity.CRITICAL: Severity.CRITICAL}[severity]


class Suppressor:
    def __init__(self, states: RuleStateRepository) -> None:
        self._states = states

    def decide(self, *, rule: Rule, entity_id: str, value: float, severity: Severity, tenant_id: str) -> SuppressionDecision:
        now = utc_now()
        state = self._states.get(rule.rule_id, entity_id, tenant_id)
        if rule.suppression.hysteresis and compare(value, rule.suppression.hysteresis.clear_when):
            self._states.save(rule_id=rule.rule_id, entity_id=entity_id, tenant_id=tenant_id, cooldown_until=None, active_fingerprint=None, fires_in_window=0, window_started_at=None, cleared=True)
            return SuppressionDecision(emit=False, reason="HYSTERESIS_CLEARED")
        active = state.active_fingerprint if state else None
        fires = state.fires_in_window if state else 0
        window_started = state.window_started_at if state else None
        in_cooldown = bool(state and state.cooldown_until and state.cooldown_until > now)
        if active and not (state.cleared if state else True):
            fires = fires + 1
            if in_cooldown and fires >= rule.suppression.escalation.fires_within_cooldown:
                severity = bump_severity(severity)
                event_fingerprint = fingerprint(rule.rule_id, entity_id, severity)
                self._states.save(rule_id=rule.rule_id, entity_id=entity_id, tenant_id=tenant_id, cooldown_until=now + timedelta(minutes=rule.suppression.cooldown_minutes), active_fingerprint=event_fingerprint, fires_in_window=0, window_started_at=now, cleared=False)
                return SuppressionDecision(emit=True, reason="ESCALATED", severity=severity, fingerprint=event_fingerprint)
            self._states.save(rule_id=rule.rule_id, entity_id=entity_id, tenant_id=tenant_id, cooldown_until=state.cooldown_until if state else None, active_fingerprint=active, fires_in_window=fires, window_started_at=window_started or now, cleared=False)
            return SuppressionDecision(emit=False, reason="SUPPRESSED_DUPLICATE")
        event_fingerprint = fingerprint(rule.rule_id, entity_id, severity)
        self._states.save(rule_id=rule.rule_id, entity_id=entity_id, tenant_id=tenant_id, cooldown_until=now + timedelta(minutes=rule.suppression.cooldown_minutes), active_fingerprint=event_fingerprint, fires_in_window=0, window_started_at=now, cleared=False)
        return SuppressionDecision(emit=True, severity=severity, fingerprint=event_fingerprint)
