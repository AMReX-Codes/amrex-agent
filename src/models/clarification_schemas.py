"""Schemas for clarification questions and history records."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ClarificationQuestion(BaseModel):
    field_name: Optional[str]
    question_text: str
    decision_level: int  # 1-6
    fallback_tier: str  # 'report'|'amrex_generic'|'faiss'|'free_text'
    context: dict = Field(default_factory=dict)


class ClarificationRecord(BaseModel):
    question: ClarificationQuestion
    answer: Optional[str] = None
    answered_by: str = "pending"  # 'human'|'ai_agent'|'pending'
    resolved_value: Optional[Any] = None
    turn: int = 0
