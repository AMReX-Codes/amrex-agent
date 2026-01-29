# AMReX Demo Commands

Centralized AMReX demo entry points for quick testing.
Note: Run commands from the repo root so relative paths like `demo/...` resolve correctly.

## Option 0: Baseline + inputs only (no modifications)

Use explicit overrides for the problem directory and inputs file.

```bash
python amrex_agent.py \
  --prompt "Use the AMReX Advection_AmrCore baseline as-is" \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --inputs-file-strategy override \
  --inputs-file-override inputs \
  --indexing-strategy override_static \
  --save-workflow \
  --verbose
```

## Option 1: Baseline + modifications (baseline specified)

```bash
python amrex_agent.py \
  --prompt "AMReX Advection_AmrCore with a 128x128 grid and 3 AMR levels" \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --indexing-strategy override_static \
  --save-workflow
```

## Prompt file example

```bash
python amrex_agent.py \
  --prompt_path demo/amrex/user_requirement.txt \
  --baseline-override AMReX/Tests/Amr/Advection_AmrCore/Exec \
  --save-workflow \
  --verbose
```
