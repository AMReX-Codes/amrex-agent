"""Reviewer Service: Reviewer Orchestrator: Validation Result Model."""
from typing import Literal

from pydantic import BaseModel, Field

from src.services.rules.base import RuleViolation


ReviewerReasonCode = Literal[
    "intent_missing",
    "solver_mismatch",
    "baseline_path_mismatch",
    "domain_conflict",
    "schema_unresolved",
    "resource_conflict",
    "rate_limit_pressure",
]


class ValidationResult(BaseModel):
    """Result of plan validation."""

    mode: Literal["proceed", "retry", "fail", "terminal"]
    violations: list[RuleViolation]
    summary: str
    available_schema_params: list[str] = Field(default_factory=list)
    required_solver: str | None = None
    forbidden_path_patterns: list[str] = Field(default_factory=list)
    preferred_path_patterns: list[str] = Field(default_factory=list)
    excluded_cases: list[str] = Field(default_factory=list)
    schema_escalation_required: bool = False
    replan_reason_codes: list[ReviewerReasonCode] = Field(default_factory=list)
