# AMReXAgent

AMReXAgent is an AI workflow for configuring AMReX-based simulation codes from natural language prompts.
It turns freeform user intent into runnable simulation setups across the AMReX solver ecosystem
(combustion, atmospheric, plasma, fluids, and tutorial cases).


## Quick start

1) Create the environment:

```bash
conda env create -f environment.yaml
conda activate amrex-agent-dev
```

2) Set your API key (CBORG recommended):

```bash
export CBORG_API_KEY=your_key_here
```

3) Clone the solver repo you want to run (AMReX example):

```bash
cd ..  # parent of amrex-agent
git clone --recursive https://github.com/AMReX-Codes/amrex.git
cd amrex-agent
```

If you keep AMReX elsewhere, set `AMREX_REPO_PATH` (aliases: `AMReX_HOME`, `AMREX_HOME`).

4) Build the schema once for the solver repo:

```bash
python database/scripts/build_schema.py ../amrex --solver amrex
```

If you keep AMReX elsewhere, use that path (or set `AMREX_REPO_PATH` / `AMReX_HOME` / `AMREX_HOME`).

5) Run a prompt (CLI), for example (targeted baseline):

```bash
python amrex_agent.py \
  --prompt "AMReX Advection_AmrCore with a 64x64 grid and 2 AMR levels" \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --indexing-strategy override_static
```

For more scenarios, see `demo/README.md`.

### Optional: Superfacility API (SFAPI) submission

If you want to submit runs to NERSC via SFAPI, install `sfapi_client` and provide a
PEM key file where the **first line is the client ID** and the remaining lines are
the private key. Then set one of:

```bash
export SFAPI_KEY_PATH=/path/to/priv_key.pem
# or SUPERFACILITY_KEY_PATH / NERSC_SFAPI_KEY_PATH
```

Alternatively, you can still use REST-token auth with `NERSC_API_TOKEN` or `SFAPI_TOKEN`.
Monitoring will use `sfapi_client` if available, otherwise it falls back to the REST API.

If you follow the Synapse-style shared layout (SFAPI, NERSC systems), set your run artifacts under:
`/global/cfs/cdirs/$SBATCH_ACCOUNT/$USER/superfacility` (configure via `output_dir` or `--output-dir`).

For a Perlmutter-specific config template and demo notes, see `demo/superfacility/`.

Config override example:

```bash
python amrex_agent.py --prompt "Run AMReX Advection_AmrCore with a 64x64 grid" --config demo/amrex/config.yaml
```

## Configuration knobs (examples)

- `--indexing-strategy`:
  - `simple`: mainly on-the-fly code analysis + prompt engineering, with a mix of paper-inspired RAG embeddings stored locally for FAISS retrieval and LLM calls (see `database/configs/base_amrex_config.py:106` for prompt templates; FAISS retrieval/LLM fallback in `src/services/embedding.py:222`).
  - `hierarchical`: a hierarchical RAG embedding system (L0/L1/L2) with optional custom Level 2 indices (see `src/services/embedding.py:305` and `database/indexing/level2_builder.py:354`, plus config examples in `database/configs/base_amrex_config.py:601`).
  - `override_static`: a specific override for using just one executable or for extensive inputs-modification workflows; skips L0/L1/L2 and uses baseline override + raw docs/inputs (see `src/config.py:314`).

- `--baseline-override` and `--inputs-file-strategy`:
  - Use these when you want to **directly target** a specific problem directory and inputs file
    (e.g., `AMReX/Tests/Amr/Advection_AmrCore/Exec`, then `--inputs-file-strategy newest`).
  - This bypasses pre-built indices and prioritizes explicit selection, trading off discovery of
    related cases unless you specify them.

- `--indexing-strategy override_static` (targeted mode):
  - Skip dynamic indexing and rely on explicit baseline selection.
  - Intended for tightly scoped changes on a known case rather than exploratory search.

- `--preconfirm`:
  - Enables terminal pre-confirmation gates before each workflow node and before compile/run steps.
  - Useful when you want a pause to confirm actions at each stage.

- `--llm-gate-strategy`:
  - Controls prompt gating for LLM calls (pre-send and post-output checks).
  - Values: `off`, `default`, `feedback`, `gate-major`, `gate-all`, `gate-major-prompt`, `gate-all-prompt`.

Option 0 (override everything: baseline + inputs):

```bash
python amrex_agent.py \
  --prompt "Use the AMReX Advection_AmrCore baseline as-is" \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --inputs-file-strategy override \
  --inputs-file-override inputs \
  --indexing-strategy override_static
```

Option 1 (baseline specified + modifications):

```bash
python amrex_agent.py \
  --prompt "AMReX Advection_AmrCore with a 128x128 grid and 3 AMR levels" \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --indexing-strategy override_static \
  --save-workflow
```

## Demo examples

All demo commands live under `demo/`. Highlights:

- AMReX baseline + inputs only: `demo/README.md`
- AMReX baseline + modifications (override_static): `demo/README.md` and `demo/amrex/README.md`
- AMReX prompt file example: `demo/README.md` and `demo/amrex/README.md`
- AMReX config override example: `demo/README.md`
- AMReX simple indexing dry-run: `demo/README.md`
- PeleC simple demo: `demo/pelec/README.md`
- PeleLMeX FlameSheet override (best-known example): `demo/pelelmex/README.md`
- PeleLMeX JetInCrossflow DNS prompt example: `demo/pelelmex/README.md`
- PeleLMeX retry/failure-path example: `demo/example_retry_setups.md`
- ALCF inference endpoint demo (in development): `demo/alcf/README.md`
- Superfacility (SFAPI) Perlmutter demo notes (in development): `demo/superfacility/README.md`

## Tests

Run the core unit suite:

```bash
pytest tests/unit
```

Integration and demo tests live under `tests/integration` and `tests/e2e`.
Some are intentionally skipped or require local solver repos.

## MCP server

AMReXAgent includes an MCP adapter in `mcp_server.py`.
It exposes the AMReXAgent workflow as a tool for external orchestration (early feedback welcome).

## Dependencies and API access

- Full dependency lists are in `environment.yaml` and `utils/environment-frozen.yaml`.
- LLM provider selection, endpoints, and API keys are configured via `src/config.py`
  and optional `--config` overrides (defaults live in `src/config.py`).
- Example configs live in `demo/amrex/config.yaml` and `demo/pelelmex/config_JICF.yaml`.
- Supported providers include CBORG, ALCF, OpenAI, Anthropic, PNNL, and LiteLLM
  (via `CBORG_API_KEY`, `ALCF_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
  `LLM_API_KEY`, `LITELLM_BASE_URL`, optional `LITELLM_API_KEY`).

## Solver configuration pointers

Solver-specific configuration lives in `database/configs/*_config.py`.
Codes with more active development and tuning are reflected there (e.g., AMReX, ERF, PeleC, PeleLMeX).
