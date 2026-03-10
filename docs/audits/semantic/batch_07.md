# Audit batch_07
HEAD: 488e719dc8c75744318edabc8707d53550a8e441

## [UNNUMBERED-086] — Shared Indices + Metrics + Privacy
PRD text: **Required Behavior:** Provide shared indices, per-user metrics, and reproducibility controls with privacy safeguards.

### Q1: Implementation
mcp_server.py::handle_tool_call
src/services/workflow_store.py::WorkflowStore.upsert_session
src/utils/metrics.py::MetricsCollector.record_event
src/utils/privacy.py::sanitize_payload

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_list_sweeps_returns_all_in_session
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  shared index access | YES | PARTIAL
  per-user metrics/privacy | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: end-to-end proof combining all three concerns in one pipeline is limited.
---
## [UNNUMBERED-087] — MCP validate_config + Search
PRD text: - ✅ MCP server exposes `validate_config` and search tools with schema validation.

### Q1: Implementation
src/mcp_tools.py::mcp_validate_config
src/mcp_tools.py::mcp_validate_inputs
src/mcp_tools.py::mcp_query_knowledge
src/services/validation.py::ValidationService.validate_config

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_validate_config_returns_validation
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_list_tools_and_validate_inputs
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  tool exposure | YES | YES
  schema validation path | YES | YES

### Q6: Confidence
HIGH
Risk: remaining risk is behavior under malformed external MCP clients.
---
## [UNNUMBERED-088] — Per-user Token Aggregation Without PII
PRD text: - ✅ Token usage can be aggregated per user without storing PII.

### Q1: Implementation
src/utils/metrics.py::MetricsCollector.record_llm_usage
src/utils/privacy.py::sanitize_payload
src/benchmark_runner.py::_write_jsonl_record

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_privacy.py::test_benchmark_jsonl_scrubs_prompt
  Integration (real):    tests/integration/test_privacy_scrubber_selection.py::test_privacy_scrubber_selection
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  token collection | YES | PARTIAL
  pii scrubbing | YES | YES

### Q6: Confidence
MEDIUM
Risk: user-level aggregation semantics are present but not deeply asserted across all metric sinks.
---
## [UNNUMBERED-089] — Deterministic Benchmarking
PRD text: - ✅ Benchmark runs are deterministic across hardware where feasible.

### Q1: Implementation
scripts/eval_level0_ab.py::DeterministicEmbedder._embed
src/benchmark_runner.py::run_model_benchmark

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_no_level0_regression
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  deterministic components | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: deterministic behavior is partially implemented but not fully demonstrated across hardware classes.
---
## [UNNUMBERED-090] — Dev Team Story 2
PRD text: * **Story 2:** As the Dev Team, I want to automate LaTeX table generation from `metrics.jsonl`, so I can meet the camera

### Q1: Implementation
scripts/aggregate_metrics.py::main
scripts/compare_models.py::main
scripts/generate_paper_tables.py::NOT FOUND

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  aggregation scripts | YES | ABSENT
  latex generation | NO | NO

### Q6: Confidence
LOW
Risk: table generation script named in PRD is missing in this repository state.
---
## [UNNUMBERED-091] — Dev Team Story 3
PRD text: * **Story 3:** As the Dev Team, I want to measure the "reflexion convergence" rate, so I can prove the effectiveness of

### Q1: Implementation
src/nodes/reviewer_node.py::reviewer_node
src/router_func.py::route_after_reviewer
src/benchmark_runner.py::_derive_benchmark_metrics_fields

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_reviewer_retry_count_present
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::test_reviewer_rejection_triggers_retry
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  retry counting | YES | YES
  convergence KPI | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: retry/convergence proxies exist, but explicit convergence-rate output is not fully formalized.
---
## [UNNUMBERED-092] — Dev Team Story 4
PRD text: * **Story 4:** As the Dev Team, I want to quantify the LOC savings from framework knowledge reuse, so I can justify the

### Q1: Implementation
database/indexing/level0_builder.py::Level0Builder.build
database/indexing/level1_builder.py::Level1Builder.build
src/services/config_model_factory.py::ConfigModelFactory.create_from_schema

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level0_index.py::test_level0_builder_outputs_indices
  Integration (real):    tests/integration/test_config_model_factory_integration.py::test_config_model_factory_integration
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  reuse mechanisms | YES | PARTIAL
  loc accounting | NO | NO

### Q6: Confidence
LOW
Risk: LOC-savings measurement/reporting is not implemented as an automated metric.
---
## [UNNUMBERED-093] — Dev Team Story 5
PRD text: * **Story 5:** As the Dev Team, I want to track retrieval success per index level, so I can conduct an ablation study fo

### Q1: Implementation
src/services/knowledge.py::_record_retrieval_metrics
src/utils/metrics.py::_aggregate_retrieval
database/indexing/level0_searcher.py::Level0Searcher.search

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_context_retrieval.py::test_level1_multi_index_search
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  retrieval strategy logging | YES | PARTIAL
  level-by-level ablation | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: index-level success tracking is partial and not fully surfaced in final report artifacts.
---
## [UNNUMBERED-094] — Camera-ready Benchmark Pipeline
PRD text: **Required Behavior:** End-to-end benchmark automation, aggregation scripts, and reproducible tables for camera-ready su

### Q1: Implementation
scripts/run_benchmark.py::main
src/benchmark_runner.py::run_model_benchmark
scripts/aggregate_metrics.py::main
scripts/generate_paper_tables.py::NOT FOUND

### Q2: DRY
DUPLICATED
If duplicated: benchmark orchestration responsibilities overlap between scripts/run_benchmark.py and src/benchmark_runner.py.

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_benchmark_alignment_contract
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  benchmark execution | YES | YES
  aggregation | YES | PARTIAL
  table generation | NO | NO

### Q6: Confidence
LOW
Risk: missing table-generation implementation blocks complete camera-ready automation.
---
## [UNNUMBERED-095] — Unattended Benchmark Suite
PRD text: - ✅ Benchmark suite runs unattended across target models.

### Q1: Implementation
scripts/run_benchmark.py::main
src/benchmark_runner.py::run_model_benchmark
src/benchmark_runner.py::_build_command

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_benchmark_alignment_contract
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  unattended run loop | YES | YES

### Q6: Confidence
MEDIUM
Risk: target-model breadth depends on local credentials/configuration not enforced by tests.
---
## [UNNUMBERED-096] — Tables 1-5 from metrics.jsonl
PRD text: - ✅ Tables 1–5 are generated from `metrics.jsonl` without manual edits.

### Q1: Implementation
scripts/generate_paper_tables.py::NOT FOUND
scripts/aggregate_metrics.py::main
scripts/compare_models.py::main

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  table generation | NO | NO

### Q6: Confidence
HIGH
Risk: this acceptance criterion is currently unmet because the referenced generator is missing.
---
## [UNNUMBERED-097] — Reproducible Ablation + Convergence
PRD text: - ✅ Ablation and convergence analyses are reproducible from artifacts.

### Q1: Implementation
src/benchmark_runner.py::_normalize_benchmark_record
src/benchmark_runner.py::_derive_benchmark_metrics_fields
scripts/aggregate_metrics.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_iteration_count_present
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::test_analysis_failure_triggers_retry
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  artifact capture | YES | YES
  ablation synthesis | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: reproducibility artifacts exist but full ablation outputs are not comprehensively validated.
---
## [UNNUMBERED-098] — Stable Queryable Index Hierarchy
PRD text: **Required Behavior:** Maintain a stable, queryable index hierarchy with deterministic snapshots for benchmarks.

### Q1: Implementation
database/indexing/level0_searcher.py::Level0Searcher.search
database/indexing/level1_searcher.py::Level1Searcher.search_all_docs
database/indexing/level2_searcher.py::Level2Searcher.search_all_cases
src/services/faiss_artifacts.py::_load_manifest_from_path

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level1_builder.py::test_level1_content_indexed
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  l0/l1/l2 querying | YES | PARTIAL
  deterministic snapshots | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: query hierarchy exists, but deterministic snapshot guarantees are only partially enforced.
---
## [UNNUMBERED-099] — L0/L1/L2 Load + Top-k
PRD text: - ✅ L0/L1/L2 indices load without errors and return top-k matches.

### Q1: Implementation
database/indexing/level0_searcher.py::Level0Searcher.search
database/indexing/level1_searcher.py::Level1Searcher._search_single_index
database/indexing/level2_searcher.py::Level2Searcher._search_index

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level2_searcher.py::test_combine_scores_keeps_best_per_index
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_pelec

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  index loading | YES | PARTIAL
  top-k response | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: integration coverage depends on local index availability and uses skips/xfails in some paths.
---
## [UNNUMBERED-100] — Index Manifests Versioned
PRD text: - ✅ Index manifests include versioning and timestamps for reproducibility.

### Q1: Implementation
src/services/faiss_artifacts.py::_load_manifest_from_url
src/services/faiss_artifacts.py::_load_manifest_from_path
src/benchmark_runner.py::run_model_benchmark

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  manifest loading | YES | ABSENT
  reproducibility metadata checks | PARTIAL | ABSENT

### Q6: Confidence
LOW
Risk: manifest support exists but version/timestamp enforcement is weakly tested.
---
## [UNNUMBERED-101] — Chemistry Index Resolution
PRD text: - ✅ Chemistry indices resolve mechanism files referenced in inputs.

### Q1: Implementation
src/services/architect.py::ArchitectService._extract_mechanism_from_makefile
database/indexing/level2_searcher.py::Level2Searcher.search_all_cases
src/services/cases.py::AMReXCasesService._keyword_match

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_context_retrieval.py::test_level1_multi_index_search
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_schema_valid
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  mechanism resolution | PARTIAL | PARTIAL

### Q6: Confidence
LOW
Risk: explicit chemistry-index-to-input-reference linkage is not strongly asserted by dedicated tests.
---
## [UNNUMBERED-102] — Deterministic Strategy Selection
PRD text: **Required Behavior:** Deterministic strategy selection with explicit rationale and clear fallback rules.

### Q1: Implementation
src/config.py::AMReXAgentConfig
src/services/architect.py::ArchitectService.select_baseline
src/services/knowledge.py::_record_retrieval_metrics
src/router_func.py::route_after_reviewer

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_node_history.py::test_indexing_calls_are_cumulative
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  strategy choice | YES | YES
  rationale/fallback | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: deterministic selection exists, but rationale completeness and fallback clarity are only partially asserted.
---
## [UNNUMBERED-103] — Strategy Logged with Alternatives
PRD text: - ✅ Strategy selection logged with alternatives and rationale.

### Q1: Implementation
src/utils/metrics.py::MetricsCollector.record_event
src/services/knowledge.py::_record_retrieval_metrics
src/mcp_tools.py::mcp_create_simulation_plan

### Q2: DRY
DUPLICATED
If duplicated: strategy fields appear in both workflow payloads and metrics payloads (src/mcp_tools.py, src/utils/metrics.py).

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_node_history.py::test_indexing_calls_are_cumulative
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  strategy log | YES | PARTIAL
  alternatives/rationale detail | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: alternatives/rationale richness is not consistently validated.
---
## [UNNUMBERED-104] — Static Strategy Explicit Override
PRD text: - ✅ Static strategy only triggers via explicit overrides.

### Q1: Implementation
src/config.py::AMReXAgentConfig
src/main.py::main
src/services/architect.py::ArchitectService.select_baseline

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_config_extended.py::test_override_static_configuration
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  override trigger | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: explicit override behavior is covered, but not all call surfaces are tested uniformly.
---
## [UNNUMBERED-105] — Simple Strategy for Known Prompts
PRD text: - ✅ Simple strategy used for known chemistry/tagged prompts.

### Q1: Implementation
src/config.py::AMReXAgentConfig
src/services/architect.py::ArchitectService.select_solver
src/services/architect.py::ArchitectService.select_baseline

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_solver_selection.py::test_select_solver_prefers_expected_solver
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_erf

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  simple strategy route | YES | YES

### Q6: Confidence
MEDIUM
Risk: tagged/known prompt detection heuristics may vary by dataset quality.
---
## [UNNUMBERED-106] — Reuse Measurability + Cost
PRD text: **Required Behavior:** Maintain measurable reuse across codes and document per-code customization cost.

### Q1: Implementation
database/indexing/level0_builder.py::Level0Builder.build
database/indexing/level1_builder.py::Level1Builder.build
src/services/config_model_factory.py::ConfigModelFactory.create_from_schema

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level2_extensions.py::test_level2_solver_agnostic_indexing
  Integration (real):    tests/integration/test_config_model_factory_integration.py::test_config_model_factory_integration
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  cross-code reuse | YES | PARTIAL
  customization cost reporting | NO | NO

### Q6: Confidence
LOW
Risk: reuse mechanisms exist, but measurable per-code cost accounting is not implemented.
---
## [UNNUMBERED-107] — L0 Reuse Across Solvers
PRD text: - ✅ L0 indices reused across all supported solvers.

### Q1: Implementation
database/indexing/level0_builder.py::Level0Builder.build
database/indexing/level0_searcher.py::Level0Searcher.search
src/services/architect.py::ArchitectService.select_solver

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level0_index.py::test_level0_builder_outputs_indices
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_remora

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  l0 reuse | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: true all-solver reuse still depends on local availability of each solver's assets.
---
## [UNNUMBERED-108] — Onboarding LOC Metric
PRD text: - ✅ Per-code onboarding effort measured and reported (<300 LOC target or updated range).

### Q1: Implementation
NOT FOUND

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  loc measurement/report | NO | NO

### Q6: Confidence
HIGH
Risk: no automated LOC-onboarding measurement/reporting implementation was found.
---
## [UNNUMBERED-109] — Generalization in Camera-ready Tables
PRD text: - ✅ Generalization metrics included in camera-ready tables.

### Q1: Implementation
scripts/compare_models.py::main
scripts/generate_paper_tables.py::NOT FOUND
src/benchmark_runner.py::run_model_benchmark

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_benchmark_alignment_contract
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  metric extraction | YES | PARTIAL
  table publication path | NO | NO

### Q6: Confidence
LOW
Risk: missing table-generation implementation prevents complete compliance.
---
## [UNNUMBERED-110] — Tiered Validation + Retry Guidance
PRD text: **Required Behavior:** Enforce tiered validation with consistent severity handling and retry guidance.

### Q1: Implementation
src/services/validation.py::ValidationService.validate_full_setup
src/nodes/reviewer_node.py::reviewer_node
src/services/reviewer.py::ReviewerOrchestrator.review_plan
src/router_func.py::route_after_reviewer

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_retry_guidance.py::test_analysis_retry_guidance_from_issues
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::test_reviewer_rejection_triggers_retry
  Oracle/E2E (pipeline): tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  validation tiers | YES | PARTIAL
  severity/retry guidance | YES | YES

### Q6: Confidence
HIGH
Risk: severity normalization across all validator outputs is the main remaining consistency risk.
---
## Session complete
Criteria audited: 25
Batch: batch_07
Worktree: wt-3
HEAD: 488e719dc8c75744318edabc8707d53550a8e441
