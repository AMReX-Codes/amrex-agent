# Example retry setups (failure paths)

This file records smoke-test failure paths so we can reproduce and inspect them without blocking the demo flow.

## Failure path: PeleLMeX FlameSheet (inputs mismatch / grid remap)

### Example repro command (kept for failure-path inspection)
```bash
python amrex_agent.py \
  --prompt "2D hydrogen premixed flame with 128x512 grid cells, 2 AMR levels, 1000 timesteps" \
  --baseline-override PeleLMeX/Exec/RegTests/FlameSheet \
  --indexing-strategy simple \
  --inputs-file-strategy llm_compare \
  --save-workflow \
  --save-transcript \
  --save-log \
  --color-logs always \
  --verbose
```

### Example run artifacts (from 2026-01-26)
- Run directory: `output/run_20260126_141152/`
- Workflow history: `output/run_20260126_141152/workflow_history.json`
- Stderr log: `output/run_20260126_141152/stderr.log`
- Console log: `output/console_20260126_131342.log`

### Observed failure
- `max_grid_size not divisible by blocking_factor` (from stderr)

### Notes
- This is a known failure-path for the smoke test. The demo should use the override inputs strategy for stability.
- Refining the spatial grid typically requires more conservative time stepping.
- If a newer run is created, prefer the latest `output/run_*` and `output/console_*.log` paths.
