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
- `apply_plan`
- `create_proposed_modifications_with_plan`
- `select_baseline_case`
- `search_cases` (alias for `select_baseline_case`)
- `validate_inputs`
- `validate_config` (alias for `validate_inputs`)
- `setup_job`
- `run_simulation`
- `analyze_results`
- `get_workflow_status` (alias for `analyze_results`)
- `generate_visualizations`

Use `tools/list` to discover schemas and required parameters.

## Example: apply_plan

Apply a previously generated plan to write inputs:

```json
{
  "selected_case": "PeleLMeX/Exec/RegTests/FlameSheet",
  "modifications": [["amr.max_level", "2"], ["geometry.prob_hi", "0.02 0.08"]],
  "baseline": {"code_name": "PeleLMeX"},
  "reasoning": "Increase AMR for sharper flame structure.",
  "output_dir": "output/mcp/pelelmex"
}
```

Example response:

```json
{
  "run_directory": "output/mcp/pelelmex/run_001",
  "inputs_file_path": "output/mcp/pelelmex/run_001/inputs",
  "modifications_applied": 2,
  "status": "ok",
  "requires_parameter_resolution": false,
  "unresolved_parameters": [],
  "available_schema_params": [],
  "suggested_params": {},
  "resolution_guidance": ""
}
```

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

## Crux stdio runbook (ALCF)

This is the recommended stdio-only setup for Crux using the shared conda base +
venv approach. It is intended for local runs only (no Perlmutter dispatch yet).

```bash
module use /soft/modulefiles
module load conda
conda activate base

cd /lus/eagle/projects/COMB-FLOW-UNI/mcp/amrex-agent
CONDA_NAME=$(echo ${CONDA_PREFIX} | tr '\/' '\t' | sed -E 's/mconda3|\/base//g' | awk '{print $NF}')
VENV_DIR="$(pwd)/venvs/${CONDA_NAME}"
python -m venv "${VENV_DIR}" --system-site-packages
source "${VENV_DIR}/bin/activate"
python -m pip install -U pip
python -m pip install -e .

python -u mcp_server.py
```

For an anyio subprocess client, see `demo/mcp/mcp_stdio_client_smoke.py`.

## SFAPI credential discovery (for later Perlmutter dispatch)

The superfacility runner checks these environment variables and files:

- `SBATCH_ACCOUNT` (default account if unset)
- `SUPERFACILITY_CLIENT_ID`, `SUPERFACILITY_SECRET`
- `NERSC_API_TOKEN` or `SFAPI_TOKEN`
- `SFAPI_KEY_PATH`, `SUPERFACILITY_KEY_PATH`, `NERSC_SFAPI_KEY_PATH`
- `~/.superfacility/` containing:
  - `clientid.txt` + `priv_key.jwk` (flat)
  - or `<color>_client/` with the same pair
  - `*.pem`, `key.pem`, or `priv_key.pem` (first line client ID, rest PEM key)

The PEM format expects the client ID on the first line; a standard
`-----BEGIN` header on the first line is ignored.

Note: MCP server submissions use the credentials available to the server
process (env vars and `~/.superfacility`). There is no per-request credential
switching, so start the server under the account you want to bill.

The same applies to LLM providers: CBORG, ALCF, OpenAI, etc. use the server
process credentials. Running the MCP server under your account means LLM calls
consume your quota and SFAPI submissions use your key.

## Session persistence (SQLite)

If a tool call includes `session_id`, the MCP server persists the merged
context in a SQLite store (WAL) and reuses it on subsequent calls with the same
`session_id`. The store path is configured by `workflow_store_path` in
`AMReXAgentConfig` (default `~/.amrex_agent/workflow_store.db`).

Note: `execute_workflow` does not reuse prior `steps` unless `steps` is
explicitly provided in the current request. Longer term, the session context
may be namespaced per tool to avoid cross-tool bleed.
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

## Standards alignment note

For standards alignment and capability mapping, see `docs/standards.md`.
