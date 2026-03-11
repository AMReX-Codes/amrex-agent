#!/usr/bin/env python3
"""AMReXAgent MCP server entrypoint.

Thin stdio server wrapper; tool implementations live in src.mcp_tools.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("[WARN] MCP library not available. Install with: pip install mcp", file=sys.stderr)

try:
    from src.mcp_tools import (
        AMReXAgentConfig,
        AnalysisService,
        ArchitectService,
        InputWriterService,
        LocalRunner,
        PeleKnowledgeService,
        SimulationPlan,
        SuperfacilityRunner,
        ValidationService,
        VisualizationService,
        config,
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
        mcp_stage_out_globus,
        mcp_validate_config,
        mcp_validate_inputs,
        _get_session_context,
        _persist_session_context,
    )
    from src.interactive_service import invoke_tool
except ModuleNotFoundError:
    import pathlib

    AMREX_AGENT_ROOT = pathlib.Path(__file__).parent
    sys.path.insert(0, str(AMREX_AGENT_ROOT))
    from src.mcp_tools import (
        AMReXAgentConfig,
        AnalysisService,
        ArchitectService,
        InputWriterService,
        LocalRunner,
        PeleKnowledgeService,
        SimulationPlan,
        SuperfacilityRunner,
        ValidationService,
        VisualizationService,
        config,
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
        mcp_stage_out_globus,
        mcp_validate_config,
        mcp_validate_inputs,
        _get_session_context,
        _persist_session_context,
    )
    from src.interactive_service import invoke_tool

if not HAS_MCP:
    print("[ERROR] MCP library required for server mode", file=sys.stderr)
    print("        Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

app = Server("pele-agent")
MAX_CONCURRENT_TOOL_CALLS = 5
_TOOL_CALL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_TOOL_CALLS)

print("[MCP] AMReXAgent starting...", file=sys.stderr)
print(f"[MCP] Environment: {config.environment}", file=sys.stderr)
print(f"[MCP] FAISS DB path: {config.faiss_db_path}", file=sys.stderr)
print(f"[MCP] Knowledge base path: {config.knowledge_base_path}", file=sys.stderr)


@app.list_tools()
async def list_tools():
    """List available AMReXAgent tools."""
    from mcp import Tool

    tool_specs = get_tool_specs()
    return [Tool(**spec) for spec in tool_specs]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> Any:
    """Handle tool calls from MCP client."""
    try:
        session_id = None
        context = dict(arguments)
        if "session_id" in context:
            session_id = str(context.get("session_id") or uuid.uuid4())
            context.pop("session_id", None)
        async with _TOOL_CALL_SEMAPHORE:
            return await asyncio.to_thread(
                invoke_tool,
                name,
                context,
                session_id=session_id,
                surface="mcp",
                # Do not accept caller_action from untrusted MCP payloads.
                caller_action=None,
            )

    except Exception as exc:
        import traceback

        return {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


async def main() -> None:
    """Start the MCP stdio server."""
    print("[MCP] Starting stdio server...", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        init_options = app.create_initialization_options()
        await app.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    print("[MCP] AMReXAgent MCP Server", file=sys.stderr)
    print(f"[MCP] Environment: {config.environment}", file=sys.stderr)
    print(f"[MCP] FAISS indices: {config.faiss_db_path}", file=sys.stderr)
    print("[MCP] Starting...", file=sys.stderr)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[MCP] Server stopped by user", file=sys.stderr)
    except Exception as exc:
        print(f"[MCP] Server error: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
