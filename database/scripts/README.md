# FAISS Index Building Scripts

Config-driven FAISS index builders for AMReX codes (PeleC, PeleLMeX, ERF, WarpX, incflo).

Pattern inspired by foam-agent but generalized for any AMReX code using configuration classes.

## Quick Start

**IMPORTANT**: Run from project root (`amrex-agent/`), not from scripts directory!

### Build PeleC Indices

```bash
# From project root
cd /path/to/amrex-agent

# Case structure index (hierarchical level 1 - broad matching)
python amrex_agent/database/scripts/build_index.py --config pelec --type case_structure \
    --source ~/amrex-repos/PeleC

# Case details index (hierarchical level 2 - detailed docs)
python amrex_agent/database/scripts/build_index.py --config pelec --type case_details \
    --source ~/amrex-repos/PeleC

# Input templates index
python amrex_agent/database/scripts/build_index.py --config pelec --type input_templates \
    --source ~/amrex-repos/PeleC

# Chemistry mechanism index
python amrex_agent/database/scripts/build_index.py --config pelec --type chemistry
```

### Build PeleLMeX Indices

```bash
# From project root
python amrex_agent/database/scripts/build_index.py --config pelelmex --type case_structure \
    --source ~/amrex-repos/PeleLMeX

python amrex_agent/database/scripts/build_index.py --config pelelmex --type case_details \
    --source ~/amrex-repos/PeleLMeX
```

## Index Types

### `case_structure`
**Hierarchical Level 1** - High-level case organization
- Directory structure
- Case type (RegTests, Production, Tutorial)
- Basic metadata extraction
- Use for: Broad case matching

### `case_details`
**Hierarchical Level 2** - Detailed documentation
- README content
- Input file parameters
- Detailed metadata
- Use for: Parameter-level matching

### `input_templates`
**Templates** - Input file patterns
- Full input file content
- Parameter configurations
- Use for: Finding similar input patterns

### `chemistry`
**Domain Knowledge** - Mechanism/fuel mappings
- Chemistry mechanisms
- Fuel types
- Code-specific domain data
- Use for: Semantic chemistry queries

## Configuration Options

### Embedding Providers

```bash
# OpenAI (default, best quality)
python build_index.py --config pelec --type case_structure \
    --source ~/amrex-repos/PeleC --embedding openai

# HuggingFace (local, free, lower quality)
python build_index.py --config pelec --type case_structure \
    --source ~/amrex-repos/PeleC --embedding huggingface

# CBORG (TODO: when available)
python build_index.py --config pelec --type case_structure \
    --source ~/amrex-repos/PeleC --embedding cborg
```

### Testing with Limited Cases

```bash
# Process only first 10 cases (for testing)
python build_index.py --config pelec --type case_structure \
    --source ~/amrex-repos/PeleC --max-cases 10
```

### Custom Output Directory

```bash
# Specify custom output path
python build_index.py --config pelec --type case_structure \
    --source ~/amrex-repos/PeleC \
    --output /custom/path/pelec_case_structure
```

## Output Structure

Indices are saved to `database/faiss/` by default:

```
database/faiss/
├── pelec_case_structure/       # PeleC structure index
├── pelec_case_details/         # PeleC details index
├── pelec_input_templates/      # PeleC templates index
├── pelec_chemistry/            # PeleC chemistry index
├── pelelmex_case_structure/    # PeleLMeX structure index
└── pelelmex_case_details/      # PeleLMeX details index
```

## Adding a New Code (e.g., ERF)

1. **Create config** (`database/configs/erf_config.py`):
```python
from .base_amrex_config import BaseAMReXConfig

class ERFConfig(BaseAMReXConfig):
    code_name = "ERF"
    faiss_indices = ['erf_case_structure', 'erf_case_details']

    @classmethod
    def get_domain_data(cls):
        return {'physics_types': ERF_PHYSICS_TYPES}
```

2. **Register in `__init__.py`**:
```python
from .erf_config import ERFConfig
# Add to CONFIG_MAP in build_index.py
```

3. **Build indices**:
```bash
python build_index.py --config erf --type case_structure \
    --source ~/amrex-repos/ERF
```

Done! The builder automatically uses ERFConfig's metadata extraction.

## Utilities (`utils.py`)

Core functions used by index builders:

- `tokenize()`: Normalize text (foam-agent pattern)
- `format_case_document()`: XML-like document structure
- `find_case_directories()`: Discover cases in source tree
- `extract_directory_structure()`: Build directory tree
- `extract_input_file_content()`: Parse inputs files
- `extract_readme_content()`: Extract README docs
- `combine_hierarchical_scores()`: Multi-level scoring

## Foam-Agent Patterns

✓ **Tokenization**: Underscore→space, camelCase split, lowercase
✓ **XML Formatting**: `<case_begin>/<index>/<metadata>` structure
✓ **Hierarchical Levels**: Structure → Details → Templates
✓ **Document Metadata**: Rich metadata for filtering

## Architecture

```
build_index.py (generic)
    ↓
BaseAMReXConfig (common AMReX)
    ↓
PeleCConfig / PeleLMeXConfig / ERFConfig (code-specific)
    ↓
extract_metadata() (uses config's knowledge)
    ↓
format_case_document() (XML structure)
    ↓
tokenize() (normalize)
    ↓
FAISS.from_documents() (embed & index)
```

## Requirements

- langchain
- langchain-community
- langchain-openai (for OpenAI embeddings)
- langchain-huggingface (for HuggingFace embeddings)
- faiss-cpu or faiss-gpu
- openai (API key in environment for OpenAI)

## Environment Variables

```bash
# For OpenAI embeddings
export OPENAI_API_KEY="sk-..."

# For CBORG (when available)
export CBORG_API_KEY="..."
```

## Troubleshooting

**Issue**: `ImportError: No module named 'amrex_agent'`
- Run from project root or ensure PYTHONPATH is set

**Issue**: `Source directory does not exist`
- Check `--source` path exists and points to code repository

**Issue**: OpenAI API errors
- Verify OPENAI_API_KEY is set
- Try `--embedding huggingface` for local embeddings

**Issue**: No cases found
- Check source directory structure
- Builder looks for: `**/Exec/**`, `**/Tests/**`, `**/Tutorials/**`

## Performance

- Case structure: ~10-20 cases/min (depends on directory size)
- Case details: ~5-10 cases/min (parses README + inputs)
- Input templates: ~10-15 cases/min
- Chemistry: Instant (small dataset)

Use `--max-cases` for quick testing.
