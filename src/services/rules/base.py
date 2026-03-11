"""
Input Writer: Rule Factory: Rule Base Class.

Minimal implementation for TDD green phase.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass
class RuleViolation:
    """Represents a validation rule violation."""

    rule_name: str
    severity: str  # "error", "warning", "info"
    message: str
    parameter: str | None = None
    suggested_fix: str | None = None
    auto_correctable: bool = False
    tier: str = ""
    category: str = ""

    def __post_init__(self) -> None:
        """Populate canonical tier/category fields when omitted."""
        if not self.tier:
            self.tier = self._infer_tier(self.severity)
        if not self.category:
            self.category = self.rule_name

    @staticmethod
    def _infer_tier(severity: str) -> str:
        """Map severity to deterministic validation tier."""
        normalized = severity.lower()
        if normalized in {"critical", "error"}:
            return "tier1"
        if normalized == "warning":
            return "tier2"
        if normalized == "info":
            return "tier3"
        return "tier4"


class ValidationRule(ABC):
    """Base class for all validation rules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Rule identifier.

        Returns
        -------
        str
            Rule name.
        """
        pass

    @abstractmethod
    def check(
        self,
        config: BaseModel,
        schema: dict[str, Any],
        build_config: dict[str, str]
    ) -> list[RuleViolation]:
        """
        Check configuration against this rule.

        Parameters
        ----------
        config : BaseModel
            Config model to validate.
        schema : dict
            Schema dictionary for available fields.
        build_config : dict
            Build flags for dependency checks.

        Returns
        -------
        list of RuleViolation
            Violations found by the rule.
        """
        pass

    def auto_correct(
        self,
        config: BaseModel,
        violation: RuleViolation
    ) -> BaseModel:
        """
        Attempt to auto-correct a violation.

        Parameters
        ----------
        config : BaseModel
            Config model to update.
        violation : RuleViolation
            Violation to correct.

        Returns
        -------
        BaseModel
            Updated config model.
        """
        raise NotImplementedError(f"Rule {self.name} does not support auto-correction")
