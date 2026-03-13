"""
Typed visualization intent contract.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class VisualizationPlotSpec(BaseModel):
    """Optional explicit render request for a single plot."""

    type: str = "slice"
    field: str
    axis: str | None = None


class VisualizationIntent(BaseModel):
    """
    Canonical visualization intent shared across planning, writing, and rendering.
    """

    requested_fields: list[str] = Field(default_factory=list)
    cadence_prompt_seconds: int | None = None
    cadence_solver_time: float | None = None
    timestep_scope: Literal["latest", "all"] = "latest"
    plots: list[VisualizationPlotSpec] = Field(default_factory=list)
    solver_name: str | None = None
    source: Literal["prompt", "clarification", "default"] = "default"
    adjustments: list[str] = Field(default_factory=list)

    # Compatibility carrier for current writer/renderer logic.
    visualization_config: dict[str, Any] = Field(default_factory=dict)
