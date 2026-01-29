# PeleC Demo

PeleC-specific demo notes and commands.

Node choices and graph setup are inspired by Foam-Agent (https://arxiv.org/abs/2509.18178).

## Setup

Build schema + indices for PeleC:

```bash
bash demo/setup_demo_database.sh --code pelec
```

Ensure the PeleC repo is available (or set `PELEC_REPO_PATH`):

```bash
export PELEC_REPO_PATH=/path/to/PeleC
```

## Run a Simple PeleC Demo

```bash
python amrex_agent.py \
  --prompt "PeleC premixed methane flame simulation with a 64x64 grid" \
  --output-dir /tmp/pele_e2e_runs \
  --indexing-strategy simple \
  --baseline-override PeleC/Exec/RegTests/PMF \
  --dry-run \
  --save-workflow
```

## Additional PeleC Checks

```bash
python ./test_architect_pele_plan.py
```
