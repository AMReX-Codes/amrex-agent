# PeleLMeX Demo Setup

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.

Node choices and graph setup are inspired by Foam-Agent (https://arxiv.org/abs/2509.18178).

Step 0: run from the repo root (`amrex-agent`).

```bash
cd /path/to/amrex-agent
```

Build PeleLMeX-only schemas and indices:

```bash
export PELELMEX_REPO_PATH=/path/to/PeleLMeX
bash demo/setup_demo_database.sh --code pelelmex
```

If `database/schemas` and `database/faiss` already contain the prebuilt PeleLMeX artifacts, you can skip this step. Those artifacts are tied to specific code commits; compare the commit hash in `.dependencies.json` with your local repo if you need to validate you’re on the same version. The `--clone-missing` flow uses `.dependencies.json` only to select the fork/branch/commit to clone when repos are missing.

Auto-clone missing PeleLMeX repo (requires git + network). Uses recursive
clone to pull submodules.

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

## Known Best Example (FlameSheet override)

This is the current best-known demo command for PeleLMeX. It preserves the
domain aspect ratio (dx ≈ dy) and uses a modest timestep count.

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

## Testing Jet In Cross Flow (short CI example)

Use the short JICF prompt file and the JetInCrossflow case from the JICF-ModCon branch.
See the JICF-ModCon branch on Bruce Perry's fork (baperry2/PeleLMeX).

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
