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

If `database/schemas` and `database/faiss` already contain the prebuilt ERF artifacts, you can skip this step. The `.dependencies.json` ERF pin remains the recommended commit for reproducible shared runs, but startup preflight does not block on pin mismatch when local schema and FAISS artifacts are valid for your current ERF commit.

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

## Startup readiness preflight prerequisites (ERF)

Zero-manual-setup path:

1. Keep ERF as a sibling repo (`../ERF`) or set `ERF_REPO_PATH`.
2. Run `bash demo/setup_demo_database.sh --code erf`.
3. Run the agent from repo root.

Required behavior and fallback notes:

- Sibling repo autodetect: ERF is discovered from sibling layout first.
- Auto-clone fallback: `bash demo/setup_demo_database.sh --code erf --clone-missing` clones missing ERF using `.dependencies.json`.
- Rebuild/index repair: rerun ERF build commands when schema/index artifacts are stale or mismatched:
  - `bash demo/setup_demo_database.sh --code erf`
- Commit mismatch behavior: preflight warns (does not block) when local artifacts are valid for current ERF HEAD; it blocks only when compatibility is not verified.
- Non-interactive fail-fast: headless startup checks must return non-zero on blocking ERF repo/index/dependency issues.
- CMake-default build note: ERF docs specify `CMAKE_BUILD_TYPE` default `Release` and Release should be preferred for ERF CMake builds.
- Fallback when CMake is unavailable: use GNUmakefile builds (`make ... DEBUG=FALSE`) as the fallback route.
