# ERF LLM-Compare Reachability Benchmark

## Purpose
Define a reproducible benchmark to verify ERF baseline-case and `inputs*` selection reachability via CLI using:
- `--inputs-file-strategy llm_compare`
- `--indexing-strategy simple`
- `--indexing-strategy hierarchical`

This benchmark is designed to support iterative tuning through:
1. Prompt-wave design
2. Strategy-specific baseline scoring weights
3. ERF-specific prompt templates (without overfitting)

## Scope
In scope:
- Every `inputs*` file under `../ERF/Exec/**`
- End-to-end CLI dry runs (`python amrex_agent.py ... --run-mode dry --json`)
- Match evaluation for both selected case and selected inputs file

Out of scope:
- `override_static` strategy (not prompt-driven baseline routing)
- Runtime execution fidelity/performance benchmarking
- Non-ERF full benchmark suites (only small sanity checks)

## Success Criteria
Per indexing strategy (`simple`, `hierarchical`), require:
- Weighted score >= 0.90
- No holdout regression vs baseline run
- No non-ERF sanity regression beyond tolerance

Weighted score (locked):
- `0.70 * case_accuracy + 0.30 * inputs_accuracy`

LLM availability policy (locked):
- If any run reports `llm_unavailable` fallback for `llm_compare`, abort benchmark and fail run.

## Why This Is Needed (Lessons Learned)
`src/services/cases.py` is not sufficient for this objective because:
- It is case-level, not input-file-level.
- It does not directly validate `input_writer` `llm_compare` outcomes.
- It cannot prove per-`inputs*` file reachability through CLI end-to-end flow.

The benchmark must score the actual CLI output fields from `workflow_history` and top-level result payload.

## Two-Pass Workflow

### Pass 1: Dataset + Prompt Matrix Generation (No Model Calls)
Generate immutable benchmark inputs from repository truth.

Inputs:
- `../ERF/Exec/**/inputs*`

Outputs:
- `benchmark/erf_llm_compare/prompt_matrix.jsonl`
- `benchmark/erf_llm_compare/manifest.json`
- `benchmark/erf_llm_compare/splits/train_ids.json`
- `benchmark/erf_llm_compare/splits/holdout_ids.json`
- `benchmark/erf_llm_compare/splits/holdout_paraphrase_ids.json`

Each matrix row must contain at least:
- `row_id`
- `target_case_relpath`
- `target_inputs_relpath`
- `target_inputs_filename`
- `category`
- `wave_id` (`wave0`, `wave1`, `wave2`)
- `prompt_text`
- `strategy_targets` (`["simple", "hierarchical"]`)

Prompt waves:
- `wave0`: baseline natural prompt from case/input semantics
- `wave1`: improved disambiguation wording
- `wave2`: stronger but still generic phrasing

Split policy:
- deterministic split with fixed seed
- holdout ratio default 20%
- paraphrase holdout subset default 30% of holdout

### Pass 2: Independent CLI Evaluation
Consume pass-1 artifacts and run CLI as a black-box scorer.

Command template:
```bash
python amrex_agent.py \
  --indexing-strategy {simple|hierarchical} \
  --prompt "{prompt_text}" \
  --inputs-file-strategy llm_compare \
  --run-mode dry \
  --json
```

Parse from output JSON:
- selected case path (`selected_case` and/or architect history details)
- selected input path (`inputs_file_selected` / `used_inputs_file` and/or input_writer details)
- fallback metadata (`fallback_reason`, strategy metadata)

Abort condition:
- Any `llm_unavailable` fallback in `llm_compare` path

## Match and Scoring Rules
For each row:
- `case_match = 1` if selected case equals `target_case_relpath`, else `0`
- `inputs_match = 1` if selected input file/path equals target input, else `0`
- row score = `0.7 * case_match + 0.3 * inputs_match`

Aggregate per strategy:
- `case_accuracy = mean(case_match)`
- `inputs_accuracy = mean(inputs_match)`
- `weighted_score = mean(row score)`

Report required:
- overall metrics per strategy
- per-category metrics
- top miss clusters
- failure CSV with expected vs predicted case/input

## Anti-Overfit Requirements

### 1) Fixed Train/Holdout Protocol
- Tune only on train split.
- Holdout is never used for tuning decisions.

### 2) Holdout Paraphrase Gate
- Evaluate on paraphrase holdout subset.
- Candidate must not materially regress vs standard holdout.

### 3) Category Guardrails
- Report category-level weighted score.
- Initial guardrail: no category below 0.75.

### 4) Non-ERF Sanity Set
- Small fixed set from non-ERF solvers.
- Candidate must not regress by more than 0.03 weighted score vs baseline.

### 5) Baseline-vs-Candidate Acceptance
A candidate tuning run is accepted only if all are true:
1. Holdout weighted score improves or stays neutral.
2. Per-strategy pass criterion (>= 0.90) is met.
3. Paraphrase and category guardrails pass.
4. Non-ERF sanity regression tolerance passes.

## Tuning Levers

### A) Strategy-Specific Weights (Primary)
Expose and use config fields for both `simple` and `hierarchical` default bucket weights:
- `*_weight_kb_relevance`
- `*_weight_metrics`
- `*_weight_path_heuristics`
- `*_weight_domain_specific`
- `*_weight_faiss_semantic`

Architect must normalize and log `weights_used`.

### B) Prompt-Wave Selection (Secondary)
Select wave family (`wave0/1/2`) based on train results, validated on holdout.

### C) ERF Prompt Templates (Secondary)
Tune `database/configs/erf_config.py` prompt templates for ERF-specific disambiguation.

Guardrails against overfitting:
- no direct case-name hardcoding intended to memorize benchmark IDs
- all template changes must pass holdout/paraphrase/non-ERF gates

## Tuning Workflow

### Step A: Baseline Run
- Use current templates and current config weights.
- Run pass-2 evaluation on train, holdout, holdout paraphrase, and non-ERF sanity datasets.
- Persist baseline summary at:
  - `benchmark/erf_llm_compare/runs/{run_id}/summary_baseline.json`

### Step B: Tuning Loop
Allowed knobs:
1. strategy-specific config weights
2. ERF prompt templates
3. prompt wave selection (`wave0`, `wave1`, `wave2`)

For each candidate:
- evaluate on train first
- if train improves, evaluate holdout + paraphrase + non-ERF sanity
- keep candidate only if all acceptance gates pass

### Step C: Final Candidate Selection
Select best accepted candidate by:
1. highest mean holdout weighted score across strategies
2. tie-breaker: lower variance across categories
3. tie-breaker: fewer catastrophic misses

## Implementation Artifacts
New scripts:
- `scripts/erf_benchmark/generate_prompt_matrix.py`
- `scripts/erf_benchmark/make_splits.py`
- `scripts/erf_benchmark/make_sanity_prompt_set.py`
- `scripts/erf_benchmark/run_llm_compare_benchmark.py`
- `scripts/erf_benchmark/compare_runs.py`

Run outputs:
- `benchmark/erf_llm_compare/runs/{run_id}/results.jsonl`
- `benchmark/erf_llm_compare/runs/{run_id}/summary.json`
- `benchmark/erf_llm_compare/runs/{run_id}/summary_baseline.json` (baseline step only)
- `benchmark/erf_llm_compare/runs/{run_id}/category_report.csv`
- `benchmark/erf_llm_compare/runs/{run_id}/failures.csv`
- `benchmark/erf_llm_compare/runs/{run_id}/explainability_calls.jsonl`
- `benchmark/erf_llm_compare/runs/{run_id}/explainability_failures.csv`

## Validation and Tests
Unit tests should cover:
- dataset generation completeness and determinism
- split reproducibility
- JSON parsing and match extraction
- scoring correctness
- abort-on-llm-unavailable behavior

Integration tests should cover:
- small sampled end-to-end run for each strategy
- config weight loading and architect weight application

## Operational Defaults
- Benchmark mode: `--run-mode dry`
- Indexing strategies: `simple`, `hierarchical`
- Scoring blend: `70/30`
- Holdout ratio: `20%`
- Paraphrase subset: `30% of holdout`
- Non-ERF sanity set: `20 prompts`

## Reproducibility Requirements
Every run must persist:
- benchmark script version/hash
- ERF repo commit hash
- agent repo commit hash
- split seed and split files
- config file path and effective weight values
- timestamped output directory
