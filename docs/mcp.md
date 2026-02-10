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
- `create_simulation_plan`
- `create_proposed_modifications_with_plan`
- `select_baseline_case`
- `validate_inputs`
- `setup_job`
- `run_simulation`
- `analyze_results`
- `generate_visualizations`

Use `tools/list` to discover schemas and required parameters.

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
