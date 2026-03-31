# AMReXAgent Demo

Quick start guide for running AMReXAgent demos and sanity checks.

## Interface Paths

Use the path that matches your integration target:

| Path | Entry point | Best for |
|---|---|---|
| CLI | `python amrex_agent.py ...` | direct workflows and full CLI options |
| MCP stdio | `python -u mcp_server.py` + `demo/mcp/*client*` | MCP tool contract and transport smoke tests |
| Academy exchange | `python demo/mcp/academy_amrex_agent.py` | Academy/AISAC discovery with AMReX MCP actions |

For MCP and Academy payload-level guidance, use `demo/mcp/README.md` and `docs/mcp.md`.

## Demo Layout

```
demo/
  alcf/       # ALCF inference endpoint demo (in development)
  amrex/      # AMReX-focused config overrides
  alcf/       # ALCF-specific demo config + notes
  erf/        # ERF-focused demo scripts
  pelec/      # PeleC-focused demo notes
  pelelmex/   # PeleLMeX-focused demo scripts + prompt files
  vector_store/ # Hosted vector store setup notes
  README.md
  run_examples.sh
  setup_demo_database.sh
```

## Setup

### 0. Run from repo root

```bash
cd /path/to/amrex-agent
```

### 1. Create Conda Environment

```bash
conda env create -f environment.yaml
conda activate amrex-agent-dev
```

### 2. Set API Key (provider endpoints configured in src/config.py)

```bash
export CBORG_API_KEY=your_key_here
# or for ALCF (first pass: default to Sophia/vLLM base URL)
export ALCF_API_KEY=your_access_token
export ALCF_BASE_URL=https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1
# optional cluster shortcut:
export ALCF_CLUSTER=sophia
# or for OpenAI
export OPENAI_API_KEY=your_key_here
# or for Anthropic
export ANTHROPIC_API_KEY=your_key_here
```

ALCF tokens are short-lived; use `python inference_auth_token.py get_access_token` after authenticating with the ALCF helper script.

To use ALCF as the LLM provider, set `llm_provider: alcf` in `config.yaml` (or the config file you pass to the CLI).

### 3. Clone Source Repositories (first time only)

The agent requires access to solver source code to build indices. By default we expect each solver repository as a sibling of `amrex-agent`:

```bash
cd ..  # Go to parent directory of amrex-agent
git clone --recursive https://github.com/AMReX-Combustion/PeleC.git
git clone --recursive https://github.com/AMReX-Combustion/PeleLMeX.git
git clone --recursive https://github.com/erf-model/ERF.git
git clone --recursive https://github.com/AMReX-Codes/amrex.git
cd amrex-agent  # Return to amrex-agent directory
```

If you store the repos elsewhere, set environment variables:

```bash
export PELEC_REPO_PATH=/path/to/PeleC
export PELELMEX_REPO_PATH=/path/to/PeleLMeX
export ERF_REPO_PATH=/path/to/ERF
export AMREX_REPO_PATH=/path/to/amrex
```

If you want `--clone-missing` to pull specific forks/branches/commits, edit `.dependencies.json` in the repo root. This is only for cloning missing repos; normal runs use the sibling repos or the `AMREX_HOME` / `*_REPO_PATH` overrides you provide.

### 4. Build Database Indices

```bash
bash demo/setup_demo_database.sh --force-rebuild
```

This extracts parameter schemas and builds FAISS indices from the source repositories.
If prebuilt schemas/indices are already present in `database/schemas` and `database/faiss`, you can skip this step. Those artifacts are tied to specific code commits; compare the commit hash recorded in `.dependencies.json` with the commit in your local repo if you need to validate you’re using the same version.
Use the `--code <code>` variant for the specific repo you are actively working with.

To build indices for a single code only:

```bash
bash demo/setup_demo_database.sh --code erf --force-rebuild
bash demo/setup_demo_database.sh --code amrex --force-rebuild
bash demo/setup_demo_database.sh --code pelelmex --force-rebuild
```

To clone missing solver repos automatically (requires git + network):

```bash
bash demo/setup_demo_database.sh --clone-missing
```

To run the hierarchy build without API calls (mock embeddings):

```bash
bash demo/setup_demo_database.sh --mock
```

To build indices and upload to the hosted OpenAI vector store:

```bash
bash demo/setup_demo_database.sh --upload-openai
```

### Startup readiness preflight prerequisites

Use this as the zero-manual-setup path for first runs:

1. Keep solver repos as siblings of `amrex-agent` (autodetected default).
2. Run `bash demo/setup_demo_database.sh --force-rebuild` (or `--code <code> --force-rebuild` for the repo you're using).
3. Start the CLI from repo root.

Required behavior and fallbacks:

- Sibling repo autodetect: default lookup is `../ERF`, `../PeleC`, `../PeleLMeX`, `../amrex`.
- Auto-clone fallback: run `bash demo/setup_demo_database.sh --clone-missing` to fetch missing repos using `.dependencies.json` pins.
- Rebuild/index repair: if schemas or FAISS artifacts are stale/corrupt, rerun setup.
  - Full rebuild: `bash demo/setup_demo_database.sh --force-rebuild`
  - Single-code repair: `bash demo/setup_demo_database.sh --code <code> --force-rebuild`
- Non-interactive fail-fast: CI/headless startup readiness checks should exit non-zero on blocking repo/dependency/index issues instead of prompting.
- Code-specific build policy: defaults and fallbacks can vary by solver/codebase.
- ERF-specific build policy is documented in `demo/erf/README.md` (CMake Release default and GNUmake fallback notes).

### Optional: Hosted Vector Store (no local FAISS)

If you want hosted retrieval instead of local indices, see `demo/vector_store/README.md`.
You can upload once and then set `vector_store_backend: openai` in your config.

## Running the Demo

Note: Run commands from the repo root so relative paths like `demo/...` resolve correctly.

If you are testing MCP or Academy behavior (instead of CLI-only behavior), start with:

- `demo/mcp/README.md` for runnable examples
- `docs/mcp.md` for canonical payload/contract definitions

### Option 0: AMReX baseline + inputs only (no modifications)

Use explicit overrides for the problem directory (`--baseline-override`) and inputs file.

```bash
python amrex_agent.py \
  --prompt "Use the AMReX Advection_AmrCore baseline as-is" \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --inputs-file-strategy override \
  --inputs-file-override inputs \
  --indexing-strategy simple \
  --save-workflow \
  --verbose
```

### Option 1: AMReX baseline + modifications (baseline specified)

```bash
python amrex_agent.py \
  --prompt "AMReX Advection_AmrCore with a 128x128 grid and 3 AMR levels" \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --indexing-strategy override_static \
  --save-workflow
```

#### Using a user requirements file:
```bash
python amrex_agent.py \
  --prompt_path demo/amrex/user_requirement.txt \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --save-workflow \
  --verbose
```

Note: This prompt-file demo can hit the reviewer retry limit if parameter
resolution fails. For a more reliable run, use the inline prompt or the
config override example instead.

Example user requirements file format (`demo/amrex/user_requirement.txt`):
```
AMReX advection test
Grid: 512x512 cells
AMR: 2 levels of refinement
Run for 1000 timesteps
```

#### Using a config override file:
```bash
python amrex_agent.py \
  --prompt "Run AMReX Advection_AmrCore with a 64x64 grid" \
  --config demo/amrex/config.yaml
```

### Option 2: Solver-specific demos (ERF / Pele)

#### ERF selection and plan checks:
```bash
python demo/erf/test_solver_selection.py
python demo/erf/test_simulation_plan_creation.py
```

#### PeleLMeX overrides and writer flows:
```bash
python demo/pelelmex/test_override_path.py
python demo/pelelmex/test_baseline_override.py
python demo/pelelmex/test_writer_service.py
```

### Option 2: Automated Examples (Under Development)

```bash
bash demo/run_examples.sh
```

**Note:** This script is under development. For reliable testing, use Option 1 with `amrex_agent.py` and basic user requirement files.

### Example: Targeted PeleLMeX override

```bash
python amrex_agent.py \
  --prompt "2D hydrogen premixed flame with 32x128 grid cells, 2 AMR levels, 200 timesteps" \
  --baseline-override PeleLMeX/Exec/RegTests/FlameSheet \
  --indexing-strategy simple \
  --inputs-file-strategy override \
  --inputs-file-override flamesheet-drm19-2d.inp \
  --save-workflow \
  --save-transcript \
  --save-log \
  --color-logs always \
  --verbose
```

This command produces a full workflow history and logs even if execution fails
due to local environment issues (e.g., MPI/runtime setup).

**Note:** This grid size preserves the domain aspect ratio (dx ≈ dy). Refining
the spatial grid typically requires more conservative time stepping.

## AMReX Demo (Simple Indexing)

Build schema + indices:

```bash
bash demo/setup_demo_database.sh --code amrex --force-rebuild
```

Run a simple AMReX demo:

```bash
python amrex_agent.py \
  --prompt "AMReX Advection_AmrCore baseline with a 64x64 grid" \
  --output-dir /tmp/amrex_e2e_runs \
  --indexing-strategy simple \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --run-mode dry \
  --save-workflow
```

For PeleC-specific examples, see `demo/pelec/README.md`.
For Superfacility (SFAPI) Perlmutter notes, see `demo/superfacility/README.md`.

## Command Line Options

```
Required (one of):
  --prompt "text"           Inline simulation request
  --prompt_path FILE        Path to text file with request

Optional:
  --output-dir DIR          Where to save generated files (default: output/run_<timestamp>)
  --save-workflow           Save workflow_history.json
  --save-transcript         Save agent reasoning log
  --verbose, -v             Enable debug output
  --run-mode MODE           Run strategy: dry, stage, submit, full (default: full)
  --indexing-strategy       Choose "simple", "hierarchical", or "override_static"
  --inputs-file-strategy    Choose inputs selection: oldest/newest/smallest/llm_compare/override
  --inputs-file-override    Explicit inputs file (absolute path or relative to case dir)
  --baseline-override       Force baseline case (skips automatic selection)
  --run-serial              Run locally without MPI (use serial executable if available)
  --run-ntasks N            Local run tasks (mpirun -np N, default: 1)
```

Local runs default to MPI with 1 task. If you want to test without MPI, pass
`--run-serial` (and optionally `--run-ntasks N` when MPI is enabled).

## Output

Generated simulation files are saved to the specified output directory:
- `inputs` - simulation input file
- `probin` - problem-specific parameters (if applicable)
- `run.sh` - execution script
- `README.md` - simulation summary
- `workflow_history.json` - complete workflow trace (with `--save-workflow`)
- `transcript.txt` - agent reasoning log (with `--save-transcript`)
