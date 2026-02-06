# ALCF Demo (In Development)

Minimal ALCF setup using the OpenAI-compatible inference endpoint.

## 1) Set environment

```bash
export ALCF_API_KEY=your_access_token
export ALCF_CLUSTER=sophia
```

If you are using the helper script, export the short-lived token directly:

```bash
export ALCF_API_KEY="$(python inference_auth_token.py get_access_token)"
```

Docs for obtaining tokens + base URLs:

- Inference Endpoints user guide: https://docs.alcf.anl.gov/services/inference-endpoints/
- Auth helper script (source + download): https://github.com/argonne-lcf/inference-endpoints

Quickstart from the docs (download the helper script):

```bash
wget https://raw.githubusercontent.com/argonne-lcf/inference-endpoints/refs/heads/main/inference_auth_token.py
# or
curl -L -o inference_auth_token.py https://raw.githubusercontent.com/argonne-lcf/inference-endpoints/refs/heads/main/inference_auth_token.py
```

Point to a local solver repository (required for baseline overrides):

```bash
export AMREX_REPO_PATH=/path/to/amrex
```

If you need to override the base URL:

```bash
export ALCF_BASE_URL=https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1
```

Tokens expire; use the ALCF helper script to refresh:

```bash
python inference_auth_token.py authenticate
python inference_auth_token.py get_access_token
```

Token notes (per docs):
- Access tokens are valid for 48 hours; `get_access_token` refreshes if needed.
- Re-authentication may be required every 7 days.

## 2) Use the config

```bash
python amrex_agent.py --config demo/alcf/config_alcf_test.yaml --prompt "2D advection test"
```

Model notes:
- Default Sophia model in `config_alcf_test.yaml` is `meta-llama/Meta-Llama-3.1-70B-Instruct` (aligns with CBORG auto-select preference for `llama-3.1-70b-instruct`).
- For Metis, set `llm_model: openai/gpt-oss-120b` and `alcf_cluster: metis`.

## 3) Override-static test path (first-class)

Baseline override only:

```bash
python amrex_agent.py \
  --config demo/alcf/config_alcf_test.yaml \
  --prompt "Use the AMReX Advection_AmrCore baseline as-is" \
  --save-log \
  --verbose
```

Inputs override (explicit file):

```bash
python amrex_agent.py \
  --config demo/alcf/config_alcf_test.yaml \
  --prompt "Use the AMReX Advection_AmrCore baseline as-is" \
  --inputs-file-strategy override \
  --inputs-file-override inputs \
  --save-log \
  --verbose
```

Expected debug signals:
- Logs show `indexing_strategy: override_static` and baseline override selection.
- Logs include `override_static sets disable_embeddings=True by default` (no FAISS or embedding calls).
- Input writer reports the chosen inputs file (override or default).

Notes on AMReX Advection_AmrCore inputs:
- Default selection may pick `inputs-errorfn` (adds `adv.errfn`) depending on strategy.
- The explicit override `--inputs-file-override inputs` removes `adv.errfn` and matches the base `inputs` file.
