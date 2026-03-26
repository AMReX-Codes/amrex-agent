# MCP and Academy Integration

AMReXAgent exposes MCP tool endpoints in `mcp_server.py`, and the same tool surface
can be registered through Academy using `src/academy_mcp_agent.py`.

This page is the current reference for:
- which integration mode to use,
- how CLI concepts map to MCP payloads,
- supported `execute_workflow` payload patterns.

## Integration Mode Matrix

| Mode | Entry point | Transport | Best for |
|---|---|---|---|
| CLI | `python amrex_agent.py ...` | none | direct workflows and full CLI behavior (`--config`, local iteration) |
| MCP stdio | `python -u mcp_server.py` + MCP client | stdio JSON-RPC | tool schema testing and external MCP orchestrators |
| Academy exchange | `python demo/mcp/academy_amrex_agent.py` | Academy exchange + Globus | AISAC/Academy discovery and delegated execution |

For runnable command sequences and solver-specific recipes, see `demo/mcp/README.md`.

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

## Current Payload Templates

### execute_workflow: plan + run only (no analysis)

```json
{
  "prompt": "<required: natural-language request>",
  "steps": ["create_simulation_plan", "run_simulation"],
  "baseline_override": "<optional: solver case path>",
  "output_dir": "<optional: output path override>",
  "submit": {"dry_run": true}
}
```

### generate_visualizations: visualization only

```json
{
  "run_directory": "<required: existing run directory>",
  "output_dir": "<optional: visualization output directory>",
  "visualization_config": {
    "plots": [
      {"type": "slice", "field": "<field_name>", "axis": "z"}
    ]
  }
}
```

### execute_workflow: per-call config overrides

Local run target:

```json
{
  "prompt": "<required>",
  "steps": ["create_simulation_plan", "run_simulation"],
  "config_overrides": {
    "environment": "local",
    "output_dir": "<optional local output dir>"
  }
}
```

Perlmutter/account override:

```json
{
  "prompt": "<required>",
  "steps": ["create_simulation_plan", "run_simulation"],
  "config_overrides": {
    "environment": "perlmutter",
    "superfacility_account": "<project account>"
  },
  "submit": {"dry_run": true, "nodes": 2, "walltime": "00:30:00"}
}
```

For runnable solver-specific examples (PeleLMeX/JetInCrossflow/Perlmutter), see:
- `demo/mcp/mcp_execute_workflow_examples.py`
- `demo/mcp/README.md`

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

- `SBATCH_ACCOUNT` (default account if unset)
- `SBATCH_ACCOUNT`
- `SUPERFACILITY_CLIENT_ID`, `SUPERFACILITY_SECRET`
- `NERSC_API_TOKEN` or `SFAPI_TOKEN`
- `SFAPI_KEY_PATH`, `SUPERFACILITY_KEY_PATH`, `NERSC_SFAPI_KEY_PATH`
- `~/.superfacility/` containing:
- `clientid.txt` + `priv_key.jwk` (flat)
- or `<color>_client/` with the same pair
- `*.pem`, `key.pem`, or `priv_key.pem` (first line client ID, rest PEM key)
- `~/.superfacility/` key material

The PEM format expects the client ID on the first line; a standard
`-----BEGIN` header on the first line is ignored.

If using PEM key files, restrict permissions:

```bash
chmod 600 ~/.superfacility/*.pem
```

Note: MCP server submissions use the credentials available to the server
process (env vars and `~/.superfacility`). There is no per-request credential
switching, so start the server under the account you want to bill.

The same applies to LLM providers: CBORG, ALCF, OpenAI, etc. use the server
process credentials. Running the MCP server under your account means LLM calls
consume your quota and SFAPI submissions use your key.

### Session persistence

If `session_id` is provided on calls via `src/academy_mcp_agent.py`, merged tool context is stored in SQLite (`workflow_store_path` in `AMReXAgentConfig`, default `~/.amrex_agent/workflow_store.db`).

## Testing

```bash
pytest tests/unit/test_mcp_tools.py
```

## Runtime intent notes

- Runtime intent routing is documented in `docs/intent_runtime_routing.md`.
- Prompt-specified runtime settings remain subject to critical-tool gating.
- Noninteractive payloads do not gain extra permissions; approval still requires
  an approval token or trusted approval source.
