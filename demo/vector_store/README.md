# OpenAI Vector Store Demo

Minimal setup for hosted retrieval using a single shared OpenAI vector store.

See `demo/vector_store/STORES.md` for the current shared/per-code store IDs.

## 1) Set API key + store ID

```bash
export OPENAI_API_KEY=your_key_here
export OPENAI_VECTOR_STORE_ID=vs_6974e35272c0819189f4c2ec47d313d5
```

Optional custom OpenAI endpoint:
```bash
export OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
```

## 2) Upload documents (once per release)

This uploads the same documents used for FAISS indices into a hosted store.

```bash
bash demo/vector_store/upload_openai_vector_store.sh --config all --type all
```

To create a fresh vector store using `text-embedding-3-*` and upload:
```bash
bash demo/vector_store/upload_openai_vector_store.sh --create-store --store-name amrex-agent-all-te3s --embedding-model text-embedding-3-small --config all --type all
```

To create one store per code (names like `amrex-agent-pelec-te3s`):
```bash
bash demo/vector_store/upload_openai_vector_store.sh --create-per-code --store-name amrex-agent-te3s --embedding-model text-embedding-3-small --config all --type all
```

To target a single code:
```bash
bash demo/vector_store/upload_openai_vector_store.sh --config erf --type all --source /path/to/ERF
```

## 3) Use hosted retrieval at runtime

Set in config:
```
vector_store_backend: openai
openai_vector_store_id: vs_6974e35272c0819189f4c2ec47d313d5
```

Now run any demo or `amrex_agent.py` as usual. Retrieval will use the hosted
vector store instead of local FAISS indices.

## ALCF example config

See `demo/alcf/config_alcf_test.yaml` for a minimal ALCF setup that uses ALCF
embeddings and the Sophia cluster default.
