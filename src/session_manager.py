"""Shared session merge/persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
