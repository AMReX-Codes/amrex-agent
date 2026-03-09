"""Canonical invocation path for interactive multi-surface tool calls."""

from __future__ import annotations

from typing import Any

from src.policy import evaluate_gate_policy
from src.session_manager import (
    append_policy_audit,
    merge_session_context,
    persist_session_result,
)
from src.tool_registry import dispatch_tool


def invoke_tool(
    name: str,
    arguments: dict[str, Any] | None = None,
    *,
    session_id: str | None = None,
    surface: str = "unknown",
    caller_action: str | None = None,
) -> Any:
    """
    Invoke a tool through shared session + policy + dispatch layers.

    Returns the underlying tool output. Policy denials are returned as
    structured error dictionaries to preserve current API behavior.
    """
    context = merge_session_context(
        session_id=session_id,
        arguments=dict(arguments or {}),
    )
    decision = evaluate_gate_policy(
        tool_name=name,
        context=context,
        caller_action=caller_action,
    )

    append_policy_audit(
        context,
        tool_name=name,
        surface=surface,
        caller_action=caller_action,
        gate_required=decision.gate_required,
        bypass_applied=decision.bypass_applied,
        reason_code=decision.reason_code,
        policy_version=decision.policy_version,
    )

    if not decision.allowed:
        result: dict[str, Any] = {
            "error": "Gate approval required",
            "tool": name,
            "gate": {
                "gate_required": decision.gate_required,
                "approved": decision.approved,
                "gate_bypassed": decision.bypass_applied,
                "reason_code": decision.reason_code,
                "policy_version": decision.policy_version,
            },
        }
        return persist_session_result(
            session_id=session_id,
            context=context,
            result=result,
        )

    result = dispatch_tool(name, context)
    if isinstance(result, dict):
        gate_block = {
            "gate_required": decision.gate_required,
            "gate_bypassed": decision.bypass_applied,
            "reason_code": decision.reason_code,
            "policy_version": decision.policy_version,
        }
        result.setdefault("gate", gate_block)

    return persist_session_result(
        session_id=session_id,
        context=context,
        result=result,
    )
