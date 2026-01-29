# ALCF Demo (In Development)

Minimal ALCF setup using the OpenAI-compatible inference endpoint.

## 1) Set environment

```bash
export ALCF_API_KEY=your_access_token
export ALCF_CLUSTER=sophia
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

## 2) Use the config

```bash
python amrex_agent.py --config demo/alcf/config_alcf_test.yaml --prompt "2D advection test"
```
