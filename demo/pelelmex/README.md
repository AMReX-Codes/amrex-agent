# PeleLMeX Demo Setup

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.

Node choices and graph setup are inspired by Foam-Agent (https://arxiv.org/abs/2509.18178).

---

## Quick start

Run from the repo root (`amrex-agent`).

```bash
cd /path/to/amrex-agent
```

Build PeleLMeX-only schemas and indices:

```bash
export PELELMEX_REPO_PATH=/path/to/PeleLMeX
bash demo/setup_demo_database.sh --code pelelmex --force-rebuild
```

If `database/schemas` and `database/faiss` already contain the prebuilt PeleLMeX artifacts, you can skip this step. Those artifacts are tied to specific code commits; compare the commit hash in `.dependencies.json` with your local repo if you need to validate you’re on the same version. The `--clone-missing` flow uses `.dependencies.json` only to select the fork/branch/commit to clone when repos are missing.
Use `--code pelelmex` for PeleLMeX because setup choices are specific to the repo you are targeting.

---

## Setup variants

Auto-clone missing PeleLMeX repo (requires git + network). Uses recursive clone to pull submodules.

```bash
bash demo/setup_demo_database.sh --code pelelmex --clone-missing
```

Mock embeddings (no API calls):

```bash
bash demo/setup_demo_database.sh --code pelelmex --mock
```

If you prefer running each step explicitly:

```bash
python database/scripts/build_schema.py "$PELELMEX_REPO_PATH" --output database/schemas --auto-compose
python database/scripts/build_all_indices.py --code pelelmex --repo "$PELELMEX_REPO_PATH" --output database/faiss
python database/scripts/build_index.py --config pelelmex --type case_structure --source "$PELELMEX_REPO_PATH" --embedding cborg
python database/scripts/build_index.py --config pelelmex --type case_details --source "$PELELMEX_REPO_PATH" --embedding cborg
```

---

## Jet in crossflow (full requirement example)

This example exercises the full JICF user requirements prompt and is intended to drive boundary condition and chemistry changes.

```bash
python amrex_agent.py \
  --config demo/pelelmex/config_JICF.yaml \
  --prompt-path demo/pelelmex/user_requirements_DNS_isothermal_reacting.txt \
  --run-mode dry \
  --save-workflow \
  --save-transcript \
  --save-log \
  --verbose
```

Expected flag changes (and why):

- `peleLM.do_react = 1` because the prompt explicitly requests a reacting case.
- `peleLM.chem_integrator = ReactorCvode` to enable chemistry integration for reacting flows.
- `peleLM.lo_bc`/`peleLM.hi_bc` should switch wall types to `NoSlipWallIsotherm` because the prompt specifies isothermal walls.

---

## Testing Jet In Cross Flow (short CI example)

Use the short JICF prompt file and the JetInCrossflow case from the JICF-ModCon branch. See the JICF-ModCon branch on Bruce Perry's fork (baperry2/PeleLMeX).

To add the fork as a remote and check out the branch in an existing repo:

```bash
cd /path/to/PeleLMeX
git remote add baperry https://github.com/baperry2/PeleLMeX.git
git fetch baperry
git checkout -b JICF-ModCon baperry/JICF-ModCon
```

```bash
python amrex_agent.py \
  --prompt-path demo/pelelmex/user_requirements_jicf_short.txt \
  --baseline-override PeleLMeX/Exec/Production/JetInCrossflow \
  --indexing-strategy simple \
  --save-workflow \
  --save-transcript \
  --save-log \
  --color-logs always \
  --verbose

Note: this flow expects network access for the LLM provider (default: CBORG).
Expected outputs (dry run): `output/run_<timestamp>/inputs`, `run_local.sh`,
`workflow_history.json`, and `agent_transcript.txt` (no plotfiles generated).
```

---

## Pytest matrix coverage

The PeleLMeX test matrix is exercised via pytest (real services only). These tests are opt-in and require a local PeleLMeX repo plus schemas/indices.

Focused rerun: isothermal_reacting

Pytest:

```bash
pytest tests/integration/test_pelelmex_test_matrix.py -m "e2e and use_real_services" -k "isothermal_reacting and local" --llm-provider cborg --llm-model claude-sonnet-4-5
```

Direct CLI:

```bash
python amrex_agent.py \
  --config demo/pelelmex/config_JICF.yaml \
  --prompt-path demo/pelelmex/user_requirements_DNS_isothermal_reacting.txt \
  --run-mode dry \
  --save-workflow --save-transcript --save-log --verbose
```

Examples:

```bash
pytest tests/integration/test_pelelmex_test_matrix.py -m e2e
```

```bash
pytest tests/integration/test_pelelmex_test_matrix.py -m e2e \
  --llm-provider cborg --llm-model claude-sonnet-4-5
```

```bash
LLM_PRESET=sonnet pytest tests/integration/test_pelelmex_test_matrix.py -m e2e
```

Enable remote targets (Perlmutter/ALCF) explicitly:

```bash
pytest tests/integration/test_pelelmex_test_matrix.py -m e2e --pelelmex-remote \
  --llm-provider alcf --llm-model meta-llama/Meta-Llama-3.1-70B-Instruct
```
