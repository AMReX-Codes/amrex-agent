"""Run MCP in-process with memory streams and list tools."""

import anyio
from mcp.client.session import ClientSession
import mcp_server


async def main() -> None:
    """Start the MCP server in-process and list available tools."""
    client_to_server_send, client_to_server_recv = anyio.create_memory_object_stream(0)
    server_to_client_send, server_to_client_recv = anyio.create_memory_object_stream(0)

    init_options = mcp_server.app.create_initialization_options()

    async with anyio.create_task_group() as tg:
        tg.start_soon(
            mcp_server.app.run,
            client_to_server_recv,
            server_to_client_send,
            init_options,
        )

        async with ClientSession(server_to_client_recv, client_to_server_send) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            tools = _normalize_tools(tools_response)
            tool_names = [getattr(tool, "name", str(tool)) for tool in tools]
            print(f"tools: {tool_names}")


def _normalize_tools(tools_response):
    """Normalize list_tools response across MCP client versions."""
    if tools_response is None:
        return []
    if hasattr(tools_response, "tools"):
        return getattr(tools_response, "tools") or []
    if isinstance(tools_response, tuple):
        tools_response = tools_response[0]
    if isinstance(tools_response, dict):
        return tools_response.get("tools", []) or []
    return tools_response or []


anyio.run(main)
