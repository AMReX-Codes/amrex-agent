"""Schema for persisted gate approval events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GateApprovalRecord(BaseModel):
    gate_id: str
    gate_type: str
    decision: str
    interface_path: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    details: dict[str, Any] = Field(default_factory=dict)
