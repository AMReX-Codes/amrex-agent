# CBORG Embeddings Setup Guide

## What is CBORG?

CBORG is LBNL's free embedding service using Nomic embeddings. It's the **recommended** embedding provider for amrex-agent.

**Advantages**:
- ✅ **FREE** at LBNL (no API costs)
- ✅ **8192 token context** (vs 512 for HuggingFace)
- ✅ **768 dimensions** (good quality)
- ✅ **Official OpenAI SDK** (well-maintained)
- ✅ **No local compute** (unlike HuggingFace)

## Setup Instructions

### 1. Get API Key

Visit: https://api.cborg.lbl.gov

Sign up or log in to get your API key.

### 2. Set Environment Variable

```bash
# Add to your ~/.bashrc or ~/.zshrc
export CBORG_API_KEY="your_api_key_here"

# Or set for current session
export CBORG_API_KEY="your_api_key_here"
```

### 3. Verify Setup

Test with the provided comparison script:

```bash
cd amrex_agent
python test_embedding_comparison.py
```

You should see:
```
✅ Status: Working (OFFICIAL SDK)
   Dimensions: 768
   Query time: ~100ms
   Cost: FREE
   Context length: 8192 tokens
```

### 4. Configure amrex-agent

Update `src/config.py` or set environment variable:

```python
# In config.py (already set as default)
embedding_provider: str = "cborg"
```

Or via environment:
```bash
export EMBEDDING_PROVIDER=cborg
```

### 5. Build Indices with CBORG

**IMPORTANT**: Run from project root, not from scripts directory!

Applies to PeleC, PeleLMeX, ERF, WarpX, incflo indices.

```bash
# From project root
cd /path/to/amrex-agent

# Build PeleC indices with CBORG (recommended)
python amrex_agent/database/scripts/build_index.py --config pelec --type case_structure \
    --source ~/amrex-repos/PeleC --embedding cborg

python amrex_agent/database/scripts/build_index.py --config pelec --type case_details \
    --source ~/amrex-repos/PeleC --embedding cborg

python amrex_agent/database/scripts/build_index.py --config pelec --type chemistry --embedding cborg
```

## Implementation Pattern

The code uses the **official OpenAI SDK pattern** (from test_embedding_comparison.py):

```python
import openai
import os

# Configure for CBORG endpoint
openai.api_key = os.environ["CBORG_API_KEY"]
openai.base_url = "https://api.cborg.lbl.gov"

# Embed query (string)
response = openai.embeddings.create(
    model="lbl/nomic-embed-text",
    input=query_text  # STRING
)
embedding = response.data[0].embedding

# Embed documents (list)
response = openai.embeddings.create(
    model="lbl/nomic-embed-text",
    input=[doc1, doc2, doc3]  # LIST
)
embeddings = [item.embedding for item in response.data]
```

### LangChain Integration

We use `langchain_openai.OpenAIEmbeddings` configured for CBORG:

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="lbl/nomic-embed-text",
    openai_api_key=os.environ["CBORG_API_KEY"],
    openai_api_base="https://api.cborg.lbl.gov",
    base_url="https://api.cborg.lbl.gov",
)
```

This gives us:
- ✅ Consistent interface with other embedding providers
- ✅ Automatic retry logic
- ✅ Batch processing
- ✅ Integration with FAISS

## Alternative Embedding Providers

### OpenAI (Fallback)
```bash
export OPENAI_API_KEY="sk-..."
export EMBEDDING_PROVIDER=openai

python build_index.py --config pelec --type case_structure \
    --source ~/amrex-repos/PeleC --embedding openai
```

**Cost**: $0.02 per 1M tokens
**Dimensions**: 1536
**Context**: 8191 tokens

### HuggingFace (Local - NOT RECOMMENDED)

**⚠️ WARNING**: sentence-transformers is **NOT** in environment.yaml

Install first:
```bash
conda install -c conda-forge sentence-transformers
# Or
pip install sentence-transformers langchain-huggingface
```

Then use:
```bash
export EMBEDDING_PROVIDER=huggingface

python build_index.py --config pelec --type case_structure \
    --source ~/amrex-repos/PeleC --embedding huggingface
```

**Limitations**:
- ❌ Only 512 token context (very short)
- ❌ Lower quality than CBORG/OpenAI
- ✅ FREE (local)
- ✅ No API key needed

## Comparison Table

| Provider | Cost | Dimensions | Context | Speed | Quality |
|----------|------|------------|---------|-------|---------|
| **CBORG** (recommended) | FREE | 768 | 8192 | Fast | High |
| OpenAI | $0.02/1M | 1536 | 8191 | Fast | Highest |
| HuggingFace | FREE | 384 | 512 | Medium | Medium |

## Troubleshooting

### Error: CBORG_API_KEY not set
```
Error: CBORG_API_KEY environment variable not set
       Get your key from: https://api.cborg.lbl.gov
```

**Solution**: Set the environment variable (see step 2 above)

### Error: langchain-openai not installed
```
Error: langchain-openai not installed for CBORG
       Install: pip install langchain-openai
```

**Solution**: Already in environment.yaml, just activate environment

### Error: sentence-transformers not found (HuggingFace)
```
Error: HuggingFace embeddings not available
       Missing package: sentence-transformers
```

**Solution**: Install sentence-transformers or use CBORG/OpenAI instead

### CBORG API errors
- Check API key is valid
- Check internet connection
- Try test script: `python test_embedding_comparison.py`

## Performance Tips

1. **Use CBORG for index building**: Free and high quality
2. **Batch documents**: CBORG handles lists efficiently
3. **Cache indices**: Set `faiss_cache_enabled: true` in config
4. **8K context**: CBORG's 8192 tokens handles long input files

## References

- CBORG API: https://api.cborg.lbl.gov
- Test script: `test_embedding_comparison.py`
- Embedding service: `src/services/embedding.py`
- Index builder: `database/scripts/build_index.py`
