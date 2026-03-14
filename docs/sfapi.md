# Superfacility API (SFAPI) Usage

This page documents the full SFAPI workflow beyond the demo README. It covers
auth, staging, submission, monitoring, and the relevant config fields.

## When to use SFAPI

Use SFAPI when you want AMReXAgent to submit and monitor jobs on NERSC
Perlmutter from either:
- a Perlmutter login node (no staging needed), or
- a non-NERSC host (stage inputs/executables to CFS, then submit remotely).

## Prerequisites

- NERSC Perlmutter access.
- A CFS path for run data, e.g. `/global/cfs/cdirs/$SBATCH_ACCOUNT/$USER/superfacility`.
- SFAPI credentials (client key or REST token).

Optional but recommended:
- `sfapi_client` installed in your environment.

## Authentication options

### Option A: sfapi_client PEM (recommended)

Use a PEM file where the first line is the client ID and the remaining lines
are the private key. Then set one of:

```bash
export SFAPI_KEY_PATH=/path/to/priv_key.pem
# or SUPERFACILITY_KEY_PATH / NERSC_SFAPI_KEY_PATH
```

AMReXAgent will also search `~/.superfacility/*.pem`, `~/.superfacility/priv_key.pem`,
and `~/sfapi/priv_key.pem`.

If you want to pass credentials explicitly, you can set:

```bash
export SUPERFACILITY_CLIENT_ID=your_client_id
export SUPERFACILITY_SECRET='-----BEGIN PRIVATE KEY----- ...'
```

### Option B: REST token

Use a token when `sfapi_client` is not available or for REST uploads/downloads:

```bash
export NERSC_API_TOKEN=your_token
# or SFAPI_TOKEN=your_token
```

Token discovery also checks `~/.nersc/token`, `~/.config/nersc/token`,
and `~/.superfacility/token`.

## Core configuration fields

These live in `src/config.py` and can be set in a YAML config override.

- `environment`: set to `perlmutter` to enable SFAPI logic.
- `superfacility_account`: defaults to `SBATCH_ACCOUNT` or `amsc014`.
- `remote_output_dir`: CFS destination for staged runs (defaults to `output_dir`).
- `remote_run_dir`: fixed remote run directory (overrides `remote_output_dir/run_name`).
- `remote_executable_path`: absolute path to prebuilt executable on Perlmutter.
- `remote_executable_template`: template for finding an executable on CFS.
- `remote_executable_find`: enable discovery of a `*.ex` under a remote case dir.
- `remote_staging_method`: `auto`, `sfapi_client`, or `rest_upload`.
- `monitor_job`: monitor until completion (default: true).
- `stage_out_outputs`: download logs + latest plotfile (default: true).
- `run_mode`: `dry`, `stage`, `submit`, or `full`.

Template variables supported by `remote_executable_template`:
`{case_dir}`, `{case_dir_name}`, `{repo_name}`, `{solver_name}`.

## How staging is decided

Remote staging is inferred when:
- `environment` is `perlmutter`, and
- the current host is not Perlmutter.

In that case, AMReXAgent stages the local run directory to a remote CFS path
before submission. On Perlmutter, no staging occurs and `output_dir` is used
directly.

## Submission flow

AMReXAgent generates `submit.sh` in the run directory and chooses a submission
path in this order:

1) `sfapi_client` submission (requires client ID + private key).
2) REST submission (requires token or OAuth session).
3) `sbatch` fallback (only works on Perlmutter with Slurm available).

Monitoring uses `sfapi_client` when available, otherwise REST.

## Allocation and API use (token flow)

If you authenticate with a Superfacility API token (`NERSC_API_TOKEN` or
`SFAPI_TOKEN`), AMReXAgent uses the REST endpoints below:

- Upload (staging + mkdir): `https://api.nersc.gov/api/v1.2/utilities/upload/{system}`
- Download (stage-out): `https://api.nersc.gov/api/v1.2/utilities/download/{system}`
- List remote directory: `https://api.nersc.gov/api/v1.2/utilities/ls/{system}/{remote_dir}`
- Submit job script: `https://api.nersc.gov/api/v1.2/compute/jobs/{system}`
- Poll job status: `https://api.nersc.gov/api/v1.2/compute/jobs/perlmutter/{job_id}`

The workflow uses these endpoints as follows:
- Staging: uploads the run directory to `remote_run_dir` (and may create
  `remote_run_dir` by uploading a `.keep` file).
- Submission: posts the SLURM script contents (or a path if staged).
- Monitoring: polls the job status until completion.
- Stage-out: downloads logs and the newest plotfile from the remote run dir.

Job allocation details (nodes/time) are encoded in the generated SLURM script:
- `nodes`: derived from `config.mpi_ranks` when the Runner node submits
  (default: 1).
- `walltime`: defaults to `00:10:00` unless you call `SuperfacilityRunner.submit`
  directly with a different value.
- `qos`: defaults to `regular`.
- `constraint`: defaults to `gpu&hbm40g`.
- `account`: uses `config.superfacility_account`, which defaults to
  `SBATCH_ACCOUNT` (or `amsc014` if unset).

To override these values today, call `SuperfacilityRunner.submit(...)` with
explicit `nodes`, `walltime`, `qos`, or `constraint`, or adjust `mpi_ranks` and
`superfacility_account` in your config.

MCP note: the MCP adapter (`mcp_server.py`) reads `submit` fields from the
payload in `mcp_run_simulation` and defaults to `nodes=1`,
`walltime=00:10:00`, `qos=regular`, `constraint=gpu&hbm40g`, with
`dry_run=true` unless overridden.

## Remote executable resolution

When staging from a non-Perlmutter host, AMReXAgent can skip local compilation
and resolve an existing executable on Perlmutter:

- `remote_executable_path`: use this exact path.
- `remote_executable_template`: render a case-specific path on CFS.
- `remote_executable_find`: scan a remote case directory for a `*.ex`
  (prefers CUDA/MPI naming).

If none of these are set, AMReXAgent attempts a default CFS layout:
`/global/cfs/cdirs/$SBATCH_ACCOUNT/$USER/<repo_name>/<case_dir>`.

## Example: Perlmutter login node

```bash
python amrex_agent.py \
  --prompt "Run AMReX Advection_AmrCore with default inputs." \
  --config demo/superfacility/config_perlmutter_login_node.yaml \
  --environment perlmutter
```

## Example: remote staging from another host

```bash
python amrex_agent.py \
  --prompt "Run AMReX Advection_AmrCore with default inputs." \
  --config demo/superfacility/config_perlmutter_remote.yaml \
  --environment perlmutter \
  --run-mode full
```

## Run modes

- `dry`: generate scripts only.
- `stage`: stage inputs/executable, no submit.
- `submit`: submit the job (staging still happens if it is inferred), no monitoring.
- `full`: stage (if inferred), submit, and monitor until completion.

## Troubleshooting

- `Missing SFAPI client credentials`: set `SFAPI_KEY_PATH` or
  `SUPERFACILITY_CLIENT_ID` + `SUPERFACILITY_SECRET`.
- `sfapi_client not available`: install `sfapi_client` or rely on REST token
  auth via `NERSC_API_TOKEN` / `SFAPI_TOKEN`.
- `Remote run directory not found`: create it on Perlmutter or set
  `remote_staging_method: rest_upload` (auto uses REST to create `.keep`).
- `No executable found`: set `remote_executable_path` or
  `remote_executable_template`, or ensure a `*.ex` exists under the remote case.
- `sbatch not found in PATH`: load Slurm modules or submit via SFAPI.
- Stage-out fails: ensure a REST token or OAuth session is available for
  downloads (`~/.nersc/token` or `NERSC_API_TOKEN`).

## Runtime intent interaction

When `perlmutter` is requested via runtime intent, runner performs a read-only
remote filesystem probe before execution. If the probe fails, execution falls
back to `local` and records the adjustment in workflow history.

For full precedence and gating behavior, see `docs/intent_runtime_routing.md`.

## Related references

- Demo configs: `demo/superfacility/`
- Demo notes: `demo/superfacility/README.md`

## Globus stage-out (MCP)

If you use the MCP `stage_out_globus` tool, it will build a Globus CLI transfer
command. Default endpoints are preconfigured for common NERSC→ALCF transfers:

- Source (NERSC DTN): `9d6d994a-6d04-11e5-ba46-22000b92c6ec`
- Destination (ALCF): `05d2c76a-e867-4f67-aa57-76edeb0beda0`

Override these by passing `globus.source_endpoint` / `globus.destination_endpoint`
in the tool payload or by setting `GLOBUS_SRC_ENDPOINT` / `GLOBUS_DST_ENDPOINT`.
