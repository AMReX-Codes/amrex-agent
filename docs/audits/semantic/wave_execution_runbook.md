# Wave Execution Runbook

## Goal
Run wave sessions safely across `wt-1..wt-5` with isolated agent contexts and resumable state.

## Why this avoids sandbox friction
- Run each agent invocation from inside a specific worktree directory.
- Do not run one agent session that writes across multiple worktree roots.
- Each worker only touches its own worktree path.

## Scripts
- `scripts/run_wave_worktree.sh`
  - Executes assigned sessions for one `wt` and one `wave`.
  - Reads assignments from `docs/audits/semantic/wave_plan.md`.
  - Persists progress in `.wave_runs/` (`*.complete`, `*.failed`, logs).
- `scripts/launch_wave_all_worktrees.sh`
  - Launches `wt-1..wt-5` in parallel.
  - Uses per-worktree logs in `.wave_runs/launcher_wave*_wt*.log`.

## Preflight
1. Ensure worktrees exist at sibling paths:
   - `.../amrex-agent_wt-1` through `.../amrex-agent_wt-5`
2. Ensure each worktree has its own branch checked out.
3. Ensure your agent CLI is available (`codex` by default; override with `--agent`).

## Examples

Single worktree, wave 1 dry-run:
```bash
cd ~/codes/worktree_sandbox/amrex-agent_wt-1
~/codes/worktree_sandbox/amrex-agent/scripts/run_wave_worktree.sh \
  --wt 1 --wave 1 --agent codex --dry-run
```

Single worktree, wave 1 real run with resume:
```bash
cd ~/codes/worktree_sandbox/amrex-agent_wt-1
~/codes/worktree_sandbox/amrex-agent/scripts/run_wave_worktree.sh \
  --wt 1 --wave 1 --agent codex --resume
```

Launch all worktrees for wave 1:
```bash
cd ~/codes/worktree_sandbox/amrex-agent
scripts/launch_wave_all_worktrees.sh --wave 1 --agent codex --resume
```

## Merge checkpoint policy
After each wave:
1. Merge all wt branches into `consolidate_all`.
2. Run full CI merge gate.
3. Start next wave only after gate passes.

## Failure handling
- Worker stops on first failing session.
- Inspect logs in `.wave_runs/`.
- Fix issue in that worktree.
- Re-run with `--resume`.
