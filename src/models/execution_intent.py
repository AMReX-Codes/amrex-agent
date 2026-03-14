"""
Typed execution intent contract.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ExecutionIntent(BaseModel):
    """Canonical execution/runtime intent shared across parsing and runner."""

    environment: Literal["local", "perlmutter", "mcp"] | None = None
    run_mode: Literal["dry", "stage", "submit", "full"] | None = None
    total_procs: int | None = None
    walltime: str | None = None
    qos: str | None = None
    constraint: str | None = None
    account: str | None = None
    system: str | None = None
    source: Literal["prompt", "clarification", "default"] = "default"
    adjustments: list[str] = Field(default_factory=list)
    execution_config: dict[str, Any] = Field(default_factory=dict)
