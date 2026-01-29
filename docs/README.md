# Documentation Notes

This folder contains design and workflow docs for the AMReX agent.

## ALCF Inference (OpenAI-compatible)

Default ALCF base URL (first pass) is the Sophia vLLM endpoint:

```
https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1
```

Set environment variables:

```bash
export ALCF_API_KEY=your_access_token
export ALCF_BASE_URL=https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1
export ALCF_CLUSTER=sophia  # optional shortcut, ignored if ALCF_BASE_URL is set
```

Enable the provider in your config (example):

```yaml
llm_provider: alcf
```

Embedding default for ALCF is `mistralai/Mistral-7B-Instruct-v0.3-embed` unless
you override `alcf_embedding_model` or set a non-default `faiss_embedding_model`.

Tokens expire; use the ALCF helper script to refresh:

```bash
python inference_auth_token.py authenticate
python inference_auth_token.py get_access_token
```
