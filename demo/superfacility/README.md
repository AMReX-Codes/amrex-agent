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

To obtain a client key, follow the NERSC SFAPI client instructions:
```
https://docs.nersc.gov/services/sfapi/authentication/#client
```

Adapted from Synapse’s walkthrough:
```
https://github.com/BLAST-AI-ML/synapse/blob/main/dashboard/README.md#how-to-get-the-superfacility-api-credentials
```

Steps (adapted):
1) Log in to https://iris.nersc.gov/profile
2) Open the menu under your username, then find “Superfacility API Clients”
3) Click “New Client”
4) Choose a client name, pick your **own NERSC username** for “User”
5) Select **Red** security level (required for private key auth)
6) Choose an IP preset (“Your IP” for local use or “Spin” for Spin)
7) Download the PEM key and **prepend your client ID on the first line**
8) `chmod 600 priv_key.pem`
9) Place the key under `~/.superfacility/` (e.g., `~/.superfacility/priv_key.pem`)

If you need the exact PEM format guidance, see the sfapi_client docs:
```
https://nersc.github.io/sfapi_client/quickstart/#storing-keys-in-files
```

Example: merge `clientid.txt` + downloaded `priv_key.pem` into the expected format:

```bash
cp ~/.superfacility/priv_key.pem ~/.superfacility/priv_key.pem.no_client_id
{
  cat ~/.superfacility/clientid.txt
  printf "\n"
  cat ~/.superfacility/priv_key.pem.no_client_id
} > ~/.superfacility/priv_key.pem
chmod 600 ~/.superfacility/priv_key.pem
```

### Option B: REST token

```bash
export NERSC_API_TOKEN=your_token
# or SFAPI_TOKEN=your_token
```

## Config templates

Start with one of the configs in this folder and update the paths:

- `config_perlmutter_login_node.yaml`: run on Perlmutter with local CFS paths
- `config_perlmutter_remote.yaml`: stage from another host to Perlmutter via SFAPI

Synapse-style shared layout (example):
`/global/cfs/cdirs/$PROJECT/$USER/superfacility`

## Example command

```bash
# export PROJECT=m4106
python amrex_agent.py \
  --prompt "Run AMReX Advection_AmrCore using the default inputs file without changes." \
  --config demo/superfacility/config_perlmutter_remote.yaml \
  --environment perlmutter
```

## Notes

- The SFAPI path assumes the executable and inputs are already on Perlmutter.
- The generated submission script uses `srun` (no container).
- If `sfapi_client` is unavailable, the code falls back to REST token auth.
