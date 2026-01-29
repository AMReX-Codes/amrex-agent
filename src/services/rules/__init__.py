"""
Input Writer: Rule Factory: Rule Factory.

Minimal implementation for TDD.
"""

from .base import RuleViolation, ValidationRule
from .common import BuildFlagDependencyRule, GridConsistencyRule, TimestepBoundsRule

# Physics Consistency Rules (Reviewer Service: Physics Validator) - Import BEFORE registry
from .physics import BoundaryConditionRule, CFLStabilityRule, GeometryDomainRule
from .schema_existence import SchemaExistenceRule

RULE_REGISTRY: dict[str, type[ValidationRule]] = {
    "SchemaExistence": SchemaExistenceRule,
    "BuildFlagDependency": BuildFlagDependencyRule,
    "GridConsistency": GridConsistencyRule,
    "TimestepBounds": TimestepBoundsRule,
    "CFLStabilityRule": CFLStabilityRule,
}


class RuleFactory:
    """Factory for creating validation rules."""

    @staticmethod
    def create(rule_name: str) -> ValidationRule:
        """
        Create a rule instance by name.

        Parameters
        ----------
        rule_name : str
            Registered rule name.

        Returns
        -------
        ValidationRule
            Instantiated rule.
        """
        if rule_name not in RULE_REGISTRY:
            raise KeyError(f"Unknown rule: '{rule_name}'")

        rule_class = RULE_REGISTRY[rule_name]
        return rule_class()


__all__ = [
    'ValidationRule',
    'RuleViolation',
    'RuleFactory',
    'SchemaExistenceRule',
    'BuildFlagDependencyRule',
    'GridConsistencyRule',
    'TimestepBoundsRule',
    'CFLStabilityRule',
    'BoundaryConditionRule',
    'GeometryDomainRule',
    'RULE_REGISTRY',
]
