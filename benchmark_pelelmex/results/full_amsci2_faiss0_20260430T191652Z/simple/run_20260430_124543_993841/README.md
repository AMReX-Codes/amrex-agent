# AMReX Simulation Run

**Created:** 2026-04-30 12:45:46

## Configuration
- Grid: 64 64 64
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
cd run_20260430_124543_993841
./run_local.sh
```

## Submit Job (if `submit.sh` exists)
```bash
cd run_20260430_124543_993841
sbatch submit.sh
```

## Monitor
```bash
squeue -u $USER  # batch only
tail -f run.out  # batch only
```
