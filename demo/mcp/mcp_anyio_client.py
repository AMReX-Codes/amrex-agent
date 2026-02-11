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
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools]
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


anyio.run(main)
