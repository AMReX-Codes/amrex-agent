# AMReX Simulation Run

**Created:** 2026-04-29 13:01:09

## Configuration
- Grid: 512  4 256
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
cd run_20260429_130109_308858
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260429_130109_308858
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
