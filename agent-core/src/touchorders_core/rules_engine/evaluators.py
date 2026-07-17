"""Pure comparison evaluators for declarative rule packs."""

from __future__ import annotations

import operator
import re

from touchorders_core.rules_engine.models import Rule


_COMPARATORS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "==": operator.eq}
_CONDITION = re.compile(r"^\s*(<=|>=|==|<|>)\s*(-?\d+(?:\.\d+)?)\s*$")


def compare(value: float, condition: str) -> bool:
    match = _CONDITION.match(condition)
    if not match:
        raise ValueError(f"Unsupported deterministic condition: {condition}")
    return _COMPARATORS[match.group(1)](value, float(match.group(2)))


def evaluate(rule: Rule, value: float) -> bool:
    if rule.evaluator in {"threshold", "delta_pct", "rate"}:
        if rule.operator is None or rule.value is None:
            raise ValueError(f"Rule {rule.rule_id} requires operator and value.")
        return _COMPARATORS[rule.operator](value, rule.value)
    raise ValueError(f"Evaluator {rule.evaluator} requires a deterministic composite/scheduled caller.")


def severity_for(rule: Rule, value: float) -> object:
    matches = [band.severity for band in rule.severity_bands if compare(value, band.when)]
    if not matches:
        return None
    return max(matches, key=lambda severity: severity.rank)
