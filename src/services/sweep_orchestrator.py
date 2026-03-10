"""Core sweep orchestration utilities (B2b)."""

from __future__ import annotations

import time
from typing import Any

from src.models.sweep_schemas import (
    ChildJobStatus,
    ChildWorkflowState,
    ParentSweepState,
    SweepSpec,
    SweepType,
    validate_transition,
)

_TERMINAL_STATUSES = {
    ChildJobStatus.completed,
    ChildJobStatus.failed,
    ChildJobStatus.cancelled,
}


def _coerce_status(raw: Any) -> ChildJobStatus | None:
    """Normalize status from enum/string/dict payloads."""
    candidate = raw.get("status") if isinstance(raw, dict) else raw
    if isinstance(candidate, ChildJobStatus):
        return candidate
    if isinstance(candidate, str):
        normalized = candidate.strip().lower()
        try:
            return ChildJobStatus(normalized)
        except ValueError:
            return None
    return None


def _extract_failure_reason(raw: Any) -> str | None:
    """Read failure reason from poll/submit payload when present."""
    if isinstance(raw, dict):
        reason = raw.get("failure_reason") or raw.get("error")
        return str(reason) if reason else None
    return None


def _is_terminal(status: ChildJobStatus) -> bool:
    return status in _TERMINAL_STATUSES


def _is_complete(parent: ParentSweepState) -> bool:
    return all(_is_terminal(child.status) for child in parent.children)


def _advance_status(child: ChildWorkflowState, target: ChildJobStatus) -> bool:
    """Advance status, including valid intermediary hops when poll skips states."""
    if validate_transition(child.status, target):
        child.status = target
        return True

    bridge_paths: dict[tuple[ChildJobStatus, ChildJobStatus], list[ChildJobStatus]] = {
        (ChildJobStatus.pending, ChildJobStatus.running): [ChildJobStatus.submitted, ChildJobStatus.running],
        (ChildJobStatus.pending, ChildJobStatus.completed): [
            ChildJobStatus.submitted,
            ChildJobStatus.running,
            ChildJobStatus.completed,
        ],
        (ChildJobStatus.pending, ChildJobStatus.failed): [ChildJobStatus.submitted, ChildJobStatus.failed],
        (ChildJobStatus.submitted, ChildJobStatus.completed): [ChildJobStatus.running, ChildJobStatus.completed],
    }
    path = bridge_paths.get((child.status, target))
    if not path:
        return False

    for step in path:
        if not validate_transition(child.status, step):
            return False
        child.status = step
    return True


def orchestrate_sweep(
    spec: SweepSpec,
    state: dict,
    config,
    architect_fn,
    reviewer_fn,
    submit_fn,
    poll_fn,
) -> ParentSweepState | None:
    """
    B2b Orchestrator core.
    Fan-out, child creation, polling loop.
    All external calls go through injectable fns.
    """
    if not getattr(config, "enable_sweep_orchestration", False):
        submit_fn(state, None)
        return None

    children = _create_children(spec)
    parent = ParentSweepState(
        sweep_id=spec.sweep_id,
        sweep_spec=spec,
        children=children,
        total_count=len(children),
    )

    base_plan = _run_architect_phase(spec, state, architect_fn)
    for child in parent.children:
        plan = base_plan
        if spec.sweep_type == SweepType.physics:
            plan = _run_reviewer_phase(child, base_plan, reviewer_fn)

        submit_result = submit_fn(child, plan)
        submit_status = _coerce_status(submit_result) or ChildJobStatus.submitted
        update_parent_state(
            parent,
            child.sweep_child_id,
            submit_status,
            failure_reason=_extract_failure_reason(submit_result),
        )

    return _poll_until_complete(parent, poll_fn)


def _create_children(
    spec: SweepSpec,
) -> list[ChildWorkflowState]:
    """Create N ChildWorkflowState from SweepSpec."""
    children: list[ChildWorkflowState] = []
    for idx, value in enumerate(spec.parameter_values):
        children.append(
            ChildWorkflowState(
                sweep_id=spec.sweep_id,
                sweep_child_id=f"{spec.sweep_id}-child-{idx}",
                parameter_name=spec.parameter_name,
                parameter_value=value,
            )
        )
    return children


def _run_architect_phase(
    spec: SweepSpec,
    state: dict,
    architect_fn,
) -> dict:
    """
    execution/physics: architect runs once.
    Returns base plan dict.
    """
    if spec.sweep_type not in {SweepType.execution, SweepType.physics}:
        return {}
    result = architect_fn(spec, state)
    return result if isinstance(result, dict) else {}


def _run_reviewer_phase(
    child: ChildWorkflowState,
    plan: dict,
    reviewer_fn,
) -> dict:
    """
    physics sweep: reviewer per child.
    Returns reviewed plan for this child.
    """
    reviewed = reviewer_fn(child, plan)
    return reviewed if isinstance(reviewed, dict) else plan


def poll_child_status(child: ChildWorkflowState, poll_fn) -> ChildWorkflowState:
    """Poll one child and apply status transition if valid."""
    if _is_terminal(child.status):
        return child

    poll_result = poll_fn(child)
    polled_status = _coerce_status(poll_result)
    if not polled_status or not _advance_status(child, polled_status):
        return child

    if child.status == ChildJobStatus.failed:
        child.failure_reason = _extract_failure_reason(poll_result)
    return child


def _poll_until_complete(
    parent: ParentSweepState,
    poll_fn,
    timeout_seconds: int = 3600,
) -> ParentSweepState:
    """
    Poll all children until terminal state.
    Uses validate_transition to guard updates.
    """
    deadline = time.monotonic() + timeout_seconds

    while not _is_complete(parent):
        if time.monotonic() >= deadline:
            for child in parent.children:
                if not _is_terminal(child.status):
                    update_parent_state(
                        parent,
                        child.sweep_child_id,
                        ChildJobStatus.failed,
                        failure_reason="poll timeout",
                    )
            break

        for child in parent.children:
            if _is_terminal(child.status):
                continue
            previous_status = child.status
            poll_child_status(child, poll_fn)
            if child.status != previous_status:
                update_parent_state(
                    parent,
                    child.sweep_child_id,
                    child.status,
                    failure_reason=child.failure_reason,
                )

        if not _is_complete(parent):
            time.sleep(0.01)

    return parent


def update_parent_state(
    parent: ParentSweepState,
    child_id: str,
    new_status: ChildJobStatus,
    failure_reason: str | None = None,
) -> ParentSweepState:
    """
    Update child status with transition guard.
    Update parent counts.
    """
    child = next((entry for entry in parent.children if entry.sweep_child_id == child_id), None)
    if child is None:
        return parent

    if child.status == new_status:
        if failure_reason and new_status == ChildJobStatus.failed:
            child.failure_reason = failure_reason
    elif _advance_status(child, new_status):
        if child.status == ChildJobStatus.failed:
            child.failure_reason = failure_reason

    parent.completed_count = sum(1 for entry in parent.children if entry.status == ChildJobStatus.completed)
    parent.failed_count = sum(1 for entry in parent.children if entry.status == ChildJobStatus.failed)
    return parent
