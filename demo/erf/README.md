# ERF Demo Setup

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.

Step 0: run from the repo root (`amrex-agent`).

```bash
cd /path/to/amrex-agent
```

Build ERF-only schemas and indices:

```bash
export ERF_REPO_PATH=/path/to/ERF
bash demo/setup_demo_database.sh --code erf
```

Auto-clone missing ERF repo (requires git + network):

```bash
bash demo/setup_demo_database.sh --code erf --clone-missing
```

Mock embeddings (no API calls):

```bash
bash demo/setup_demo_database.sh --code erf --mock
```

If you prefer explicit commands:

```bash
python database/scripts/build_schema.py "$ERF_REPO_PATH" --output database/schemas --auto-compose
python database/scripts/build_all_indices.py --code erf --repo "$ERF_REPO_PATH" --output database/faiss
python database/scripts/build_index.py --config erf --type case_structure --source "$ERF_REPO_PATH" --embedding cborg
python database/scripts/build_index.py --config erf --type case_details --source "$ERF_REPO_PATH" --embedding cborg
```
