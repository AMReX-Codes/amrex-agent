# API Keys and OpenAI Usage

This page documents API key setup for supported providers and the OpenAI SDK
usage in the codebase.

## Providers and support

| Provider | Status | Notes |
| --- | --- | --- |
| CBORG | supported | OpenAI-compatible endpoint |
| ALCF | supported | OpenAI-compatible endpoint |
| OpenAI | supported | Direct OpenAI API |
| PNNL | supported | OpenAI-compatible endpoint |
| AmSC i2 | supported | OpenAI-compatible endpoint |
| LiteLLM / self-hosted | supported | Any OpenAI-compatible endpoint (Ollama, vLLM, LiteLLM proxy, LM Studio, an HPC BYOK server, etc.) |
| Anthropic | config only | Provider not implemented in get_llm_client |

## Environment variables

Common:
- `LLM_API_KEY` (PNNL)
- `OPENAI_API_KEY` (OpenAI + OpenAI-compatible endpoints)
- `OPENAI_BASE_URL` (optional, OpenAI-compatible override)
- `OPENAI_VECTOR_STORE_ID` (optional, hosted vector store uploads)

Provider specific:
- `CBORG_API_KEY`
- `ALCF_API_KEY`
- `ALCF_CLUSTER`
- `ALCF_BASE_URL`
- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL`
- `AMSC_I2_API_KEY`
- `AMSC_I2_BASE_URL`
- `ANTHROPIC_API_KEY`

## Config fields

These are defined in `src/config.py`.

- `llm_provider`: `cborg`, `alcf`, `openai`, `anthropic`, `pnnl`, `litellm`, `amsc-i2`
- `llm_model`: provider model name (auto-detected for CBORG if unset)
- `cborg_api_key`, `cborg_base_url`
- `alcf_api_key`, `alcf_cluster`, `alcf_base_url`
- `openai_api_key`, `openai_base_url`
- `anthropic_api_key`
- `pnnl_api_key`, `pnnl_base_url`, `pnnl_default_model`
- `litellm_api_key`, `litellm_base_url` (also used by `amsc-i2`)
- `openai_vector_store_id`, `openai_vector_store_ids`

## Base URL overrides (explicit examples)

OpenAI-compatible override via environment variable:

```bash
export OPENAI_BASE_URL="https://your-openai-compatible-endpoint/v1"
```

OpenAI-compatible override via config:

```yaml
openai_base_url: https://your-openai-compatible-endpoint/v1
```

ALCF override via environment variable:

```bash
export ALCF_BASE_URL="https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1"
```

ALCF override via config:

```yaml
alcf_base_url: https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1
```

## Minimal examples

CBORG:

```bash
export CBORG_API_KEY="cborg-..."
```

```yaml
llm_provider: cborg
llm_model: lbl/Llama-4-Scout-17B-16E-Instruct
```

ALCF:

```bash
export ALCF_API_KEY="alcf-..."
export ALCF_CLUSTER="sophia"
```

```yaml
llm_provider: alcf
llm_model: openai/gpt-oss-120b
```

OpenAI:

```bash
export OPENAI_API_KEY="sk-..."
```

```yaml
llm_provider: openai
llm_model: gpt-4o-mini
```

Anthropic (config only; provider not wired):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

```yaml
llm_provider: anthropic
llm_model: claude-sonnet-4-5
```

PNNL:

```bash
export LLM_API_KEY="pnnl-..."
```

```yaml
llm_provider: pnnl
llm_model: claude-haiku-4-5-20251001-v1-birthright
```

LiteLLM / self-hosted (any OpenAI-compatible endpoint — Ollama, vLLM, LiteLLM proxy, LM Studio, an HPC BYOK server):

```bash
export LITELLM_BASE_URL="http://localhost:<PORT>/v1"
export LITELLM_API_KEY="<token if your endpoint requires one; else 'litellm'>"
export LITELLM_MODEL="<model id your endpoint exposes>"
```

```yaml
llm_provider: litellm
llm_model: <model id your endpoint exposes>
litellm_base_url: http://localhost:<PORT>/v1
```

`llm_provider` and `embedding_provider` are plain fields on `AMReXAgentConfig` with no env-var fallback, so the YAML must be supplied via the `--config` flag. `LITELLM_*` env vars above are honoured directly because those specific fields use `default_factory=lambda: os.getenv(...)`.

```bash
python amrex_agent.py --prompt "..." --config path/to/local.yaml
```

Unset any other provider key (e.g. `CBORG_API_KEY`) in your environment so `get_llm_client()` fails fast against the local endpoint instead of silently falling back. LangGraph flows require the endpoint to support OpenAI `tools`/`tool_choice` and emit well-formed `tool_calls` responses. If the endpoint does not expose `/v1/embeddings`, set `embedding_provider: huggingface` so `sentence-transformers` runs embeddings locally (`pip install sentence-transformers langchain-huggingface`).

NLR Kestrel via the OnField Assistant (`ofa`) BYOK server ([onfield-assistant](https://github.com/nileshsawant/onfield-assistant)):

```bash
module load assistant
ofa --serve --serve-enable-tools
export LITELLM_BASE_URL="http://localhost:$(cat $OFA_SCRATCH/.ofa_serve_port)/v1"
export LITELLM_API_KEY="$(cat $OFA_SCRATCH/.ofa_api_key)"
export LITELLM_MODEL="ofa-code"
unset CBORG_API_KEY
```

```yaml
llm_provider: litellm
llm_model: ofa-code
embedding_provider: huggingface
```

```bash
python amrex_agent.py --prompt "..." --config ~/.amrex_agent/kestrel-ofa.yaml
```

AmSC i2 (American Science Cloud):

```bash
export AMSC_I2_API_KEY="..."
export AMSC_I2_BASE_URL="https://<your-amsc-i2-endpoint>/v1"
```

```yaml
llm_provider: amsc-i2
llm_model: claude-sonnet-4-5
```

`amsc-i2` uses the same OpenAI-compatible client path as `litellm` under the
hood. `LITELLM_API_KEY` / `LITELLM_BASE_URL` can be used as equivalents.

Hosted OpenAI vector store upload:

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_VECTOR_STORE_ID="vs_..."
bash demo/vector_store/upload_openai_vector_store.sh --config all --type all
```

## Demo references

- `demo/README.md` (general demo setup, OpenAI upload examples)
- `demo/vector_store/README.md` (hosted OpenAI vector store)
- `demo/alcf/README.md` (ALCF OpenAI-compatible endpoint)
- `demo/pnnl/README.md` (PNNL setup and config)
- `demo/amsc-i2/README.md` (AmSC i2 setup and config)

## OpenAI SDK usage (functions and call sites)

OpenAI client construction:
- `OpenAI(api_key=..., base_url=...)` in `src/config.py`,
  `src/services/config_service.py`, `src/services/vector_store_backends.py`,
  `database/scripts/upload_openai_vector_store.py`

Model discovery:
- `client.models.list()` in `src/config.py` (CBORG auto-detect)

Chat completions:
- `client.chat.completions.create(...)` in
  `src/nodes/analysis_node.py`, `src/nodes/reviewer_node.py`,
  `src/services/architect.py`, `src/services/cases.py`,
  `src/services/config_model_factory.py`, `src/services/inputs_file_selector.py`,
  `src/services/knowledge.py`

Hosted vector store:
- `client.vector_stores.create(...)` in `database/scripts/upload_openai_vector_store.py`
- `client.files.create(file=..., purpose="assistants")` in
  `database/scripts/upload_openai_vector_store.py`
- `client.vector_stores.files.create(vector_store_id=..., file_id=...)` in
  `database/scripts/upload_openai_vector_store.py`

Embeddings (langchain-openai, not OpenAI SDK direct):
- `OpenAIEmbeddings(...)` in `src/services/embedding_factory.py`
