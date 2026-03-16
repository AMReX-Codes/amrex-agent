# AmSC i2 API Demo

Setup for using the American Science Cloud i2 LiteLLM API.

Access portal: the appropriate American Science Cloud API page

## Setup

Quick start:

1. Get API key from your provider portal
2. Set environment variable:
   ```bash
   export AMSC_I2_API_KEY=<your-key>
   export AMSC_I2_BASE_URL=https://<your-amsc-i2-endpoint>/v1
   ```

`amsc-i2` is implemented as an OpenAI-compatible path under the hood. You can
also use `LITELLM_API_KEY` / `LITELLM_BASE_URL` instead of the `AMSC_I2_*`
aliases.

## Usage

```bash
python amrex_agent.py \
  --config demo/amsc-i2/config_amsc_i2.yaml \
  --prompt "AMReX Advection_AmrCore with a 64x64 grid and 2 AMR levels" \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --indexing-strategy override_static
```

Override model:
```bash
python amrex_agent.py \
  --config demo/amsc-i2/config_amsc_i2.yaml \
  --llm-model llama-4-scout \
  --prompt "AMReX Advection_AmrCore with a 64x64 grid and 2 AMR levels" \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --indexing-strategy override_static
```

## Available Models

See available models and pricing in your provider docs.

## FAISS Note

The demo config sets `faiss_semantic_weight: 0.0` because AmSC i2 embedding models (cohere-embed-v4, titan-embed-text-v2, etc.) don't match the models used to build existing FAISS indices (CBORG nomic-embed-text or OpenAI text-embedding-3-small).

To use FAISS with amsc-i2, rebuild indices with compatible embeddings.

## Documentation

- Provider docs and API reference are available from your portal.
