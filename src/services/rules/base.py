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
