# isc-llm4hpc-paper-v1 Artifact Index

## Bundle Scope

- Paper bundle name: `isc-llm4hpc-paper-v1`
- Code snapshot commit: `2c2d60017707d48b63c5803fa0d80ffef43c6e3c`
- Code zip: `isc-llm4hpc-paper-v1_code_2c2d600.zip`
- Benchmark/evidence zip: `isc-llm4hpc-paper-v1_benchmark_and_evidence.zip`
- Manuscript binary: excluded from the committed release branch; retained as a local-only working document

## Numeric Claims Mapped To Saved Artifacts

- `0.922` weighted ERF score for `claude-sonnet-4-5`: matched by `benchmark_v2/results/full_amsci2_20260429T160959Z/summary.json` (`simple_weighted_score=0.922794`, `hierarchical_weighted_score=0.922794`), with release-facing summary in `benchmark_crosscode/latest/benchmark_summary.md`.
- `0.441` weighted ERF score for `lbl/cborg-deepthought`: matched by `benchmark_v2/results/full_cborg_20260427T202152Z/summary.json` (`simple_weighted_score=0.441912`), with release-facing summary in `benchmark_crosscode/latest/benchmark_summary.md`.
- `136-item` ERF frozen prompt set: matched by `benchmark_v2/prompt_matrix.jsonl` and summarized in `benchmark_crosscode/latest/benchmark_summary.md`.
- ERF case-match percentages `100%`, `47.1%`, and `50.7%`: matched by `benchmark_crosscode/latest/benchmark_summary.csv` and `benchmark_crosscode/latest/benchmark_summary.md` (source values `100.00`, `47.06`, and `50.74`).
- ERF token totals `3.47M` prompt and `50.8K` completion with about `68:1`: matched by `benchmark_v2/results/full_amsci2_20260429T160959Z/token_summary.txt` (`3,469,128` prompt, `50,823` completion, ratio about `68.26:1`).
- ERF open-weight token totals `1.92M` prompt and `647K` completion with about `3:1`: matched by `benchmark_v2/results/full_cborg_20260427T202152Z/token_summary.txt` (`1,916,931` prompt, `647,618` completion, ratio about `2.96:1`).
- PeleLMeX token ratio `about 23:1`: matched as a rounded workflow-summary aggregate across all `metrics.jsonl` files under `benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/`, including the strategy-level rollups and per-run `run_*/metrics.jsonl` records, which together yield `4037293 prompt / 179123 completion (22.54:1)`.
- Table 3 missing-parameter recovery claim: matched by `artifacts/self_correction/march18_ekman_spiral_workflow_history.json`, which records the Ekman Spiral recovery path referenced in the manuscript.
- Table 4 post-execution correction claim for `erf.fixed_dt`: matched by the generated e2e reproducibility artifact `.pytest-e2e/test_cli_full_mode_short_refle0/runs_full_mode_short/run_20260514_131839_294108/workflow_history.json`, which records a post-execution stability-consistency repair path from a user-requested `dt=20` to reviewer-guided `erf.fixed_dt=5` via `reason_code=postexec_stability_consistency`.

## External Or Non-Matching Claims

- Figure 1 provenance: external SIAM-talk reference. No local repository artifact was identified for the exact figure asset, so it is intentionally not claimed as part of the saved benchmark bundle.
- `57.91%` line coverage: matched by the historical repository validation snapshot `results/repo_validation_snapshot_20260313_102708/pytest_cov.log`, which records `TOTAL 20648 8066 8560 1049 57.91%`. This should be treated as a March 13, 2026 validation artifact, distinct from the current packaged local `.coverage` file, which reports `10.92%` under the present worktree state.
- `11.0%` of CBORG hierarchical selections outside the ERF catalog: supported as a documented derivation from investigation material. Row-level inspection identified `30` selections across both CBORG strategy runs landing outside the ERF case catalog, out of `272` total CBORG selections (`136` rows times `2` strategies), yielding `30/272 = 11.03%`, rounded to `11.0%`. Because the numerator is recovered from investigation output rather than emitted as a single packaged summary field, this claim should be treated as a derived computation.

## Directory Pointers

- Cross-code benchmark rollup: `benchmark_crosscode/latest/`
- ERF benchmark prompt set and saved summaries: `benchmark_v2/` and `benchmark_v2/results/full_amsci2_20260429T160959Z/`
- ERF open-weight comparison run: `benchmark_v2/results/full_cborg_20260427T202152Z/`
- PeleLMeX benchmark evidence: `benchmark_pelelmex/` and `benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/`
- REMORA benchmark evidence: `benchmark_remora/` and `benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/`
- Self-correction workflow artifact: `artifacts/self_correction/`
