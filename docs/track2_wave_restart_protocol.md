# Track 2 Wave Restart Protocol

This protocol treats prior Wave 1 results as a preserved prototype, then restarts Wave 1 in checkpointed batches with stronger artifact retention and gating.

## 1) Preserve Current Progress

Use a dedicated branch for result preservation before new runs.

```bash
git checkout -b results/wave-prototype-2026-03-14
git add results/ scripts/paper/run_track2_waves.sh scripts/erf_benchmark/run_llm_compare_benchmark.py
git commit -m "preserve prototype wave artifacts before batched restart"
```

If you only want to preserve artifacts/logs:

```bash
git add results/
git commit -m "archive track2 prototype results"
```

## 2) Batched Wave 1 Restart

Run batched Wave 1 with explicit artifact preservation:

```bash
./scripts/paper/track2_wave1_batched_restart.sh \
  --matrix benchmark/erf_llm_compare/train_subsample_s42.jsonl \
  --batch-size 20 \
  --sleep-sec 15 \
  --enforce-gates
```

The script writes to:

- `results/track2_recovery/wave1_batched_restart_<timestamp>/`
- `run.log` (batch-level orchestration log)
- `batch_status.csv` (batch-by-batch metrics + gate outcomes)
- `batches/batch_*/summary.json`
- `batches/batch_*/results.jsonl`
- `batches/batch_*/console_logs.jsonl`
- `batches/batch_*/explainability_calls.jsonl`

## 3) Solver-Generated Artifact Preservation

`run_llm_compare_benchmark.py` now forwards the following flags to each `amrex_agent.py` call when requested:

- `--save-workflow`
- `--save-transcript`
- `--save-log`

The batch restart script enables all three by default. Combined with `--verbose-cli`, this preserves:

- `workflow_history.json`
- `agent_transcript.txt`
- solver run logs
- `metrics.jsonl`
- verbose stderr/stdout traces that include top-k baseline context (when emitted by solver internals)

## 4) Gate Semantics

Current gate in batch script:

- `fail:hier_non_erf` if any hierarchical baseline-selection row does not include solver `ERF`.

With `--enforce-gates`, the script stops immediately on gate failure.

## 5) Promotion Rule for Wave 2/3

Only proceed to Wave 2/3 when:

- `batch_status.csv` has no failed gates,
- sentinel failures (`simple_failed_sentinel`, `hier_failed_sentinel`) are acceptable,
- and sampled batch outputs confirm expected solver/case/input extraction behavior.
