# Metadata Extraction and README Generation

Comprehensive metadata extraction for AMReX and Pele cases.

## Architecture

```
database/scripts/
├── amrex_metadata_utils.py    # Generic AMReX utilities (all codes)
├── pele_metadata_utils.py     # Pele-specific utilities (combustion)
└── enhance_metadata.py         # README generator (uses both)
```

### Separation of Concerns

**Generic AMReX** (`amrex_metadata_utils.py`):
- Works for ANY AMReX code (PeleC, PeleLMeX, ERF, WarpX, incflo, Castro, etc.)
- Extracts: DIM, USE_MPI, USE_CUDA, compiler
- File types: generic interpretations (data_file, config_file)

**Pele-Specific** (`pele_metadata_utils.py`):
- Only for PelePhysics codes (PeleC, PeleLMeX, PeleMP)
- Extracts: Chemistry_Model, Eos_dir, Transport_dir
- File types: combustion interpretations (chemistry_data, chemistry_config)
- Mechanism database: 66 mechanisms with fuel mappings

**README Generator** (`enhance_metadata.py`):
- Combines both utilities
- Creates comprehensive case documentation
- Supports single case or batch mode

## Usage

### Single Case (Interactive)

```bash
cd database/scripts
python enhance_metadata.py ~/amrex-repos/PeleC/Exec/RegTests/Sedov
```

Output:
- Displays extracted metadata
- Shows auxiliary files found
- Generates README preview
- Prompts to save README.md

### Batch Mode (All Cases in Directory)

```bash
# Process all subdirectories
python enhance_metadata.py --batch ~/amrex-repos/PeleC/Exec/RegTests

# Auto-save without prompting
python enhance_metadata.py --batch --save ~/amrex-repos/PeleC/Exec/Production
```

### Integration with Database Building

Instead of standalone usage, integrate into config classes:

```python
# database/configs/base_amrex_config.py
from database.scripts.amrex_metadata_utils import extract_generic_build_config

class BaseAMReXConfig:
    @classmethod
    def extract_metadata(cls, case_path: Path) -> Dict[str, Any]:
        metadata = { ... }

        # Add generic build config
        build_config = extract_generic_build_config(case_path)
        metadata.update(build_config)

        return metadata
```

```python
# database/configs/pelec_config.py
from database.scripts.pele_metadata_utils import extract_pele_build_config

class PeleCConfig(BaseAMReXConfig):
    @classmethod
    def extract_metadata(cls, case_path: Path) -> Dict[str, Any]:
        metadata = super().extract_metadata(case_path)

        # Add Pele-specific config
        pele_config = extract_pele_build_config(case_path)
        metadata.update(pele_config)

        return metadata
```

## Extracted Metadata

### Generic AMReX (All Codes)

From `extract_generic_build_config()`:
```python
{
    'dim': 3,                    # Dimensionality
    'use_mpi': True,            # MPI enabled
    'use_cuda': False,          # CUDA disabled
    'use_hip': False,           # HIP disabled
    'use_omp': True,            # OpenMP enabled
    'compiler': 'gnu',          # Compiler (gnu, intel, etc.)
}
```

From `catalog_generic_auxiliary_files()`:
```python
[
    {'file': 'Prob.cpp', 'type': 'problem_setup', 'purpose': '...'},
    {'file': 'geometry.stl', 'type': 'eb_geometry', 'purpose': '...'},
    {'file': 'data.dat', 'type': 'data_file', 'purpose': 'data data file'},
]
```

From `compare_inputs_variants()`:
```python
[
    {
        'file': 'inputs.2d',
        'grid': '256 256',
        'max_level': '2',
        'dim_hint': '2D',
        'notes': 'Regression test'
    },
    ...
]
```

### Pele-Specific (Combustion Codes)

From `extract_pele_build_config()`:
```python
{
    'chemistry_model': 'drm19',      # Chemistry mechanism
    'eos_model': 'Fuego',            # Equation of state
    'transport_model': 'Simple',     # Transport model
}
```

From `catalog_pele_auxiliary_files()`:
```python
[
    {
        'file': 'drm19.yaml',
        'type': 'chemistry_config',
        'purpose': 'DRM19 (21-species methane) chemistry configuration (Cantera format)'
    },
    ...
]
```

From `infer_combustion_regime()`:
- `'premixed_flame'` - Premixed combustion
- `'diffusion_flame'` - Non-premixed combustion
- `'detonation'` - Detonation wave
- `'auto_ignition'` - Auto-ignition
- `'inert'` - Non-reacting flow

From `get_mechanism_info()`:
```python
{
    'name': 'DRM19',
    'species_count': 21,
    'fuel': 'methane',
    'description': 'Reduced methane mechanism from GRI-Mech',
    'reference': 'Kazakov & Frenklach (1994)'
}
```

## Generated README Structure

```markdown
# CaseName

**[One sentence physics description - TO BE FILLED]**

*Combustion Regime:* Premixed Flame

## Case Configuration

| Parameter | Value |
|:----------|:------|
| Dimensionality | 3D |
| Grid | 128 128 128 |
| AMR levels | 2 |
| Chemistry | DRM19 (21 species, methane) |
| EOS | Fuego |
| Transport | Simple |
| Compiler | gnu |
| Parallelism | MPI, OpenMP |

## Files

- **inputs**: Main configuration
- **GNUmakefile**: Build configuration
- **drm19.yaml**: DRM19 chemistry configuration (Cantera format)
- **Prob.cpp**: Problem-specific initial/boundary conditions

## Input File Variants

| File | Grid | AMR Levels | Notes |
|:-----|:-----|:-----------|:------|
| inputs.2d | 256 256 (2D) | 2 | Regression test |
| inputs.3d | 128 128 128 (3D) | 1 | Production settings |

## Physics

**[Premixed combustion case]**

Describe the premixed flame configuration:
- Flame type (1D, 2D, or 3D)
- Fuel-air mixture composition
- Flame stabilization mechanism
- Expected flame speed/thickness

## Keywords

**Suggested:** 3D, premixed flame, methane

**[ADD MORE]**: shock, flame, turbulence, etc.

## Use Cases

**Good for:**
- [Problem type 1]

**Not suitable for:**
- [What this doesn't cover]

## References

- Chemistry mechanism: Kazakov & Frenklach (1994)
```

## Mechanism Database

Currently includes **66 mechanisms** from `architect.py`:

**Methane:** drm19, drm22, gri30, grimech30, alzeta, kolla, ...
**Hydrogen:** lidryer, burkedryer, sandiego, chem-h, ...
**Heavy Hydrocarbons:** dodecane_lu, heptane_3sp, propane_fc, ...
**Specialty:** sootreaction, methaneions_direnzo, ionizedair, ...

Detailed info available for 10 common mechanisms:
- drm19, drm22, gri30, lidryer, burkedryer, sandiego, dodecane_lu, alzeta, kolla, null

## Workflow Recommendation

### Phase 1: Generate READMEs (One-time, Human-in-Loop)

```bash
# Process all RegTests cases
cd database/scripts
python enhance_metadata.py --batch --save ~/amrex-repos/PeleC/Exec/RegTests

# Review and fill in physics descriptions manually
# Edit each README.md to complete [TO BE FILLED] sections
```

### Phase 2: Build FAISS Indices (Uses READMEs)

```bash
# Build indices with enhanced metadata
cd database/scripts
python build_index.py --config pelec

# READMEs are automatically included via utils.extract_readme_content()
```

## Testing

```bash
# Test generic utils (should work for any AMReX code)
cd database/scripts
python -c "
from pathlib import Path
from amrex_metadata_utils import extract_generic_build_config
print(extract_generic_build_config(Path('~/amrex-repos/PeleC/Exec/RegTests/Sedov')))
"

# Test Pele utils (only for Pele codes)
python -c "
from pathlib import Path
from pele_metadata_utils import extract_pele_build_config, get_mechanism_info
config = extract_pele_build_config(Path('~/amrex-repos/PeleC/Exec/RegTests/PMF'))
print(config)
if config.get('chemistry_model'):
    print(get_mechanism_info(config['chemistry_model']))
"

# Test full README generation
python enhance_metadata.py ~/amrex-repos/PeleC/Exec/RegTests/Sedov
```

## Future Extensions

### For Other AMReX Codes

Create code-specific utilities similar to `pele_metadata_utils.py`:

- `warpx_metadata_utils.py` - Particle beam physics
- `erf_metadata_utils.py` - Atmospheric physics
- `castro_metadata_utils.py` - Astrophysics

Each imports generic utils and adds domain-specific knowledge.

### For Enhanced Metadata

Add to `pele_metadata_utils.py`:
- Reaction pathway analysis
- Species grouping (radicals, products, etc.)
- Combustion index calculation (Damköhler number, etc.)
- Auto-detect flame type from BC and IC

Add to `amrex_metadata_utils.py`:
- Parse probin files (Fortran namelists)
- Extract EB geometry complexity
- Analyze AMR efficiency settings
