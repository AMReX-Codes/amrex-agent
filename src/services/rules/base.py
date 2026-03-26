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
    tier: str | None = None
    category: str | None = None

    def __post_init__(self) -> None:
        """Normalize and backfill taxonomy fields for consistent error payloads."""
        normalized_severity = (self.severity or "error").strip().lower()
        self.severity = normalized_severity if normalized_severity else "error"

        if not self.tier:
            self.tier = self._infer_tier(self.severity)

        if not self.category:
            self.category = self._infer_category(self.parameter)

    @staticmethod
    def _infer_tier(severity: str) -> str:
        """Map severity levels to processing tiers."""
        return {
            "critical": "tier1",
            "error": "tier1",
            "warning": "tier2",
            "info": "tier3",
        }.get((severity or "").lower(), "tier2")

    @staticmethod
    def _infer_category(parameter: str | None) -> str:
        """Derive a coarse category from parameter namespace."""
        if not parameter:
            return "System & Resources"

        param_lower = parameter.lower()

        if any(x in param_lower for x in ("plot", "check", "derived", "plot_int", "io.")):
            return "I/O"
        if any(x in param_lower for x in ("particles.", "eb2.", "eb_", "spray.")):
            return "Particles & EB"
        if any(x in param_lower for x in ("cfl", "stop_time", "dt", "solver", "physics")):
            return "Physics & Solver"
        if any(x in param_lower for x in ("amr.", "geometry.", "prob_lo", "prob_hi", "n_cell", "coord_sys")):
            return "Grid & Geometry"

        return "General"


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
