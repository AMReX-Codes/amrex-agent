# AMReX Simulation Run

**Created:** 2026-04-28 10:29:12

## Configuration
- Grid: 128  128   128
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
cd run_20260428_102912_845798
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260428_102912_845798
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
