"""Academy agent wrapper around AMReX MCP adapter tools."""

from __future__ import annotations

import asyncio
from typing import Any

from academy.agent import Agent, action

from src.interactive_service import invoke_tool
from src.tool_registry import get_tool_specs


class AMReXMCPAgent(Agent):
    """Expose MCP tool functions as Academy actions."""

    @staticmethod
    def _maybe_wrap_response_rationale(
        result: Any,
        include_response_rationale: bool,
    ) -> Any:
        """Optionally wrap tool output with response/rationale summary fields."""
        if not include_response_rationale:
            return result

        if isinstance(result, dict):
            has_error = bool(result.get("error"))
            if has_error:
                response = f"error: {result.get('error')}"
            else:
                response = (
                    result.get("response")
                    or result.get("answer")
                    or result.get("status")
                    or result.get("selected_case")
                    or "ok"
                )
            rationale = result.get("rationale") or result.get("reasoning")
            wrapped: dict[str, Any] = {
                "response": response,
                "status": "error" if has_error else "ok",
                "data": result,
            }
            if rationale:
                wrapped["rationale"] = rationale
            return wrapped

        return {"response": str(result), "data": result}

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
        include_response_rationale: bool = False,
    ) -> Any:
        """Dispatch a tool call by name with optional session context."""
        try:
            result = await asyncio.to_thread(
                invoke_tool,
                name,
                dict(arguments or {}),
                session_id=session_id,
                surface="academy",
            )
        except Exception as exc:
            import traceback

            return {
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }

        return self._maybe_wrap_response_rationale(result, include_response_rationale)

    @action
    async def execute_workflow(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        """Convenience action for execute_workflow."""
        return await self.call_tool(
            "execute_workflow",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def query_knowledge(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "query_knowledge",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def select_baseline_case(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "select_baseline_case",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def create_simulation_plan(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "create_simulation_plan",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def create_proposed_modifications_with_plan(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "create_proposed_modifications_with_plan",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def apply_plan(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "apply_plan",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def validate_inputs(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "validate_inputs",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def validate_config(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "validate_config",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def setup_job(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "setup_job",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def run_simulation(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "run_simulation",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def analyze_results(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "analyze_results",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def generate_visualizations(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "generate_visualizations",
            payload,
            include_response_rationale=include_response_rationale,
        )

    @action
    async def stage_out_globus(
        self,
        payload: dict[str, Any],
        include_response_rationale: bool = False,
    ) -> Any:
        return await self.call_tool(
            "stage_out_globus",
            payload,
            include_response_rationale=include_response_rationale,
        )
