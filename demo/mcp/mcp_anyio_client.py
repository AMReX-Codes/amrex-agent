import anyio
from pathlib import Path
import tempfile

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main() -> None:
    server = StdioServerParameters(command="python", args=["-u", "mcp_server.py"])
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            tools = _normalize_tools(tools_response)
            tool_names = [getattr(tool, "name", str(tool)) for tool in tools]
            print(f"tools: {tool_names}")

            inputs_path = await anyio.to_thread.run_sync(_write_inputs_file)
            result = await session.call_tool(
                "validate_inputs",
                {"inputs_file_path": str(inputs_path)},
            )
            print(result)


def _write_inputs_file():
    temp_dir = Path(tempfile.mkdtemp(prefix="amrex_mcp_"))
    inputs_path = temp_dir / "inputs"
    inputs_path.write_text("amr.max_level = 1\n")
    return inputs_path


def _normalize_tools(tools_response):
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
