"""Contract tests for canonical job status normalization."""

from __future__ import annotations

import pytest

from src.utils.job_status import CANONICAL_JOB_STATUSES, normalize_job_status


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("COMPLETED", "completed"),
        ("success", "completed"),
        ("ok", "completed"),
        ("succeeded", "completed"),
        ("DONE", "completed"),
        ("PENDING", "queued"),
        ("submitted", "queued"),
        ("RUNNING", "running"),
        ("CONFIGURING", "queued"),
        ("FAILED", "failed"),
        ("NODE_FAIL", "failed"),
        ("OUT_OF_MEMORY", "failed"),
        ("CANCELLED", "cancelled"),
        ("CANCELLED by 12345", "cancelled"),
        ("PREEMPTED", "cancelled"),
        ("TIMEOUT", "timeout"),
        ("skipped", "skipped"),
    ],
)
def test_normalize_job_status_aliases_to_canonical_set(raw: str, expected: str) -> None:
    normalized = normalize_job_status(raw)
    assert normalized == expected
    assert normalized in CANONICAL_JOB_STATUSES


def test_normalize_job_status_unknown_fallback() -> None:
    assert normalize_job_status("totally_new_state") == "unknown"
    assert normalize_job_status(None) == "unknown"
    assert normalize_job_status("") == "unknown"

