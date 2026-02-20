# MCP + Academy Demo

This folder documents two integration paths for AMReXAgent tools:

- `stdio MCP`: local subprocess client/server using `mcp_server.py`
- `Academy exchange`: register `AMReXMCPAgent` to the Academy exchange

Mode selection and interface mapping are defined in `docs/mcp.md`.
This page focuses on runnable setup and example requests.

## Setup

### NERSC (Perlmutter login)

```bash
cd /global/cfs/cdirs/amsc014/superfacility/amrex-agent
conda activate amrex-agent-dev
```

If needed:

```bash
conda env create -f environment.yaml
conda activate amrex-agent-dev
```

### ALCF (Crux)

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
```

This follows ALCF guidance (base conda + venv overlay). Running without a venv is not recommended because shared base envs are not writable for `pip install`.

## Path A: MCP stdio

### Start server

```bash
python -u mcp_server.py
```

### Run stdio smoke client

```bash
python demo/mcp/mcp_stdio_client_smoke.py
```

Expected abridged output:

```text
tools: ['query_knowledge', 'execute_workflow', ...]
structuredContent={'valid': False, 'errors': [...], 'warnings': [...]}
```

### Run execute_workflow examples (stdio)

```bash
python demo/mcp/mcp_execute_workflow_examples.py
```

## Path B: Academy exchange

Run the Academy wrapper for AMReX MCP tools:

```bash
conda activate amrex-agent-dev
python demo/mcp/academy_amrex_agent.py
```

Expected startup:

```text
AMReXMCPAgent running: <agent_id>
Press Ctrl+C to stop
```

Notes:
- First run may require Globus auth.
- Globus auth is interactive: you must open the URL and paste the auth code in the terminal.
- Non-interactive execution (for example CI/background jobs) will fail during Academy login.
- Keep this process running while bridge/client discovery occurs.
- Use this mode instead of stdio when validating Academy/AISAC integration.

### Academy execute_workflow smoke calls

After startup prints `AMReXMCPAgent uid: <uuid>`, run:

```bash
python demo/mcp/academy_execute_workflow_smoke.py --agent-id <uuid>
```

This issues `list_tools`, `execute_workflow` (plan+run dry-run), `execute_workflow`
with `config_overrides`, and a `generate_visualizations` tool call.

### Interactive two-terminal helper

Use the helper script to run and log both sides consistently:

Terminal A:

```bash
demo/mcp/run_academy_handoff_interactive.sh agent
```

Terminal B:

```bash
AGENT_ID=$(demo/mcp/run_academy_handoff_interactive.sh extract-agent-id)
demo/mcp/run_academy_handoff_interactive.sh client --agent-id "$AGENT_ID"
```

Default evidence output is `output/handoff_runs/2026-02-20/`.

## Recipe Payload Examples

### 1) Plan + run only (no analysis)

```json
{
  "prompt": "<contents of demo/pelelmex/user_requirements_DNS_isothermal_reacting.txt>",
  "steps": ["create_simulation_plan", "run_simulation"],
  "output_dir": "output/mcp/pelelmex",
  "submit": {"dry_run": true},
  "baseline_override": "PeleLMeX/Exec/Production/JetInCrossflow"
}
```

### 2) Visualization only

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

### 3) Config overrides per call

Local run override:

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

## Related docs and scripts

- Current MCP contract templates: `docs/mcp.md`
- In-process memory stream demo: `demo/mcp/mcp_inprocess_examples.py`
- CLI comparison scripts: `demo/mcp/run_dns_cli_examples.sh`, `demo/mcp/run_dns_cli_examples_dry_verbose.sh`
