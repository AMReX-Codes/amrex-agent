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
./demo/mcp/run_mcp_stdio.sh
```

## Run anyio client (spawns server)

```bash
python demo/mcp/mcp_anyio_client.py
```

The anyio client starts a stdio MCP server subprocess, lists tools, and calls
`validate_inputs` against a temporary inputs file to verify wiring.

Note: The anyio client uses `StdioServerParameters`, required by recent MCP
client versions.
