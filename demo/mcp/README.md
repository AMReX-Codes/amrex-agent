# MCP Demo (Crux stdio)

This folder contains a minimal stdio-based MCP server/client demo intended for
Crux (ALCF) with a shared conda base + venv.

## Setup

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

```bash
./demo/mcp/run_mcp_stdio.sh
```

## Run anyio client (spawns server)

```bash
python demo/mcp/mcp_anyio_client.py
```

The anyio client starts a stdio MCP server subprocess, lists tools, and calls
`validate_inputs` against a temporary inputs file to verify wiring.
