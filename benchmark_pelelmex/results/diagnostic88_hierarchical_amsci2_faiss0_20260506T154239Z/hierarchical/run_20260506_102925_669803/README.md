# AMReX Simulation Run

**Created:** 2026-05-06 10:29:28

## Configuration
- Grid: 64 128
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
cd run_20260506_102925_669803
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260506_102925_669803
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
