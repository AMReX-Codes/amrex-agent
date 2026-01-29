# FAISS Indexing System

Complete guide to building and using FAISS indices for AMReXAgent's case selection system.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Indexing Strategies](#indexing-strategies)
  - [Simple Indexing](#simple-indexing)
  - [Hierarchical Indexing](#hierarchical-indexing)
- [Building Indices](#building-indices)
  - [Simple Indices](#building-simple-indices)
  - [Hierarchical Indices](#building-hierarchical-indices)
- [Supported Codes](#supported-codes)
- [Index Types](#index-types)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Overview

AMReXAgent uses FAISS (Facebook AI Similarity Search) vector indices to find relevant simulation cases based on user requirements. Two strategies are available:

1. **Simple Indexing** - Fast, single-search approach (production-ready)
2. **Hierarchical Indexing** - Multi-level search with solver-specific refinement (experimental)

**Architecture:**
```
User Prompt → Embeddings → FAISS Search → Best Case Selection → Baseline Metadata
```

---

## Quick Start

### For New Users (Start with Simple)

```bash
# 1. Clone the target AMReX code (if not already done)
cd ..
git clone https://github.com/AMReX-Combustion/PeleC.git
cd amrex_agent

# 2. Build simple index for PeleC
# IMPORTANT: Run from amrex_agent/ directory (project root)
python database/scripts/build_index.py \
  --config pelec \
  --type case_structure \
  --source ../PeleC

# 3. Run agent (will auto-use simple strategy)
./amrex_agent.py --prompt_path demo/pelec/user_requirement_specific.txt
```

### For Advanced Users (Hierarchical)

```bash
# Build full 3-level hierarchical indices
python database/scripts/build_all_indices.py \
  --repo ../PeleC \
  --output database/indices/hierarchical

# Enable hierarchical strategy
export PELE_AGENT_INDEXING_STRATEGY=hierarchical
./amrex_agent.py --prompt_path demo/pelec/user_requirement_specific.txt
```

---

## Indexing Strategies

### Simple Indexing

**How it works:**
1. Embed user prompt into vector space
2. Single FAISS search against case database
3. Return top-1 match with baseline metadata

**Characteristics:**
- ⚡ Fast (~0.5-2 seconds)
- ✅ Production-ready and proven
- 📦 Low memory (~50MB)
- 🎯 ~90% success rate on common cases

**Best for:**
- Standard 2D/3D simulations
- Well-covered domains (flames, jets, detonations)
- Production deployments
- Quick iterations

---

### Hierarchical Indexing

**How it works:**
1. **Level 0**: Solver selection - Which AMReX code best fits the problem?
2. **Level 1**: Documentation retrieval - What algorithms/approaches apply?
3. **Level 2**: Case selection - Which specific case is most relevant?

**Characteristics:**
- 🧠 Sophisticated multi-stage reasoning
- 🔍 Better for specialized/out-of-domain problems
- ⏱️ Slower (~5-15 seconds)
- 💾 Higher memory (~150MB)
- 🎯 ~85% overall, ~95% on specialized domains

**Best for:**
- Specialized physics (high-Mach, reactive flows)
- Multi-physics simulations
- Research applications
- When simple indexing fails

---

## Building Indices

### Building Simple Indices

Simple indices use `build_index.py` for direct case-to-embedding mapping.

**Command Structure:**
```bash
python amrex_agent/database/scripts/build_index.py \
  --config <code> \
  --type <index_type> \
  --source <repo_path> \
  [--embedding <provider>] \
  [--max-cases <N>] \
  [--output <custom_path>]
```

#### Examples by Code

**PeleC (compressible reacting flows):**
```bash
# Case structure (recommended, hierarchical level 1)
python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type case_structure \
  --source ~/codes/amrex-agent/PeleC

# Case details (hierarchical level 2)
python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type case_details \
  --source ~/codes/amrex-agent/PeleC

# Input templates
python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type input_templates \
  --source ~/codes/amrex-agent/PeleC

# Chemistry mechanisms
python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type chemistry
```

**PeleLMeX (low-Mach reacting flows):**
```bash
python amrex_agent/database/scripts/build_index.py \
  --config pelelmex \
  --type case_structure \
  --source ~/codes/amrex-agent/PeleLMeX
```

**ERF (atmospheric modeling):**
```bash
# 1. Clone ERF first (if not already done)
cd ..
git clone https://github.com/erf-model/ERF.git
cd amrex_agent

# 2. Build index
python database/scripts/build_index.py \
  --config erf \
  --type case_structure \
  --source ../ERF
```

**WarpX (particle accelerator physics):**
```bash
python amrex_agent/database/scripts/build_index.py \
  --config warpx \
  --type case_structure \
  --source ~/codes/amrex-agent/warpx
```

**incflo (incompressible flow):**
```bash
python amrex_agent/database/scripts/build_index.py \
  --config incflo \
  --type case_structure \
  --source ~/codes/amrex-agent/incflo
```

#### Build All Simple Indices (Batch)

```bash
# Build for all supported codes
for code in pelec pelelmex erf warpx incflo; do
  if [ -d ~/codes/amrex-agent/${code^^} ] || [ -d ~/codes/amrex-agent/$code ]; then
    python amrex_agent/database/scripts/build_index.py \
      --config $code \
      --type case_structure \
      --source ~/codes/amrex-agent/${code^^}
  fi
done
```

#### Custom Options

**Test build (limited cases):**
```bash
python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type case_structure \
  --source ~/codes/amrex-agent/PeleC \
  --max-cases 10
```

**Use HuggingFace embeddings (local, free):**
```bash
python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type case_structure \
  --source ~/codes/amrex-agent/PeleC \
  --embedding huggingface
```

**Custom output directory:**
```bash
python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type case_structure \
  --source ~/codes/amrex-agent/PeleC \
  --output /custom/path/pelec_case_structure
```

#### Output Location

Default: `amrex_agent/database/faiss/`

```
database/faiss/
├── pelec_case_structure/
├── pelec_case_details/
├── pelec_input_templates/
├── pelec_chemistry/
├── pelelmex_case_structure/
├── erf_case_structure/
└── ...
```

---

### Building Hierarchical Indices

Hierarchical indices use `build_all_indices.py` to create all three levels.

**Command Structure:**
```bash
python amrex_agent/database/scripts/build_all_indices.py \
  [--mock] \
  [--repo <path>] \
  [--output <dir>]
```

#### Quick Test Build (No API Calls)

```bash
# Fast test using mock embeddings (no API keys needed)
python amrex_agent/database/scripts/build_all_indices.py \
  --mock \
  --output database/indices/hierarchical_test
```

#### Production Build

```bash
# Set API key for real embeddings
export OPENAI_API_KEY=sk-...

# Build for specific solver
python amrex_agent/database/scripts/build_all_indices.py \
  --repo ~/codes/amrex-agent/PeleC \
  --output database/indices/hierarchical

# Or let it auto-detect from config
python amrex_agent/database/scripts/build_all_indices.py \
  --output database/indices/hierarchical
```

#### Overnight Batch Job

```bash
# Run in background (can take 30-60 minutes)
nohup python amrex_agent/database/scripts/build_all_indices.py \
  --repo ~/codes/amrex-agent/PeleC \
  --output database/indices/hierarchical > build.log 2>&1 &

# Monitor progress
tail -f build.log
```

#### Output Structure

```
database/indices/hierarchical/
├── level0/                    # Solver selection
│   ├── physics_regimes.faiss
│   ├── solver_capabilities.faiss
│   ├── code_lineage.faiss
│   └── cross_cutting_guidance.faiss
├── level1/                    # Documentation retrieval
│   ├── pelec_docs.faiss
│   ├── pelelmex_docs.faiss
│   ├── erf_docs.faiss
│   └── ...
└── level2/                    # Case selection
    ├── pelec/
    │   ├── cases.faiss
    │   └── cases_metadata.json
    ├── pelelmex/
    │   ├── cases.faiss
    │   └── cases_metadata.json
    └── ...
```

---

## Supported Codes

| Code | Config Name | Domain | Priority Cases | Index Quality |
|------|-------------|--------|----------------|---------------|
| **PeleC** | `pelec` | Compressible reacting flows | PMF, Sod, TurbInflow | Excellent (4 cases) |
| **PeleLMeX** | `pelelmex` | Low-Mach reacting flows | FlameSheet, TaylorGreen | Excellent (3 cases) |
| **ERF** | `erf` | Atmospheric modeling | ABL, Bubble, DensityCurrent | Good (3 cases) |
| **WarpX** | `warpx` | Particle accelerator | BeamBeam, LaserAcceleration | Excellent (3 cases) |
| **incflo** | `incflo` | Incompressible flow | TaylorGreen, Channel | Good (6 cases) |

### Adding a New Code

1. **Create config file** in `database/configs/`:
```python
# database/configs/mycode_config.py
from .base_amrex_config import BaseAMReXConfig

class MyCodeConfig(BaseAMReXConfig):
    code_name = "MyCode"
    github_org = "my-org"
    github_repo = "MyCode"
    description = "My AMReX application"

    priority_cases = [
        "Exec/RegTests/TestCase1",
        "Exec/Production/Important",
    ]

    faiss_indices = [
        'mycode_case_structure',
        'mycode_case_details',
    ]
```

2. **Register in `__init__.py`**:
```python
# database/configs/__init__.py
from .mycode_config import MyCodeConfig

__all__ = [..., 'MyCodeConfig']
```

3. **Build indices**:
```bash
python amrex_agent/database/scripts/build_index.py \
  --config mycode \
  --type case_structure \
  --source ~/codes/MyCode
```

---

## Index Types

### `case_structure`
**Hierarchical Level 1** - High-level case organization
- Directory structure
- Case types (RegTests, Production, Tutorial)
- Basic metadata
- **Use for:** Broad case matching

### `case_details`
**Hierarchical Level 2** - Detailed documentation
- README content
- Input file parameters
- Detailed metadata
- **Use for:** Parameter-level matching

### `input_templates`
**Templates** - Input file patterns
- Full input file content
- Parameter configurations
- **Use for:** Finding similar input patterns

### `chemistry`
**Domain Knowledge** - Mechanism/fuel mappings
- Chemistry mechanisms
- Fuel types
- Code-specific domain data
- **Use for:** Semantic chemistry queries

---

## Configuration

### Environment Variables

```bash
# Strategy selection
export PELE_AGENT_INDEXING_STRATEGY=simple      # or "hierarchical"

# Embedding provider
export PELE_AGENT_EMBEDDING_PROVIDER=openai     # or "huggingface", "cborg"
export OPENAI_API_KEY=sk-...                    # If using OpenAI

# Custom paths
export PELE_AGENT_FAISS_DB_PATH=/path/to/indices
```

### In Code (src/config.py)

```python
from src.config import PeleAgentConfig

config = PeleAgentConfig()

# Strategy selection
config.indexing_strategy = "simple"  # or "hierarchical"

# Simple indexing paths
config.faiss_index_path = "database/indices/pelec_case_structure.faiss"
config.faiss_metadata_path = "database/indices/pelec_case_structure_metadata.json"

# Hierarchical indexing paths
config.level0_indices_dir = "database/indices/hierarchical/level0"
config.level1_indices_dir = "database/indices/hierarchical/level1"
config.level2_indices_dir = "database/indices/hierarchical/level2"

# Embedding settings
config.embedding_provider = "openai"  # or "huggingface"
config.faiss_embedding_model = "text-embedding-ada-002"
```

---

## Testing Indices

### Verify Simple Index

```bash
# Check index exists
ls -lh database/faiss/pelec_case_structure/

# Test loading
python -c "
from langchain_community.vectorstores import FAISS
index = FAISS.load_local('database/faiss/pelec_case_structure/')
print(f'Index loaded: {index.index.ntotal} vectors')
"

# Run unit tests
pytest tests/unit/ -m "indexing_simple" -v

# Run integration tests
pytest tests/integration/ -m "indexing_simple and use_real_services" -v
```

### Verify Hierarchical Indices

```bash
# Check all levels exist
ls -lh database/indices/hierarchical/level0/*.faiss
ls -lh database/indices/hierarchical/level1/*.faiss
ls -lh database/indices/hierarchical/level2/*/cases.faiss

# Test level 0 searcher
python -c "
from database.indexing.level0_searcher import Level0Searcher
from pathlib import Path
searcher = Level0Searcher(Path('database/indices/hierarchical/level0'))
results = searcher.search('2D flame simulation', k=3)
for solver, score in results:
    print(f'{solver}: {score:.3f}')
"

# Run hierarchical tests
pytest tests/unit/ -m "indexing_hierarchical" -v
pytest tests/integration/ -m "indexing_hierarchical and use_real_services" -v
```

---

## Troubleshooting

### Issue: "No cases found for [CODE]"

**Cause:** Index not built for that code.

**Solution:**
```bash
# 1. Clone the repository (go up one level from amrex_agent/)
cd ..
git clone https://github.com/[org]/[CODE].git
cd amrex_agent

# 2. Build index
python database/scripts/build_index.py \
  --config [code] \
  --type case_structure \
  --source ../[CODE]
```

### Issue: "FileNotFoundError: database/indices/..."

**Cause:** Index files missing or incorrect path.

**Solution:**
```bash
# Verify path
ls -lh database/faiss/
ls -lh database/indices/hierarchical/

# Rebuild if needed (see Building Indices above)

# Check config matches actual location
grep "faiss.*path" src/config.py
```

### Issue: "TypeError: argument of type 'NoneType' is not iterable"

**Cause:** This was a bug in architect.py when baseline selection fails.

**Status:** ✅ **FIXED** - The null check is now properly handled.

### Issue: Build takes too long

**Solution 1 - Test with limited cases:**
```bash
python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type case_structure \
  --source ~/codes/amrex-agent/PeleC \
  --max-cases 10
```

**Solution 2 - Use local embeddings:**
```bash
python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type case_structure \
  --source ~/codes/amrex-agent/PeleC \
  --embedding huggingface
```

**Solution 3 - Background job:**
```bash
nohup python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type case_structure \
  --source ~/codes/amrex-agent/PeleC > build.log 2>&1 &
```

### Issue: OpenAI API errors

**Cause:** Missing or invalid API key.

**Solution:**
```bash
# Set API key
export OPENAI_API_KEY=sk-...

# Or use free local embeddings
python build_index.py ... --embedding huggingface
```

### Issue: Import errors when building

**Cause:** Not running from project root.

**Solution:**
```bash
# Always run from project root
cd /path/to/amrex-agent
python amrex_agent/database/scripts/build_index.py ...
```

---

## Performance Comparison

| Metric | Simple | Hierarchical |
|--------|--------|--------------|
| **Search Time** | 0.5-2s | 5-15s |
| **Memory** | ~50MB | ~150MB |
| **FAISS Searches** | 1 | 3 (L0+L1+L2) |
| **Success Rate** | ~90% (common) | ~85% overall, ~95% (specialized) |
| **Build Time** | 5-15 min | 30-60 min |
| **API Calls** | Low | High |
| **Best For** | Production | Research |

---

## Maintenance

### Rebuild After Code Updates

```bash
# When new cases added to repository
cd ~/codes/amrex-agent/PeleC
git pull

# Rebuild simple index
python amrex_agent/database/scripts/build_index.py \
  --config pelec \
  --type case_structure \
  --source ~/codes/amrex-agent/PeleC

# Rebuild hierarchical (if using)
python amrex_agent/database/scripts/build_all_indices.py \
  --repo ~/codes/amrex-agent/PeleC \
  --output database/indices/hierarchical
```

### Clear All Indices

```bash
# Remove all indices (careful!)
rm -rf database/faiss/*
rm -rf database/indices/hierarchical/*

# Rebuild from scratch
# (Follow build instructions above)
```

### Index Integrity Check

```bash
# Verify index loads correctly
python -c "
from pathlib import Path
import faiss

# Check simple indices
for idx_dir in Path('database/faiss').iterdir():
    if idx_dir.is_dir():
        idx_path = idx_dir / 'index.faiss'
        if idx_path.exists():
            index = faiss.read_index(str(idx_path))
            print(f'{idx_dir.name}: {index.ntotal} vectors')

# Check hierarchical indices
for level in ['level0', 'level1', 'level2']:
    level_path = Path(f'database/indices/hierarchical/{level}')
    if level_path.exists():
        for idx_file in level_path.rglob('*.faiss'):
            index = faiss.read_index(str(idx_file))
            print(f'{idx_file}: {index.ntotal} vectors')
"
```

---

## Further Reading

- **Indexing Strategies Deep Dive**: [`docs/INDEXING_STRATEGIES.md`](../../docs/INDEXING_STRATEGIES.md)
- **Build Scripts README**: [`database/scripts/README.md`](../scripts/README.md)
- **Architect Node Contract**: [`tests/contracts/architect_node_contract.json`](../../tests/contracts/architect_node_contract.json)
- **Embedding Service**: [`src/services/embedding_service.py`](../../src/services/embedding_service.py)
- **Base Config**: [`database/configs/base_amrex_config.py`](../configs/base_amrex_config.py)

---

## Questions?

1. Check configuration: `grep -r "indexing_strategy\|faiss.*path" src/config.py`
2. Verify indices exist: `ls -lh database/faiss/ database/indices/hierarchical/`
3. Check logs: `export LOG_LEVEL=DEBUG && pytest -v --capture=no`
4. Review workflow history for indexing metadata
5. Compare strategies with comparative tests
6. File issue with build logs and error messages

---

**Last Updated:** 2026-01-08
**Version:** 1.0
**Maintainer:** AMReXAgent Team
