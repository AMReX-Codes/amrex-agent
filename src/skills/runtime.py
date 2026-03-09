"""Skill runtime utilities for routing/executing tool calls."""

from __future__ import annotations

from typing import Any

from src.interactive_service import invoke_tool


def run_skill_calls(
    tool_calls: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    surface: str = "skill",
    caller_action: str | None = None,
) -> list[dict[str, Any]]:
    """Execute an ordered list of tool calls via the canonical invoke path."""
    outputs: list[dict[str, Any]] = []
    for call in tool_calls:
        name = str(call.get("name", "")).strip()
        if not name:
            raise ValueError("Skill call missing tool name")
        arguments = call.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("Skill call arguments must be an object")
        result = invoke_tool(
            name,
            arguments,
            session_id=session_id,
            surface=surface,
            caller_action=caller_action,
        )
        outputs.append({"name": name, "result": result})
    return outputs
