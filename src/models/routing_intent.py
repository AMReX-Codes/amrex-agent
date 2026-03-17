"""Typed routing intent used to constrain solver/case selection."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RoutingIntent(BaseModel):
    """Prompt/reviewer-derived constraints for routing decisions."""

    explicit_solver: str | None = None
    explicit_case_path: str | None = None
    path_segments: list[str] = Field(default_factory=list)
    anchor_strength: Literal["none", "weak", "strong"] = "none"
    allowed_solvers: list[str] = Field(default_factory=list)
    forbidden_solvers: list[str] = Field(default_factory=list)
    preferred_path_patterns: list[str] = Field(default_factory=list)
    forbidden_path_patterns: list[str] = Field(default_factory=list)
    baseline_override_candidate: str | None = None
    conflict_policy: Literal["block_then_clarify", "penalize_only"] = "block_then_clarify"
    source_tags: list[str] = Field(default_factory=list)
    clarification_triggered: bool = False
    clarification_reason_code: str | None = None
