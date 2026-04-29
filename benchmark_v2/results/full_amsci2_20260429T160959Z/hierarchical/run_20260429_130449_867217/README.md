# AMReX Simulation Run

**Created:** 2026-04-29 13:04:51

## Configuration
- Grid: 150  150    55
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
cd run_20260429_130449_867217
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260429_130449_867217
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
