# Documentation Notes

This folder contains design and workflow docs for the AMReX agent.

## Python standards (docs, packaging, tests/examples)

### Documentation tooling

Decision: use MkDocs with the built-in Read the Docs theme for a light, fast
site that can be hosted on ReadTheDocs when ready.

Local build:

```bash
mkdocs serve
```

ReadTheDocs plan:
- Add a `readthedocs.yml` that points at `mkdocs.yml`.
- Use Python 3.11 in RTD to match `pyproject.toml`.
- Install docs deps via a small `docs/requirements.txt` when publishing.

### Packaging strategy

- Use `conda` (conda-forge) as the source of truth for compiled dependencies.
- Use `pip install -e .` for editable installs of the repo itself.
- Prefer lower bounds in `environment.yaml` and avoid upper bounds unless
  there is a known incompatibility.
- See also: dependencies_update_policy.md

### Tests/examples

- Add tests under `tests/` and update `tests/README.md` if you introduce new
  markers or workflows.
- Add example workflows under `demo/` and include a short README for each
  new scenario.

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

## LiteLLM Proxy (OpenAI-compatible)

LiteLLM works via the OpenAI-compatible proxy API. Set env vars:

```bash
export LITELLM_BASE_URL=http://localhost:4000/v1
export LITELLM_API_KEY=your_key_here  # optional, proxy-specific
export LITELLM_MODEL=gpt-4o-mini
```

Enable the provider in your config (example):

```yaml
llm_provider: litellm
llm_model: gpt-4o-mini
```

Structured outputs via `instructor` should work if the proxy returns
OpenAI-compatible response shapes.
