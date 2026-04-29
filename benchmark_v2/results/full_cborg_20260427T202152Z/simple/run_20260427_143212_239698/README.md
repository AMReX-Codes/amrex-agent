# AMReX Simulation Run

**Created:** 2026-04-27 14:32:14

## Configuration
- Grid: 96    4    128
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
cd run_20260427_143212_239698
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260427_143212_239698
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
