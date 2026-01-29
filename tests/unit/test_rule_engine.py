from typing import Dict, Any, List

import pytest
from pydantic import BaseModel

from src.services.rule_engine import RuleEngine
from src.services.rules.base import RuleViolation, ValidationRule


class _DummyModel(BaseModel):
    value: int = 1


class _RuleA(ValidationRule):
    @property
    def name(self) -> str:
        return "RuleA"

    def check(self, config: BaseModel, schema: Dict[str, Any], build_config: Dict[str, str]) -> List[RuleViolation]:
        return [RuleViolation(rule_name=self.name, severity="warning", message="A")]


class _RuleB(ValidationRule):
    @property
    def name(self) -> str:
        return "RuleB"

    def check(self, config: BaseModel, schema: Dict[str, Any], build_config: Dict[str, str]) -> List[RuleViolation]:
        return [RuleViolation(rule_name=self.name, severity="error", message="B")]


def test_rule_engine_preserves_rule_order(monkeypatch) -> None:
    """PRD Amendment C; aligns with GraphState validation flow in src/models/graph_state_canonical.py."""
    from src.services import rules as rules_module

    registry = {"RuleA": _RuleA, "RuleB": _RuleB}
    monkeypatch.setattr(rules_module, "RULE_REGISTRY", registry, raising=False)

    class _SolverConfig:
        validation_rules = ["RuleA", "RuleB"]

    violations = RuleEngine.validate(_DummyModel(), _SolverConfig)
    assert [v.rule_name for v in violations] == ["RuleA", "RuleB"]


def test_rule_engine_skips_unknown_rules(monkeypatch) -> None:
    """Reviewer contract alignment: tests/contracts/reviewer_node_contract.json; unknown rules should not crash."""
    from src.services import rules as rules_module

    registry = {"RuleA": _RuleA}
    monkeypatch.setattr(rules_module, "RULE_REGISTRY", registry, raising=False)

    class _SolverConfig:
        validation_rules = ["RuleA", "MissingRule"]

    violations = RuleEngine.validate(_DummyModel(), _SolverConfig)
    assert [v.rule_name for v in violations] == ["RuleA"]
