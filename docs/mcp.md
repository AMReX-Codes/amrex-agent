# MCP Integration

AMReXAgent exposes an MCP server in `mcp_server.py`. The MCP server provides
tool endpoints that wrap the core services (planning, validation, running,
analysis, visualization).

## Run the MCP server (stdio)

Start the server in stdio mode:

```bash
python -u mcp_server.py
```

MCP clients should spawn `mcp_server.py` and communicate over stdin/stdout.
The server writes logs to stderr to keep stdout clean for JSON-RPC.

## Tool inventory

The MCP server exposes these tools:

- `query_knowledge`
- `execute_workflow`
- `create_simulation_plan`
- `create_proposed_modifications_with_plan`
- `select_baseline_case`
- `validate_inputs`
- `setup_job`
- `run_simulation`
- `analyze_results`
- `generate_visualizations`

Use `tools/list` to discover schemas and required parameters.

## Demo: execute_workflow (in-process)

This mirrors the unit test wiring and runs `execute_workflow` without stdio:

```python
import anyio
from mcp.client.session import ClientSession
import mcp_server


async def main() -> None:
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

            remora = await session.call_tool(
                "execute_workflow",
                {
                    "prompt": "Run the REMORA Upwelling case to demonstrate wind-driven upwelling over a periodic channel.",
                    "baseline_override": "REMORA/Exec/Upwelling",
                    "strategy": "override_static",
                    "submit": {"dry_run": True},
                },
            )

            pelelmex = await session.call_tool(
                "execute_workflow",
                {
                    "prompt": "2D hydrogen premixed flame with 32x128 grid cells, 2 AMR levels, 200 timesteps",
                    "baseline_override": "PeleLMeX/Exec/RegTests/FlameSheet",
                    "strategy": "simple",
                    "steps": ["create_simulation_plan", "run_simulation"],
                    "submit": {"dry_run": True},
                },
            )

            staged = await session.call_tool(
                "execute_workflow",
                {
                    "prompt": "Run the JetInCrossflow DNS prompt from demo/pelelmex/user_requirements_test_DNS.txt",
                    "baseline_override": "PeleLMeX/Exec/Production/JetInCrossflow",
                    "strategy": "simple",
                    "steps": ["create_simulation_plan", "run_simulation"],
                    "submit": {"dry_run": True},
                    "config_overrides": {
                        "environment": "perlmutter",
                        "run_mode": "stage"
                    }
                },
            )

            print(remora)
            print(pelelmex)
            print(staged)


anyio.run(main)
```

## Smoke test (initialize response)

You can sanity-check the stdio transport with a JSON-RPC initialize request:

```bash
echo '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"probe","version":"0.0.0"}}}' > /tmp/mcp_init.json
python /tmp/mcp_probe.py /tmp/mcp_init.json
```

`/tmp/mcp_probe.py` can be created with the helper from the CLI workflow or by
mirroring the test logic in `tests/unit/test_mcp_tools.py`.

## Testing

MCP tests live in `tests/unit/test_mcp_tools.py`:

- In-process integration: uses memory streams with the MCP client session.
- Stdio integration: spawns `mcp_server.py` and sends JSON-RPC over stdio.

Run the MCP unit suite:

```bash
pytest tests/unit/test_mcp_tools.py
```

## Tool-calling LLMs

MCP provides the transport and tool definitions. Tool-calling from an LLM
still requires an orchestrator to map model tool calls into MCP tool calls.
AMReXAgent currently exposes the tools; orchestration happens outside.
