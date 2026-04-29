# AMReX Simulation Run

**Created:** 2026-04-29 10:12:59

## Configuration
- Grid: 200     4      100
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
cd run_20260429_101257_135956
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260429_101257_135956
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
