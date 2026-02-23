"""Academy agent wrapper around AMReX MCP adapter tools."""

from __future__ import annotations

import asyncio
from typing import Any

from academy.agent import Agent, action

from src.mcp_tools import (
    get_tool_specs,
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
    mcp_validate_config,
    mcp_validate_inputs,
    _get_session_context,
    _persist_session_context,
)


class AMReXMCPAgent(Agent):
    """Expose MCP tool functions as Academy actions."""

    @action
    async def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP tool specifications."""
        return get_tool_specs()

    @action
    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Any:
        """Dispatch a tool call by name with optional session context."""
        context = dict(arguments or {})
        provided_steps = "steps" in context

        if session_id:
            session_context = _get_session_context(session_id)
            session_context.update(context)
            if not provided_steps:
                session_context.pop("steps", None)
            context = session_context

        try:
            result = await asyncio.to_thread(self._dispatch_tool, name, context)
        except Exception as exc:
            import traceback

            return {
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }

        if session_id:
            merged_context = dict(context)
            if isinstance(result, dict):
                merged_context.update(result)
            _persist_session_context(session_id, merged_context)
            if isinstance(result, dict):
                result.setdefault("session_id", session_id)

        return result

    def _dispatch_tool(self, name: str, context: dict[str, Any]) -> Any:
        """Dispatch MCP tool calls synchronously for thread execution."""
        if name == "query_knowledge":
            return mcp_query_knowledge(context)
        if name == "execute_workflow":
            return mcp_execute_workflow(context)
        if name == "create_simulation_plan":
            return mcp_create_simulation_plan(context)
        if name == "create_proposed_modifications_with_plan":
            return mcp_create_proposed_modifications_with_plan(context)
        if name == "apply_plan":
            return mcp_apply_plan(context)
        if name in {"select_baseline_case", "search_cases"}:
            return mcp_select_baseline_case(context)
        if name == "validate_inputs":
            return mcp_validate_inputs(context)
        if name == "validate_config":
            return mcp_validate_config(context)
        if name == "setup_job":
            return mcp_setup_job(context)
        if name == "run_simulation":
            return mcp_run_simulation(context)
        if name in {"analyze_results", "get_workflow_status"}:
            return mcp_analyze_results(context)
        if name == "generate_visualizations":
            return mcp_generate_visualizations(context)
        raise ValueError(f"Unknown tool: {name}")

    @action
    async def execute_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Convenience action for execute_workflow."""
        return await self.call_tool("execute_workflow", payload)
