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
- `freeze_prompt_inputs.py`
  - Expands `prompt_matrix.jsonl` rows into explicit per-strategy frozen rows.
  - Output rows include `strategy` and can be replayed via
    `run_llm_compare_benchmark.py --frozen-inputs ...`.
- `diagnostic5_pelelmex_hierarchical_amsci2_faiss0.sh`
  - Runs a 5-row PeleLMeX hierarchical diagnostic using frozen inputs and a
    temporary `faiss_semantic_weight: 0.0` config override.
  - Logs CBORG spend before and after the run (with polling) as a routing
    guardrail.
  - Supports optional env vars: `MAX_ROWS`, `POLL_COUNT`,
    `POLL_INTERVAL_SEC`, `ALLOW_DIRTY`.

## Runner provenance flags

`run_llm_compare_benchmark.py` supports:

- `--frozen-inputs <path>`: use frozen JSONL rows instead of `--prompt-matrix`.
- `--allow-dirty`: bypass interactive dirty-tree confirmation.

Run artifacts now include:

- `summary.json`:
  - `audit.faiss_provenance.path|size_kb|modified|hash_or_mtime`
  - `audit.git.sha|dirty|dirty_files`
  - `audit.input_provenance.frozen_file`
- `results.jsonl` per row:
  - `run_id`, `git_sha`, `faiss_index_path`,
    `faiss_index_size_kb`, `faiss_index_modified`,
    `faiss_index_hash_or_mtime`, `frozen_input_file`

## Typical workflow

```bash
export LATEST=$(ls -td benchmark_remora/results/full_amsci2_faiss0_* | head -1)
scripts/erf_benchmark/latest_scan_console.sh
scripts/erf_benchmark/latest_case_map.sh | sort
scripts/erf_benchmark/latest_match_table.sh
```
