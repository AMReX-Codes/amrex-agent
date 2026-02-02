# Superfacility (SFAPI) Demo

Notes and example configuration for submitting AMReXAgent runs to NERSC via SFAPI.

## Prerequisites

- Access to NERSC Perlmutter
- SFAPI credentials (either a token or a client key)
- AMReX repo available on a Perlmutter-visible filesystem

## Credentials

### Option A: sfapi_client (recommended)

Use a PEM key file where the **first line is the client ID** and the remaining
lines are the private key. Then set one of:

```bash
export SFAPI_KEY_PATH=/path/to/priv_key.pem
# or SUPERFACILITY_KEY_PATH / NERSC_SFAPI_KEY_PATH
```

### Option B: REST token

```bash
export NERSC_API_TOKEN=your_token
# or SFAPI_TOKEN=your_token
```

## Config template

Start with `config_perlmutter.yaml` in this folder and update the paths:

- `amrex_repo_path`: Perlmutter AMReX repo path
- `output_dir`: where runs and scripts should be staged

Synapse-style shared layout (example):
`/global/cfs/cdirs/$PROJECT/$USER/superfacility`

## Example command

```bash
python amrex_agent.py \
  --prompt "AMReX Advection_AmrCore with a 64x64 grid" \
  --config demo/superfacility/config_perlmutter.yaml \
  --environment perlmutter \
  --dry-run
```

## Notes

- The SFAPI path assumes the executable and inputs are already on Perlmutter.
- The generated submission script uses `srun` (no container).
- If `sfapi_client` is unavailable, the code falls back to REST token auth.
