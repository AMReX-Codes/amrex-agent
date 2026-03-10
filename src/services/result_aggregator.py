"""Result aggregation utilities for sweep workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.sweep_schemas import ChildJobStatus, ChildWorkflowState, ParentSweepState


def aggregate_results(parent: ParentSweepState, output_dir: Path) -> dict[str, Any]:
    """
    Build sweep_summary.json from ParentSweepState.
    Write to output_dir/sweep_summary.json.
    Return summary dict.

    status logic:
      all completed -> "completed"
      all failed    -> "failed"
      mixed         -> "partial"

    aggregated_metrics: computed from completed children only.
    Failed children excluded.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    total_count = len(parent.children)
    completed_count = sum(1 for child in parent.children if child.status == ChildJobStatus.completed)
    failed_count = sum(1 for child in parent.children if child.status == ChildJobStatus.failed)

    if total_count > 0 and completed_count == total_count:
        overall_status = "completed"
    elif total_count > 0 and failed_count == total_count:
        overall_status = "failed"
    else:
        overall_status = "partial"

    summary: dict[str, Any] = {
        "sweep_id": parent.sweep_id,
        "sweep_type": parent.sweep_spec.sweep_type.value,
        "parameter": parent.sweep_spec.parameter_name,
        "total_count": total_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "status": overall_status,
        "children": [_child_summary_entry(child) for child in parent.children],
        "aggregated_metrics": _aggregate_child_metrics(parent.children),
    }

    summary_path = output_dir / "sweep_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _aggregate_child_metrics(children: list[ChildWorkflowState]) -> dict[str, dict[str, float | int]]:
    """
    Compute mean/min/max of numeric metric fields
    across completed children only.
    Returns empty dict if no completed children
    or no metrics available.
    """
    metric_values: dict[str, list[float]] = {}

    for child in children:
        if child.status != ChildJobStatus.completed:
            continue
        for key, value in _extract_metrics(child).items():
            metric_values.setdefault(key, []).append(float(value))

    aggregated: dict[str, dict[str, float | int]] = {}
    for key, values in metric_values.items():
        if not values:
            continue
        aggregated[key] = {
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }

    return aggregated


def _child_summary_entry(child: ChildWorkflowState) -> dict[str, Any]:
    """
    Build per-child dict for summary["children"].
    Always include: child_id, parameter_value,
    status, failure_reason.
    """
    return {
        "child_id": child.sweep_child_id,
        "parameter_value": child.parameter_value,
        "status": child.status.value,
        "failure_reason": child.failure_reason,
        "result_metrics": _extract_metrics(child),
    }


def _extract_metrics(child: ChildWorkflowState) -> dict[str, float]:
    """Extract numeric metrics from child result summary."""
    payload = child.result_summary or {}
    candidate = payload.get("result_metrics", payload) if isinstance(payload, dict) else {}
    if not isinstance(candidate, dict):
        return {}

    numeric_metrics: dict[str, float] = {}
    for key, value in candidate.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            numeric_metrics[key] = float(value)
    return numeric_metrics

