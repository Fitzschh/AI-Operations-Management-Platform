"""Validated YAML rule-pack loader."""

from __future__ import annotations

from pathlib import Path

import yaml

from touchorders_core.rules_engine.models import Rule, RulePack


class RuleLoader:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._rules: dict[str, Rule] = {}

    def load(self) -> dict[str, Rule]:
        rules: dict[str, Rule] = {}
        for path in sorted(self._directory.glob("*.yaml")):
            pack = RulePack.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            for rule in pack.rules:
                if rule.rule_id in rules:
                    raise ValueError(f"Duplicate rule ID: {rule.rule_id}")
                rule.version = pack.version
                rules[rule.rule_id] = rule
        self._rules = rules
        return dict(rules)

    @property
    def rules(self) -> dict[str, Rule]:
        return dict(self._rules)
