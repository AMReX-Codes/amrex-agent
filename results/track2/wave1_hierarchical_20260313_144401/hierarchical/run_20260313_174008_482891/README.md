# AMReX Simulation Run

**Created:** 2026-03-13 17:40:08

## Configuration
- Grid: 64  64 24
- Max level: 1
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
cd run_20260313_174008_482891
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260313_174008_482891
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
