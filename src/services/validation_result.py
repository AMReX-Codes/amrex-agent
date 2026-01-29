"""Reviewer Service: Reviewer Orchestrator: Validation Result Model."""
from typing import Literal

from pydantic import BaseModel, Field

from src.services.rules.base import RuleViolation


class ValidationResult(BaseModel):
    """Result of plan validation."""

    mode: Literal["proceed", "retry", "fail", "terminal"]
    violations: list[RuleViolation]
    summary: str
    available_schema_params: list[str] = Field(default_factory=list)
