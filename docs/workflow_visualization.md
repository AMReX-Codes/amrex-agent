# Workflow Visualization Integration

**Purpose**: Generate visualizations automatically as part of the AMReXAgent workflow.

**Status**: Active (post-analysis visualization with multi-backend support).

---

## Overview

The workflow generates visualizations from AMReX plotfiles after a successful
analysis pass. Visualization uses the multi-backend service (AMReX tools first,
then optional pyamrex, then yt) and records metadata in the graph state.

### Intent Resolution and Clarification

Visualization intent resolution is deterministic-first and code-derived:

- Architect emits semantic visualization intent only.
- `visualization_intent_node` performs canonical mapping through solver
  Tier-2 candidates from live code catalogs.
- If mapping is ambiguous/unresolved, the node records diagnostics:
  - `visualization_mapping_candidates`
  - `visualization_mapping_unresolved`
  - `visualization_mapping_source`
  - `visualization_mapping_confidence`
- Clarification node asks constrained disambiguation questions using provided
  candidate sets, and AI responses outside the candidate set are rejected.

Hard-fail behavior:

- If solver catalog/source code is unavailable for a visualization mapping
  request, runtime fails with actionable remediation instead of silently
  guessing fields.

### Workflow Flow

```
START → Architect → Reviewer (pre-execution validation)
                        ↓
                    (approved) → Input Writer → Runner
                                                    ↓
                                                Analysis (always)
                                                    ↓
                                   (fail) → Reviewer → Architect (retry)
                                                    ↓
                                         (pass) → Visualization → END
```

**Visualization Node** runs after the Analysis node if:
1. Analysis status is not `failed` (router sends failures back to Reviewer)
2. Run directory exists
3. Plotfiles are present (otherwise visualization is skipped)

---

## Backend Auto-Selection

The visualization system selects the best available backend in priority order:

### Priority Order

1. **AMReXToolsBackend** (Priority 1 - Preferred)
   - Uses native AMReX C++ tools: `fvarnames`, `fextrema`, `fsnapshot`, `fextract`
   - **Advantages**:
     - Fastest performance (compiled C++)
     - No Python dependencies beyond amrex_agent
     - Works on HPC without yt-project
     - Native AMReX format support
   - **Requires**: AMReX tools compiled in `~/amrex/Tools/Plotfile/`

2. **PyAMReXBackend** (Priority 2 - Optional)
   - Uses Python bindings if available
   - Only selected when importable

3. **YtBackend** (Priority 3 - Fallback)
   - Uses yt-project Python library
   - **Advantages**:
     - Mature, well-documented
     - Works everywhere yt is installed
     - Rich plotting capabilities
   - **Requires**: `pip install yt`

### Config Overrides

You can force the backend with `visualization_backend` in `src/config.py`:

- `auto` (default): AMReX tools → pyamrex → yt
- `amrex_tools`, `pyamrex`, `yt`: force a specific backend

AMReX tools path can be set with `amrex_tools_path` (or auto-detected from
`amrex_repo_path/Tools/Plotfile`).

### Checking Which Backend is Used

The selected backend is logged in the workflow state:

```python
from src.main import build_workflow

workflow = build_workflow()
result = workflow.invoke({"user_requirement": "simulate a 2D advection test case"})

print(f"Backend used: {result['visualization_backend']}")
# Output: "AMReXToolsBackend" or "YtBackend"
```

---

## What Gets Visualized

### Standard Plots (Auto-Generated)

The visualization node automatically creates:

1. **Temperature slice** (if `Temp` or `temperature` field exists)
   - Colormap: 'hot'
   - Axis: z-slice through domain center

2. **Density slice** (if `density` field exists)
   - Colormap: 'viridis'
   - Axis: z-slice through domain center

### Analysis-Driven Plots (Conditional)

Additional plots are generated based on analysis results:

3. **Velocity slice** (if high velocities detected)
   - Triggers when `max_velocity > 1e5` cm/s in analysis report
   - Plots `x_velocity` field

4. **Scalar species fields** (if present)
   - Auto-detects fields like `Y(species)` or passive scalars
   - Plots up to 3 scalars based on analysis hints
   - Useful for reacting flows or transport problems

### Output Location

Visualizations are saved to:
```
<run_dir>/visualization/
    ├── Temp_slice.png
    ├── density_slice.png
    ├── Y(species)_slice.png  (if scalar fields enabled)
    └── ...
```

---

## Visualization Status Tracking

### State Fields

The workflow state includes detailed visualization metadata:

```python
state = {
    # ... other workflow fields ...

    # Visualization outputs
    "visualization_images": [
        "/path/to/run_dir/visualization/Temp_slice.png",
        "/path/to/run_dir/visualization/density_slice.png"
    ],

    # Phase 5 metadata
    "visualization_backend": "AMReXToolsBackend",  # or "YtBackend", "none"
    "visualization_status": "success",  # or "failed", "skipped"
    "visualization_metadata": {
        "plotfile_count": 10,
        "latest_plotfile": "plt00200",
        "fields_plotted": ["Temp", "density", "Y(CH4)"],
        "backend_used": "AMReXToolsBackend",
        "image_count": 3,
        "container_mode": False
    }
}
```

### Status Values

| Status | Meaning | When It Happens |
|--------|---------|----------------|
| `success` | Visualizations generated successfully | Plotfiles found, backend worked |
| `failed` | Visualization failed | Backend error, file I/O error |
| `skipped` | Visualization skipped | No plotfiles, simulation failed, no run_dir |

---

## Container Mode (HPC Environments)

### Problem

On HPC systems (Perlmutter, etc.) using containers (podman-hpc, Shifter):
- Containers often lack GUI libraries (X11, OpenGL)
- matplotlib/yt may fail with display errors
- Cannot generate images directly inside container

### Solution: Two-Stage Workflow

Enable container mode in config (auto-detected from `PODMAN_HPC` or `SHIFTER`):

```python
# src/config.py or environment variable
container_mode = True
```

When `container_mode` is enabled, visualization runs the extraction + rendering
path to avoid GUI dependencies, regardless of the selected backend.

**Stage 1: Data Extraction (Inside Container)**
- Runs headless (no GUI required)
- Uses yt to load plotfile and extract numpy arrays
- Saves data to HDF5 format
- Output: `<run_dir>/visualization/extracted/<plotfile>_extracted.h5`

**Stage 2: Rendering (Outside Container)**
- Runs locally with matplotlib
- Loads HDF5 file
- Generates PNG images
- No yt required for rendering

### Usage Example

```bash
# On HPC (inside container)
export CONTAINER_MODE=true
python amrex_agent.py --prompt "simulate a basic AMReX test case"

# HDF5 files created in visualization/extracted/
# Transfer to local machine

# On local machine (outside container)
python render_from_extracted.py visualization/extracted/*.h5
```

---

## Error Handling

### Graceful Degradation

The visualization node is designed to **never crash the workflow**:

1. **Missing plotfiles**: Status = 'skipped', workflow continues
2. **Backend initialization failure**: Status = 'failed', workflow continues
3. **Image generation error**: Status = 'failed', error logged, workflow continues

Errors are logged to `state["error_logs"]` for debugging.

### Common Issues and Solutions

#### Issue: "No plotfiles found"

**Cause**: Simulation didn't generate plotfiles (too short, output disabled)

**Solution**:
- Check simulation completed at least 1 timestep
- Verify `amr.plot_int` or `amr.plot_per` in inputs file
- Increase simulation runtime

```python
# In inputs file
amr.plot_int = 10  # Plot every 10 timesteps
```

#### Issue: "AMReXToolsBackend not available"

**Cause**: AMReX tools not compiled or not found

**Solution**:
1. Build AMReX tools:
```bash
cd ~/amrex/Tools/Plotfile
make -j 8
```

2. Set environment variable:
```bash
export AMREX_TOOLS_DIR=~/amrex/Tools/Plotfile
```

3. Or configure in amrex_agent:
```python
# src/config.py
amrex_tools_path = Path.home() / "amrex" / "Tools" / "Plotfile"
```

Falls back to yt automatically if tools unavailable.

#### Issue: "Visualization failed: No module named 'yt'"

**Cause**: yt not installed and AMReX tools unavailable

**Solution**: Install yt:
```bash
pip install yt
```

---

## Customizing Visualizations

### Method 1: Via Architect Plan

The architect can specify visualization config in the plan:

```python
plan = {
    "baseline": {...},
    "modifications": {...},
    "visualization": {
        "plots": [
            {"type": "slice", "field": "Temp", "axis": "z"},
            {"type": "slice", "field": "density", "axis": "x"},  # Different axis
            {"type": "slice", "field": "Y(CH4)", "axis": "z"},
            {"type": "profile", "field": "Temp", "direction": "x"}  # 1D profile
        ]
    }
}
```

### Method 2: Via Analysis Report

The analysis node can suggest visualizations:

```python
analysis_report = {
    "status": "success",
    "max_velocity": 2e6,  # High velocity → triggers velocity plot
    "cfl_max": 0.8,
    "timesteps": 100
}
```

### Method 3: Direct Service Call

For standalone usage:

```python
from src.config import AMReXAgentConfig
from src.services.visualization import VisualizationService

config = AMReXAgentConfig()
viz = VisualizationService(config)

images = viz.create_standard_plots(
    run_dir=Path("path/to/run"),
    vis_config={
        "plots": [
            {"type": "slice", "field": "Temp", "axis": "z"},
            {"type": "slice", "field": "pressure", "axis": "y"}
        ]
    }
)

print(f"Generated: {images}")
```

---

## Accessing Visualization Results

### From Workflow State

```python
result = workflow.invoke({"user_requirement": "..."})

# Get image paths
images = result["visualization_images"]
for img in images:
    print(f"Created: {img}")

# Check backend used
print(f"Backend: {result['visualization_backend']}")

# Check if successful
if result["visualization_status"] == "success":
    print(f"Generated {len(images)} visualizations")
else:
    print(f"Visualization {result['visualization_status']}")
    print(f"Reason: {result['visualization_metadata']}")
```

### From File System

Visualizations are always saved to:
```
<run_dir>/visualization/
```

Find them programmatically:
```python
from pathlib import Path

viz_dir = Path(run_dir) / "visualization"
images = list(viz_dir.glob("*.png"))
print(f"Found {len(images)} visualizations")
```

---

## Performance Comparison

### AMReX Tools vs yt

Based on testing with typical AMReX plotfiles:

| Metric | AMReX Tools | yt-project |
|--------|-------------|------------|
| **Initialization** | ~0.1s | ~2-3s |
| **Field list** | ~0.05s | ~0.5s |
| **Min/max extraction** | ~0.2s | ~1-2s |
| **Slice generation** | ~0.3s | ~3-5s |
| **Total (2 fields)** | **~1s** | **~10s** |
| **Dependencies** | None (beyond amrex_agent) | yt + numpy + matplotlib |
| **Image quality** | Good (PPM → PNG) | Excellent (matplotlib) |

**Recommendation**: Use AMReX tools on HPC for speed, yt locally for quality.

---

## Testing

### Run Integration Tests

```bash
python test_workflow_visualization.py
```

Tests cover:
1. ✓ Success case with plotfiles
2. ✓ Graceful skip (missing plotfiles)
3. ✓ Skip on failed simulation
4. ✓ Backend auto-selection
5. ✓ Metadata population
6. ✓ Container mode detection

### Test with Real Plotfile

```bash
# Generate a test plotfile with your solver of choice (AMReX/Pele/ERF/WarpX)
# Example: AMReX Advection_AmrCore
cd ~/amrex/Tests/Amr/Advection_AmrCore/Exec
make -j 8
./main2d.gnu.MPI.ex inputs

# Test visualization
python -c "
from pathlib import Path
from src.config import AMReXAgentConfig
from src.services.visualization import VisualizationService

config = AMReXAgentConfig()
viz = VisualizationService(config)

images = viz.create_standard_plots(
    run_dir=Path('path/to/plotfile/output')
)

print(f'Generated: {images}')
"
```

---

## Advanced: Profile Plots (Future)

Profile plots (1D slices) are planned for future implementation using `fextract`:

```python
vis_config = {
    "plots": [
        {
            "type": "profile",
            "field": "Temp",
            "direction": "x",  # Extract along x-axis
            "coord": {"y": 0.5, "z": 0.5}  # At domain center in y,z
        }
    ]
}
```

This will use `fextract.ex` to extract 1D data and matplotlib for rendering.

---

## References

- **Phase 4 Workflow**: `src/main.py` - LangGraph workflow definition
- **Visualization Node**: `src/nodes/visualization_node.py`
- **VisualizationService**: `src/services/visualization.py`
- **AMReXToolsBackend**: `src/services/amrex_tools_backend.py`
- **YtBackend**: `src/services/yt_backend.py`
- **Backend Tests**: `test_visualization_backends.py`
- **Workflow Tests**: `test_workflow_visualization.py`
- **AMReX Tools Documentation**: https://amrex-codes.github.io/amrex/docs_html/Visualization.html

---

## Troubleshooting

### Enable Debug Logging

Set environment variable:
```bash
export AMREX_AGENT_DEBUG=1
python run_workflow.py
```

### Check Backend Availability

```python
from src.config import AMReXAgentConfig
from src.services.amrex_tools_backend import AMReXToolsBackend
from src.services.yt_backend import YtBackend

config = AMReXAgentConfig()

amrex_backend = AMReXToolsBackend(config)
print(f"AMReX tools available: {amrex_backend.available()}")
if amrex_backend.available():
    print(f"  Tool directory: {amrex_backend.tool_dir}")

yt_backend = YtBackend(config)
print(f"yt available: {yt_backend.available()}")
```

### Verify Plotfile Structure

```bash
# Check plotfile exists and is a directory
ls -la plt00100/

# Should contain:
#   Header (metadata file)
#   Level_0/ (coarsest level data)
#   Level_1/ (if AMR refinement)
#   ...
```

---

## Next Steps

After completing workflow visualization integration:

1. **Test on HPC** - Deploy to Perlmutter and test with production simulations
2. **Profile plots** - Implement 1D slice extraction using `fextract`
3. **Custom palettes** - Generate colormap files for `fsnapshot`
4. **Visual analysis** - Add computer vision for automatic failure detection
5. **Animation** - Generate time series animations from multiple plotfiles

See `PHASE5_NEXT_STEPS.md` for full roadmap.
