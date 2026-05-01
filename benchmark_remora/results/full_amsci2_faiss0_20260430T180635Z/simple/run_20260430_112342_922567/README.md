# AMReX Simulation Run

**Created:** 2026-04-30 11:23:42

## Configuration
- Grid: ?
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
cd run_20260430_112342_922567
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260430_112342_922567
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
