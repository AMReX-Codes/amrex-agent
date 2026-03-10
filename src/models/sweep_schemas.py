"""Pydantic schemas and validation helpers for sweep workflows."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class SweepType(str, Enum):
    execution = "execution"
    physics = "physics"
    resolution = "resolution"


class ChildJobStatus(str, Enum):
    pending = "pending"
    submitted = "submitted"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


VALID_TRANSITIONS = {
    "pending": {"submitted", "cancelled"},
    "submitted": {"running", "failed", "cancelled"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def validate_transition(current: ChildJobStatus, next: ChildJobStatus) -> bool:
    """Return True if the ChildJobStatus transition is valid."""
    return next.value in VALID_TRANSITIONS[current.value]


class SweepSpec(BaseModel):
    sweep_type: SweepType
    parameter_name: str
    parameter_values: list[Any] = Field(min_length=2)
    sweep_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChildWorkflowState(BaseModel):
    sweep_id: str
    sweep_child_id: str
    parameter_name: str
    parameter_value: Any
    status: ChildJobStatus = ChildJobStatus.pending
    failure_reason: Optional[str] = None
    result_summary: Optional[dict[str, Any]] = None


class ParentSweepState(BaseModel):
    sweep_id: str
    sweep_spec: SweepSpec
    children: list[ChildWorkflowState] = Field(default_factory=list)
    total_count: int = 0
    completed_count: int = 0
    failed_count: int = 0

    @model_validator(mode="after")
    def validate_counts(self) -> "ParentSweepState":
        """Ensure completed + failed does not exceed total."""
        if self.completed_count + self.failed_count > self.total_count:
            raise ValueError("completed_count + failed_count must be <= total_count")
        return self
