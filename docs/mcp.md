# MCP and Academy Integration

AMReXAgent exposes MCP tool endpoints in `mcp_server.py`, and the same tool surface
can be registered through Academy using `src/academy_mcp_agent.py`.

This page is the canonical reference for:
- which integration mode to use,
- how CLI concepts map to MCP payloads,
- supported `execute_workflow` payload patterns.

## Integration Mode Matrix

| Mode | Entry point | Transport | Best for |
|---|---|---|---|
| CLI | `python amrex_agent.py ...` | none | direct workflows and full CLI behavior (`--config`, local iteration) |
| MCP stdio | `python -u mcp_server.py` + MCP client | stdio JSON-RPC | tool schema testing and external MCP orchestrators |
| Academy exchange | `python demo/mcp/academy_amrex_agent.py` | Academy exchange + Globus | AISAC/Academy discovery and delegated execution |

## Start Commands

### MCP stdio server

```bash
python -u mcp_server.py
```

### MCP stdio smoke client

```bash
python demo/mcp/mcp_stdio_client_smoke.py
```

### Academy exchange launcher (AMReX wrapper)

```bash
python demo/mcp/academy_amrex_agent.py
```

## Tool Inventory

The MCP server exposes these tools:

- `query_knowledge`
- `execute_workflow`
- `create_simulation_plan`
- `apply_plan`
- `create_proposed_modifications_with_plan`
- `select_baseline_case`
- `search_cases` (alias for `select_baseline_case`)
- `validate_inputs`
- `validate_config` (schema-level config validation)
- `setup_job`
- `run_simulation`
- `analyze_results`
- `get_workflow_status` (alias for `analyze_results`)
- `generate_visualizations`

Use MCP `tools/list` to inspect exact schemas.

## CLI to MCP Payload Mapping

MCP takes payload objects; it does not take CLI argument strings.

| CLI concept | MCP equivalent |
|---|---|
| `--prompt-path file.txt` | caller reads file and sends `prompt: "..."` |
| `--baseline-override ...` | `baseline_override` |
| `--run-mode dry` | `submit: {"dry_run": true}` |
| `--environment perlmutter` | `config_overrides: {"environment": "perlmutter"}` |
| `--output-dir ...` | `output_dir` and/or `config_overrides.output_dir` |
| `--config demo/superfacility/config_perlmutter_remote.yaml` | no direct MCP config-file-path field; use `config_overrides` |

## Canonical Payloads

### execute_workflow: plan + run only (no analysis)

```json
{
  "prompt": "<contents of demo/pelelmex/user_requirements_DNS_isothermal_reacting.txt>",
  "steps": ["create_simulation_plan", "run_simulation"],
  "output_dir": "output/mcp/pelelmex",
  "submit": {"dry_run": true},
  "baseline_override": "PeleLMeX/Exec/Production/JetInCrossflow"
}
```

### generate_visualizations: visualization only

```json
{
  "run_directory": "output/mcp/pelelmex/run_001",
  "output_dir": "output/mcp/pelelmex/run_001/visualization",
  "visualization_config": {
    "plots": [
      {"type": "slice", "field": "Temp", "axis": "z", "colormap": "inferno", "vmin": 300, "vmax": 2500},
      {"type": "slice", "field": "density", "axis": "z"}
    ]
  }
}
```

### execute_workflow: per-call config overrides

Local run target:

```json
{
  "prompt": "...",
  "steps": ["create_simulation_plan", "run_simulation"],
  "config_overrides": {
    "environment": "local",
    "output_dir": "output/local_runs"
  }
}
```

Perlmutter/account override:

```json
{
  "prompt": "...",
  "steps": ["create_simulation_plan", "run_simulation"],
  "config_overrides": {
    "environment": "perlmutter",
    "superfacility_account": "m1234"
  },
  "submit": {"nodes": 2, "walltime": "00:30:00"}
}
```

## Smoke Test Ladder

1. **Transport smoke**: `python demo/mcp/mcp_stdio_client_smoke.py`
2. **Workflow smoke**: `python demo/mcp/mcp_execute_workflow_examples.py`
3. **Academy registration smoke**: `python demo/mcp/academy_amrex_agent.py`

## Operational Notes

### Crux stdio runbook (ALCF)

Recommended setup is shared conda base + venv overlay:

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

### SFAPI credential discovery

Superfacility runner checks:

- `SBATCH_ACCOUNT`
- `SUPERFACILITY_CLIENT_ID`, `SUPERFACILITY_SECRET`
- `NERSC_API_TOKEN` or `SFAPI_TOKEN`
- `SFAPI_KEY_PATH`, `SUPERFACILITY_KEY_PATH`, `NERSC_SFAPI_KEY_PATH`
- `~/.superfacility/` key material

MCP requests do not switch server credentials per call; server process credentials are used.

### Session persistence

If `session_id` is provided on calls via `src/academy_mcp_agent.py`, merged tool context is stored in SQLite (`workflow_store_path` in `AMReXAgentConfig`, default `~/.amrex_agent/workflow_store.db`).

## Testing

```bash
pytest tests/unit/test_mcp_tools.py
```
