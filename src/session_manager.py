"""Shared session merge/persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FEATURE_A_DEPENDENCY_ID = "feature_a_dependency_gate"


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


def merge_session_context(
    *,
    session_id: str | None,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Merge persisted session context with call arguments."""
    if not session_id:
        return dict(arguments)
    get_session_context, _ = _get_store_functions()
    context = get_session_context(session_id)
    context.update(arguments)
    if "steps" not in arguments:
        context.pop("steps", None)
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


def resolve_dependency_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return state enriched with persisted session context when available."""
    session_id = state.get("session_id")
    if not session_id:
        return dict(state)
    return merge_session_context(
        session_id=str(session_id),
        arguments=dict(state),
    )


def feature_a_dependency_passed(state: dict[str, Any]) -> bool:
    """
    Return True when Feature A verification marker is present and passing.

    Supported marker surfaces:
    - top-level bool `feature_a_verified` or `feature_a_verification_passed`
    - gate approval record with details.criterion == FEATURE_A_DEPENDENCY_ID
    """
    explicit_marker = state.get("feature_a_verified")
    if isinstance(explicit_marker, bool):
        return explicit_marker

    alt_marker = state.get("feature_a_verification_passed")
    if isinstance(alt_marker, bool):
        return alt_marker

    approvals = state.get("gate_approvals", [])
    if not isinstance(approvals, list):
        return False

    for approval in approvals:
        if not isinstance(approval, dict):
            continue
        details = approval.get("details", {})
        if not isinstance(details, dict):
            continue
        if details.get("criterion") != FEATURE_A_DEPENDENCY_ID:
            continue
        decision = str(approval.get("decision", "")).lower()
        if decision in {"approved", "passed", "complete", "completed"}:
            return True
        return False
    return False


def feature_a_dependency_failure_reason(state: dict[str, Any]) -> str:
    """Return a stable reason code when Feature A dependency gate fails."""
    if feature_a_dependency_passed(state):
        return "feature_a_dependency_satisfied"
    return "feature_a_dependency_unverified"
