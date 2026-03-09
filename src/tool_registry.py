"""Shared MCP tool registry and dispatcher."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ToolHandler = Callable[[dict[str, Any]], Any]


def _tool_handlers() -> dict[str, ToolHandler]:
    from src.mcp_tools import (
        mcp_analyze_results,
        mcp_apply_plan,
        mcp_create_proposed_modifications_with_plan,
        mcp_create_simulation_plan,
        mcp_execute_workflow,
        mcp_generate_visualizations,
        mcp_query_knowledge,
        mcp_run_simulation,
        mcp_select_baseline_case,
        mcp_setup_job,
        mcp_stage_out_globus,
        mcp_validate_config,
        mcp_validate_inputs,
    )

    return {
        "query_knowledge": mcp_query_knowledge,
        "execute_workflow": mcp_execute_workflow,
        "create_simulation_plan": mcp_create_simulation_plan,
        "create_proposed_modifications_with_plan": mcp_create_proposed_modifications_with_plan,
        "apply_plan": mcp_apply_plan,
        "select_baseline_case": mcp_select_baseline_case,
        "search_cases": mcp_select_baseline_case,
        "validate_inputs": mcp_validate_inputs,
        "validate_config": mcp_validate_config,
        "setup_job": mcp_setup_job,
        "run_simulation": mcp_run_simulation,
        "analyze_results": mcp_analyze_results,
        "get_workflow_status": mcp_analyze_results,
        "generate_visualizations": mcp_generate_visualizations,
        "stage_out_globus": mcp_stage_out_globus,
    }


def get_tool_specs() -> list[dict[str, Any]]:
    """Return tool schema specs from MCP tools."""
    from src.mcp_tools import get_tool_specs as _get_tool_specs

    return _get_tool_specs()


def get_handler(name: str) -> ToolHandler:
    """Return the tool handler for a tool name or raise ValueError."""
    handler = _tool_handlers().get(name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name}")
    return handler


def dispatch_tool(name: str, context: dict[str, Any]) -> Any:
    """Dispatch a tool by name using the shared registry."""
    return get_handler(name)(context)


__all__ = ["dispatch_tool", "get_handler", "get_tool_specs"]
