# ERF Benchmark Helpers

This directory includes helper scripts for inspecting `run_llm_compare_benchmark.py`
artifacts after a run.

These helpers use a single environment variable:

```bash
export LATEST=<path-to-benchmark-run-dir>
```

Example `LATEST` values:

- `benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z`
- `benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z`

## Helpers

- `latest_scan_console.sh`
  - Scans `console_logs.jsonl` and partial console logs for error-like keywords
    (`error`, `embedding`, `faiss`, `unavailable`, `401`, `403`, `traceback`).
- `latest_case_map.sh`
  - Prints sorted expected-to-selected case mappings:
    `strategy case_match expected_case -> selected_case`.
- `latest_match_table.sh`
  - Prints aggregate case/input match rates by strategy and by
    `group/subcase` extracted from `target_case_relpath` (for paths like
    `Exec/<group>/<subcase>`).

## Typical workflow

```bash
export LATEST=$(ls -td benchmark_remora/results/full_amsci2_faiss0_* | head -1)
scripts/erf_benchmark/latest_scan_console.sh
scripts/erf_benchmark/latest_case_map.sh | sort
scripts/erf_benchmark/latest_match_table.sh
```

