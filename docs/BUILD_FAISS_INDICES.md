# Building FAISS Indices - Quick Reference

## Prerequisites

1. **Activate conda environment**:
```bash
conda activate sfapi
```

2. **Set embedding provider API key** (choose one):

**CBORG (Recommended - FREE)**:
```bash
export CBORG_API_KEY="your_key_here"  # Get from https://api.cborg.lbl.gov
```

**OpenAI (Fallback)**:
```bash
export OPENAI_API_KEY="sk-..."
```

**ALCF (OpenAI-compatible, Sophia embeddings)**:
```bash
export ALCF_API_KEY="your_alcf_access_token"
export ALCF_BASE_URL="https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1"
# optional cluster shortcut:
export ALCF_CLUSTER="sophia"
```

**HuggingFace (Local - requires extra install)**:
```bash
conda install -c conda-forge sentence-transformers
# No API key needed
```

## Quick Start

**IMPORTANT**: Run from project root (`amrex-agent/`):

```bash
cd /path/to/amrex-agent
conda activate sfapi
```

### Build PeleC Indices (Recommended)

```bash
# Using CBORG (free, recommended)
python amrex_agent/database/scripts/build_index.py \
    --config pelec \
    --type case_structure \
    --source ~/amrex-repos/PeleC \
    --embedding cborg

python amrex_agent/database/scripts/build_index.py \
    --config pelec \
    --type case_details \
    --source ~/amrex-repos/PeleC \
    --embedding cborg

python amrex_agent/database/scripts/build_index.py \
    --config pelec \
    --type input_templates \
    --source ~/amrex-repos/PeleC \
    --embedding cborg

python amrex_agent/database/scripts/build_index.py \
    --config pelec \
    --type chemistry \
    --embedding cborg
```

### Build PeleLMeX Indices

```bash
python amrex_agent/database/scripts/build_index.py \
    --config pelelmex \
    --type case_structure \
    --source ~/amrex-repos/PeleLMeX \
    --embedding cborg

python amrex_agent/database/scripts/build_index.py \
    --config pelelmex \
    --type case_details \
    --source ~/amrex-repos/PeleLMeX \
    --embedding cborg
```

## Testing (Build Small Index)

Test with limited cases first:

```bash
python amrex_agent/database/scripts/build_index.py \
    --config pelec \
    --type case_structure \
    --source ~/amrex-repos/PeleC \
    --embedding cborg \
    --max-cases 5
```

## Output Location

Indices are saved to:
```
amrex_agent/database/faiss/
├── pelec_case_structure/
├── pelec_case_details/
├── pelec_input_templates/
├── pelec_chemistry/
├── pelelmex_case_structure/
└── pelelmex_case_details/
```

## Publishing + Downloading Artifacts

If you want users to download prebuilt indices, publish the FAISS directory with a manifest.

Build a manifest:
```bash
python database/scripts/build_faiss_manifest.py \
    --faiss-root database/faiss \
    --output database/faiss/manifest.json \
    --embedding-provider cborg \
    --embedding-model text-embedding-3-small
```

Download published artifacts:
```bash
python database/scripts/download_faiss_indices.py --base-url https://your-host/path/to/faiss
```

At runtime, you can set in config:
```
vector_store_backend: faiss_download
vector_store_base_url: https://your-host/path/to/faiss
```

## Embedding Provider Options

| Provider | Command Flag | API Key Required | Cost | Quality |
|----------|--------------|------------------|------|---------|
| CBORG (recommended) | `--embedding cborg` | `CBORG_API_KEY` | FREE | High |
| ALCF (OpenAI-compatible) | `--embedding alcf` | `ALCF_API_KEY` | FREE | High |
| OpenAI | `--embedding openai` | `OPENAI_API_KEY` | $0.02/1M | Highest |
| HuggingFace | `--embedding huggingface` | None | FREE | Medium |

Note: ALCF embeddings use the OpenAI-compatible path above (set `ALCF_BASE_URL` or `ALCF_CLUSTER`).
Default ALCF embedding model is `mistralai/Mistral-7B-Instruct-v0.3-embed` when `embedding_provider: alcf`.

## Troubleshooting

### Error: ModuleNotFoundError
```
ModuleNotFoundError: No module named 'langchain_core'
```
**Solution**: Activate conda environment: `conda activate sfapi`

### Error: CBORG_API_KEY not set
```
Error: CBORG_API_KEY environment variable not set
```
**Solution**: Get key from https://api.cborg.lbl.gov and export it

### Error: No such file or directory
```
FileNotFoundError: [Errno 2] No such file or directory: '~/amrex-repos/PeleC'
```
**Solution**: Use full path or ensure amrex-repos exists:
```bash
# Use full path
--source /home/username/amrex-repos/PeleC

# Or use $HOME
--source $HOME/amrex-repos/PeleC
```

## Help

```bash
python amrex_agent/database/scripts/build_index.py --help
```

## More Information

- Full documentation: `amrex_agent/database/scripts/README.md`
- CBORG setup guide: `amrex_agent/database/scripts/CBORG_SETUP.md`
- Test embeddings: `python amrex_agent/test_embedding_comparison.py`
