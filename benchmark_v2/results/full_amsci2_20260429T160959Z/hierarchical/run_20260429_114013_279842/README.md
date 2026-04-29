# AMReX Simulation Run

**Created:** 2026-04-29 11:40:15

## Configuration
- Grid: 64       64      64
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
cd run_20260429_114013_279842
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260429_114013_279842
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
