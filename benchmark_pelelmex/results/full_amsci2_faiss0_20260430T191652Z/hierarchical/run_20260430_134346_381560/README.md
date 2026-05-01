# AMReX Simulation Run

**Created:** 2026-04-30 13:43:49

## Configuration
- Grid: 128 128 128
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
cd run_20260430_134346_381560
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260430_134346_381560
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
