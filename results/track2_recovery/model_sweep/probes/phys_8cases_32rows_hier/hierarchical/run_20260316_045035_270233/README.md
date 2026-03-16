# AMReX Simulation Run

**Created:** 2026-03-16 04:50:35

## Configuration
- Grid: 4    4    50
- Max level: 0
- Executable: ?

## Files
- `inputs` - AMReX configuration
- `?` - Compiled executable
- `run_local.sh` - Local run script (generated for local runs)
- `submit.sh` - SLURM batch script (generated for cluster runs)
- `run.out` - Simulation output (batch runs only)
- `plt*` - AMReX plotfiles (after run)

## Run Locally (if `run_local.sh` exists)
```bash
cd run_20260316_045035_270233
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260316_045035_270233
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
