# MCP Demo (ALCF + NERSC stdio)

This folder contains a minimal stdio-based MCP server/client demo intended for
ALCF (Crux) or NERSC Perlmutter login nodes.

## Setup

### NERSC (Perlmutter login)

```bash
cd /global/cfs/cdirs/amsc014/mcp/amrex-agent
conda activate amrex-agent-dev
```

If you need a fresh env on Perlmutter:

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

## Run server (stdio)

### NERSC (Perlmutter login)

```bash
cd /global/cfs/cdirs/amsc014/mcp/amrex-agent
conda activate amrex-agent-dev
python -u mcp_server.py
```

### ALCF (Crux)

```bash
cd /lus/eagle/projects/COMB-FLOW-UNI/mcp/amrex-agent
python -u mcp_server.py
```

## Run anyio client (stdio subprocess)

```bash
python demo/mcp/mcp_stdio_client_smoke.py
```

The anyio client starts a stdio MCP server subprocess, lists tools, and calls
`validate_inputs` against a temporary inputs file to verify wiring.

Expected output (abridged):

```
tools: ['query_knowledge', 'execute_workflow', ...]
structuredContent={'valid': False, 'errors': [...], 'warnings': [...]}
```

Note: The anyio client uses `StdioServerParameters`, required by recent MCP
client versions.

## Example execute_workflow calls (stdio subprocess)

DNS isothermal (PeleLMeX):

```json
{
  "prompt": "<contents of demo/pelelmex/user_requirements_DNS_isothermal.txt>",
  "baseline_override": "PeleLMeX/Exec/Production/JetInCrossflow",
  "steps": ["create_simulation_plan", "run_simulation"],
  "submit": {"dry_run": true}
}
```

DNS test case:

```json
{
  "prompt": "<contents of demo/pelelmex/user_requirements_test_DNS.txt>",
  "baseline_override": "PeleLMeX/Exec/Production/JetInCrossflow",
  "steps": ["create_simulation_plan", "run_simulation"],
  "submit": {"dry_run": true}
}
```

Run them via the helper:

```bash
python demo/mcp/mcp_execute_workflow_examples.py
```

## In-process (memory stream) demo

This runs the MCP server in-process using memory streams (no subprocess, no stdio).

```bash
python demo/mcp/mcp_inprocess_examples.py
```

CLI equivalents (no dry-run/verbose, includes save flags):

```bash
./demo/mcp/run_dns_cli_examples.sh
```

CLI equivalents (dry-run + verbose):

```bash
./demo/mcp/run_dns_cli_examples_dry_verbose.sh
```
