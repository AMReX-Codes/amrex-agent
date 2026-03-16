"""Canonical job status normalization utilities."""

from __future__ import annotations

from typing import Any

CANONICAL_JOB_STATUSES = frozenset(
    {
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
        "timeout",
        "skipped",
        "unknown",
    }
)


_ALIASES: dict[str, str] = {
    "ok": "completed",
    "success": "completed",
    "succeeded": "completed",
    "done": "completed",
    "completing": "completed",
    "pending": "queued",
    "submitted": "queued",
    "configuring": "queued",
    "cancelled by": "cancelled",
    "canceled": "cancelled",
    "preempted": "cancelled",
    "boot_fail": "failed",
    "deadline": "failed",
    "error": "failed",
    "node_fail": "failed",
    "out_of_memory": "failed",
    "unstable": "failed",
}


def normalize_job_status(status: Any, *, default: str = "unknown") -> str:
    """Normalize arbitrary status values to the canonical lowercase set."""
    if not isinstance(status, str):
        return default

    value = status.strip().lower()
    if not value:
        return default
    if value in CANONICAL_JOB_STATUSES:
        return value
    if value.startswith("cancelled by"):
        return "cancelled"
    return _ALIASES.get(value, default)

