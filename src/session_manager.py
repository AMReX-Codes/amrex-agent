"""Shared session merge/persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SESSION_DEPENDENCY_COMPLETION_MARKER = "session_dependency_complete"


@dataclass(frozen=True)
class SessionEnvelope:
    """Session metadata provided by calling surfaces."""

    session_id: str
    surface: str
    persist: bool = True
    metadata: dict[str, Any] | None = None


def _get_store_functions():
    from src.mcp_tools import _get_session_context, _persist_session_context

    return _get_session_context, _persist_session_context


B4_IMPLEMENTATION_SEQUENCE = (
    "overview",
    "graph_topology_addition",
    "paper_parser_service",
    "validation_manifest_schema",
    "paper_validator_mode_1",
    "paper_validator_mode_2",
    "new_cli_arguments",
    "implementation_sequencing",
)
INHERITANCE_COST_REDUCTION_TARGET = 0.60


def _normalize_sequence_step(step: str) -> str:
    return step.strip().lower().replace("-", "_").replace(" ", "_")


def _coerce_non_negative_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if numeric >= 0 else None
    return None


def evaluate_inheritance_cost_reduction(context: dict[str, Any]) -> dict[str, Any] | None:
    """
    Evaluate inheritance planning-cost savings and target compliance.

    Expected context keys:
    - independent_planning_cost_usd
    - inherited_planning_cost_usd
    """
    independent = _coerce_non_negative_number(context.get("independent_planning_cost_usd"))
    inherited = _coerce_non_negative_number(context.get("inherited_planning_cost_usd"))
    if independent is None or inherited is None or independent == 0:
        return None

    reduction_ratio = (independent - inherited) / independent
    return {
        "independent_planning_cost_usd": independent,
        "inherited_planning_cost_usd": inherited,
        "cost_reduction_ratio": reduction_ratio,
        "cost_reduction_percent": reduction_ratio * 100,
        "target_reduction_ratio": INHERITANCE_COST_REDUCTION_TARGET,
        "target_reduction_percent": INHERITANCE_COST_REDUCTION_TARGET * 100,
        "target_met": reduction_ratio >= INHERITANCE_COST_REDUCTION_TARGET,
    }


def is_b4_implementation_sequence_complete(context: dict[str, Any]) -> bool:
    """
    Return True when validation_manifest includes the full staged B4 sequence.

    Supported manifest shapes:
    - {"b4_implementation_sequence": [...]}
    - {"b4": {"implementation_sequence": [...]}}
    - {"sessions": {"b4": {"implementation_sequence": [...]}}}
    """
    manifest = context.get("validation_manifest")
    if not isinstance(manifest, dict):
        return False

    sequence: Any = manifest.get("b4_implementation_sequence")
    if sequence is None:
        b4_entry = manifest.get("b4")
        if isinstance(b4_entry, dict):
            sequence = b4_entry.get("implementation_sequence")
    if sequence is None:
        sessions = manifest.get("sessions")
        if isinstance(sessions, dict):
            b4_session = sessions.get("b4")
            if isinstance(b4_session, dict):
                sequence = b4_session.get("implementation_sequence")

    if not isinstance(sequence, list) or any(not isinstance(step, str) for step in sequence):
        return False

    normalized_required = {_normalize_sequence_step(step) for step in B4_IMPLEMENTATION_SEQUENCE}
    normalized_sequence = {_normalize_sequence_step(step) for step in sequence}
    if normalized_required - normalized_sequence:
        return False

    positions = {_normalize_sequence_step(step): idx for idx, step in enumerate(sequence)}
    ordered_required = [_normalize_sequence_step(step) for step in B4_IMPLEMENTATION_SEQUENCE]
    if any(positions[ordered_required[i]] >= positions[ordered_required[i + 1]] for i in range(len(ordered_required) - 1)):
        return False

    return True


def merge_session_context(
    *,
    session_id: str | None,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Merge persisted session context with call arguments."""
    context = dict(arguments)
    if not session_id:
        evaluation = evaluate_inheritance_cost_reduction(context)
        if evaluation is not None:
            context["inheritance_cost_reduction"] = evaluation
        return context

    get_session_context, _ = _get_store_functions()
    context = get_session_context(session_id)
    context.update(arguments)
    if "steps" not in arguments:
        context.pop("steps", None)
    evaluation = evaluate_inheritance_cost_reduction(context)
    if evaluation is not None:
        context["inheritance_cost_reduction"] = evaluation
    return context


def append_policy_audit(
    context: dict[str, Any],
    *,
    tool_name: str,
    surface: str,
    gate_required: bool,
    bypass_applied: bool,
    reason_code: str,
    policy_version: str,
    caller_action: str | None = None,
) -> None:
    """Append policy decision metadata to session context."""
    audits = context.setdefault("policy_audit", [])
    if isinstance(audits, list):
        audits.append(
            {
                "tool_name": tool_name,
                "surface": surface,
                "caller_action": caller_action,
                "gate_required": gate_required,
                "gate_bypassed": bypass_applied,
                "reason_code": reason_code,
                "policy_version": policy_version,
            }
        )


def persist_session_result(
    *,
    session_id: str | None,
    context: dict[str, Any],
    result: Any,
) -> Any:
    """Persist merged context and stamp session_id in dict results."""
    if not session_id:
        return result
    merged_context = dict(context)
    if isinstance(result, dict):
        merged_context.update(result)
    _, persist_session_context = _get_store_functions()
    persist_session_context(session_id, merged_context)
    if isinstance(result, dict):
        result.setdefault("session_id", session_id)
    return result


def is_session_dependency_complete(state: dict[str, Any]) -> bool:
    """Return True when the required session dependency marker is present."""
    if state.get(SESSION_DEPENDENCY_COMPLETION_MARKER) is True:
        return True

    session_markers = state.get("session_markers")
    if isinstance(session_markers, dict):
        if session_markers.get(SESSION_DEPENDENCY_COMPLETION_MARKER) is True:
            return True

    completed_sessions = state.get("completed_sessions")
    if isinstance(completed_sessions, list):
        return (
            SESSION_DEPENDENCY_COMPLETION_MARKER in completed_sessions
            or "session_dependency_complete" in completed_sessions
        )

    return False
