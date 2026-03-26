# Audit batch_02
HEAD: e2603fa968244ca07b2aa8710074f97a0ed06833

## [UNNUMBERED-003] — Complexity Budget: File Size
PRD text: - no new amendment module >100 LOC without documented helper extraction.

### Q1: Implementation
src/services/sweep_orchestrator.py::orchestrate_sweep
src/services/result_aggregator.py::aggregate_results
src/services/sweep_detector.py::create_sweep_spec

### Q2: DRY
DUPLICATED
If duplicated: docs/PRD/PRD_v2605_AmendmentB1.md, docs/PRD/PRD_v2605_AmendmentB2.md, docs/PRD/PRD_v2605_AmendmentB4.md.

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  N/A | N/A | N/A

### Q6: Confidence
LOW
Risk: LOC/complexity budget is documented in PRD but not enforced by automated checks in this repo.
---
## [UNNUMBERED-003] — Sweep Phase Tests
PRD text: - unit tests per phase + integration test for fan-out/fan-in.

### Q1: Implementation
src/services/sweep_orchestrator.py::orchestrate_sweep
src/services/sweep_orchestrator.py::_fanout_children
src/services/sweep_orchestrator.py::_poll_children
src/services/result_aggregator.py::aggregate_results

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_orchestrator.py::TestSweepOrchestrator.test_fanout_spawns_correct_child_count
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  fan-out | YES | YES
  polling | YES | YES
  fan-in/summary | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: unit+integration coverage exists, but no e2e/oracle sweep pipeline test is present.
---
## [UNNUMBERED-004] — New Path Test Coverage
PRD text: - unit + integration tests for each new node/service path.

### Q1: Implementation
src/nodes/sweep_detection_node.py::sweep_detection_node
src/services/sweep_detector.py::detect_sweep_request
src/services/sweep_orchestrator.py::orchestrate_sweep
src/mcp_tools.py::mcp_get_sweep_status
src/mcp_tools.py::mcp_get_sweep_results

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_sweep_orchestrator.py::test_sweep_spec_created_from_detection
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_pelec

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  node/service additions | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: many new paths are covered, but per-path completeness is uneven across modules.
---
## [UNNUMBERED-005] — Stateless Deployment
PRD text: - Stateless deployment: no migration required.

### Q1: Implementation
src/models/graph_state_canonical.py::GRAPH_STATE_B1_B2_DEFAULTS
src/models/state_compatibility.py::ensure_state_compatibility
src/models/sweep_schemas.py::ParentSweepState.validate_counts

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_sweep_schemas.py::test_parent_sweep_state_validates_counts
  Integration (real):    tests/integration/test_infrastructure.py::test_workflow_store_roundtrip
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  migration/defaults | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: additive defaults indicate stateless rollout intent, but explicit migration-proof deployment test is limited.
---
## [F1.1] — Metrics Completeness
PRD text: - F1.1-F1.5 (all metrics must be collected)

### Q1: Implementation
src/utils/metrics.py::MetricsCollector.record_event
src/utils/metrics.py::MetricsCollector.record_llm_usage
src/utils/metrics.py::MetricsCollector.write_jsonl
src/main.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_metrics_collector.py::test_metrics_collector_aggregates_llm_tokens
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  capture | YES | YES
  aggregation | YES | PARTIAL
  paper-ready completeness | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: core metrics are instrumented, but full F1.1-F1.5 completeness is not exhaustively validated end-to-end.
---
## [F1.1] — Persona Mapping (Jamie)
PRD text: * **Mapping:** F1.1, F1.5.

### Q1: Implementation
src/utils/metrics.py::MetricsCollector.build_workflow_summary
src/benchmark_runner.py::_normalize_benchmark_record
src/benchmark_runner.py::_derive_benchmark_metrics_fields

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_gate_approvals_written_to_jsonl
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  user metrics aggregation | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: aggregation exists, but per-user budget controls (F1.5 depth) are not comprehensively asserted.
---
## [F1.2] — Strategy Logging + Load/Modify/Write
PRD text: * **Mapping:** F1.2, F3.2.

### Q1: Implementation
src/services/knowledge.py::_record_retrieval_metrics
src/utils/metrics.py::_aggregate_retrieval
src/mcp_tools.py::mcp_create_simulation_plan
src/mcp_tools.py::mcp_apply_plan

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_create_simulation_plan_returns_writer_output
  Integration (real):    tests/integration/l5_full_pipeline/test_cli_interface.py::test_cli_runs_end_to_end
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_remora

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  strategy capture | YES | PARTIAL
  apply pipeline | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: strategy metrics are recorded, but rationale-level assertions are sparse.
---
## [F1.2] — Strategy Rationale Tracking
PRD text: * **Mapping:** F1.2.

### Q1: Implementation
src/services/knowledge.py::_record_retrieval_metrics
src/utils/metrics.py::MetricsCollector.record_event
src/utils/metrics.py::_aggregate_retrieval

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_metrics_collector.py::test_metrics_collector_aggregates_llm_tokens
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_indexing_strategies
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  retrieval strategy logging | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: retrieval strategy events exist, but dedicated unit assertions for strategy rationale payload are limited.
---
## [F1.2] — Retrieval Ablation Metrics
PRD text: * **Mapping:** F1.2, F2.2.

### Q1: Implementation
src/benchmark_runner.py::run_model_benchmark
src/benchmark_runner.py::_build_command
src/utils/metrics.py::_aggregate_retrieval

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
  benchmark collection | YES | YES
  ablation evidence | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: benchmark plumbing exists, but full ablation/reporting closure remains partial.
---
## [F1.3] — Grid/Blocking Validation
PRD text: * **Mapping:** F1.3, F3.1.

### Q1: Implementation
src/services/validators/physics_validator.py::PhysicsValidator.validate
src/services/reviewer.py::ReviewerOrchestrator.review_plan
src/nodes/reviewer_node.py::reviewer_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_physics_validator.py::test_ref_ratio_blocking_factor_validation
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::test_full_graph_pipeline
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_erf

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  validation | YES | YES
  gate routing | YES | PARTIAL

### Q6: Confidence
HIGH
Risk: strongest gap is limited oracle-style validation for specific AMR mismatch scenarios.
---
## [F1.3] — Resource Pre-flight + Gating
PRD text: * **Mapping:** F1.3, F4.2.

### Q1: Implementation
src/services/validation.py::ValidationService.validate_full_setup
src/services/run_superfacility.py::run_superfacility
src/mcp_tools.py::mcp_validate_config

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_validation_service.py::test_validate_full_setup
  Integration (real):    tests/integration/test_schema_validator_integration.py::test_schema_validator_pipeline
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  config validation | YES | YES
  resource pre-flight | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: platform-specific resource estimation checks are present but not deeply exercised in integration tests.
---
## [F1.4] — PII Redaction in Logs
PRD text: * **Mapping:** F1.4.

### Q1: Implementation
src/utils/privacy.py::sanitize_payload
src/benchmark_runner.py::_write_jsonl_record
src/main.py::main

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
  sanitize events | YES | YES
  enforce everywhere | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: privacy scrubbing is implemented, but exhaustive coverage across all persisted payload shapes is not shown.
---
## [F1.4] — Convergence Metrics
PRD text: * **Mapping:** F1.4, F2.2.

### Q1: Implementation
src/benchmark_runner.py::_derive_benchmark_metrics_fields
src/nodes/reviewer_node.py::reviewer_node
src/nodes/analysis_node.py::analysis_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_iteration_count_present
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::test_error_recovery_records_iterations
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  iteration capture | YES | YES
  convergence reporting | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: iteration metrics exist, but explicit reflexion-convergence KPI tests are incomplete.
---
## [F2.1] — Solver Selection + Facility Exposure
PRD text: * **Mapping:** F2.1, F4.2.

### Q1: Implementation
src/services/architect.py::ArchitectService.select_solver
src/services/architect.py::ArchitectService.select_baseline
src/mcp_tools.py::mcp_select_baseline_case

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_solver_selection.py::test_select_solver_prefers_expected_solver
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_list_tools_and_validate_inputs
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  solver selection | YES | YES
  MCP exposure | YES | YES

### Q6: Confidence
HIGH
Risk: remaining risk is solver edge-cases outside covered fixtures.
---
## [F2.1] — Baseline Retrieval + Validation
PRD text: * **Mapping:** F2.1, F3.1.

### Q1: Implementation
src/services/cases.py::AMReXCasesService.find_local_cases
src/services/architect.py::ArchitectService._select_baseline
src/services/reviewer.py::ReviewerOrchestrator.review_plan

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_cases_service.py::test_find_local_cases
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::test_full_graph_pipeline
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  retrieval | YES | YES
  review gate | YES | PARTIAL

### Q6: Confidence
HIGH
Risk: review-gate behavior for unusual baselines still depends on heuristic logic.
---
## [F2.1] — Mechanism/Case Retrieval
PRD text: * **Mapping:** F2.1.

### Q1: Implementation
src/services/architect.py::ArchitectService.retrieve_context
src/services/architect.py::ArchitectService._extract_mechanism_from_makefile
src/services/cases.py::AMReXCasesService._keyword_match

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_context_retrieval.py::test_retrieve_context
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  retrieval | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: mechanism-specific retrieval correctness depends on repository content quality and indexing.
---
## [F2.2] — Deterministic Reproducibility
PRD text: * **Mapping:** F2.2.

### Q1: Implementation
scripts/eval_level0_ab.py::DeterministicEmbedder._embed
src/benchmark_runner.py::run_model_benchmark
src/utils/metrics.py::MetricsCollector.write_jsonl

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_contains_schema_valid_field
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_no_level0_regression
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  deterministic pieces | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: deterministic helpers exist, but hardware-cross reproducibility is not fully proven in this test suite.
---
## [F2.2] — Multi-model Benchmark Runs
PRD text: * **Mapping:** F2.2, F2.3.

### Q1: Implementation
scripts/run_benchmark.py::main
src/benchmark_runner.py::run_model_benchmark
src/benchmark_runner.py::_normalize_benchmark_record

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_benchmark_alignment_contract
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_pelec

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  benchmark execution | YES | YES
  model comparison evidence | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: benchmark runner is present, but full comparative camera-ready reporting path is still partial.
---
## [F2.4] — Automated Aggregation/Tables
PRD text: * **Mapping:** F2.4.

### Q1: Implementation
scripts/aggregate_metrics.py::main
scripts/compare_models.py::main
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
  postprocessing scripts | YES | ABSENT

### Q6: Confidence
LOW
Risk: scripts exist but lack direct automated tests in the current repository.
---
## [F2.5] — Scaling Analysis Section Presence
PRD text: Section requirement: **10.4 Scaling Analysis (Scientific Discovery Acceleration)** *(Feature ID: F2.5)*

### Q1: Implementation
benchmark/specs/case_schema.yaml::(scaling schema entries)
src/benchmark_runner.py::expand_case_runs
scripts/run_benchmark.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  scaling case definitions | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: section-aligned scaffolding exists, but dedicated scaling-law evaluation outputs are incomplete.
---
## [F2.5] — Reproducible and Traceable Scaling
PRD text: **Required Behavior:** Scaling analysis must be reproducible and traceable to benchmark artifacts.

### Q1: Implementation
src/benchmark_runner.py::run_model_benchmark
src/benchmark_runner.py::_write_jsonl_record
scripts/aggregate_metrics.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_no_new_required_field_breaks_existing
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  artifact traceability | YES | PARTIAL
  reproducibility proof | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: artifact capture is present, but reproducibility guarantees across reruns/hardware are not fully asserted.
---
## [F2.5] — Scaling Report Template
PRD text: 1) Scaling report template with required plots.

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
  template generation | NO | NO

### Q6: Confidence
HIGH
Risk: explicit scaling report template generation is not implemented in repository code.
---
## [F3.1] — Multi-tier Gating
PRD text: * **Mapping:** F3.1.

### Q1: Implementation
src/nodes/reviewer_node.py::reviewer_node
src/router_func.py::route_after_reviewer
src/utils/gate.py::run_llm_pre_gate
src/utils/gate.py::run_llm_post_gate

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_reviewer_orchestrator.py::test_reviewer_routes_rejected_to_retry
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::test_error_recovery_pipeline
  Oracle/E2E (pipeline): tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  reviewer gate | YES | YES
  route transitions | YES | PARTIAL

### Q6: Confidence
HIGH
Risk: main residual risk is policy behavior under uncommon mixed-error scenarios.
---
## [F3.2] — Typed Load-Modify-Write Path
PRD text: * **Mapping:** F3.2.

### Q1: Implementation
src/mcp_tools.py::mcp_create_proposed_modifications_with_plan
src/mcp_tools.py::mcp_apply_plan
src/services/config_model_factory.py::ConfigModelFactory.create_from_schema

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_create_simulation_plan_returns_writer_output
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::test_full_graph_pipeline
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_remora

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  typed plan build | YES | PARTIAL
  write/apply flow | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: typed-object guarantees are present but not enforced by a dedicated strict contract test for every path.
---
## [F4.1] — MCP Server Deployment
PRD text: * **Mapping:** F4.1.

### Q1: Implementation
mcp_server.py::handle_tool_call
mcp_server.py::main
src/services/workflow_store.py::WorkflowStore.upsert_session
src/services/workflow_store.py::WorkflowStore.get_session

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_list_tools_inprocess
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  tool serving | YES | YES
  session persistence | YES | PARTIAL

### Q6: Confidence
HIGH
Risk: scaling to true multi-user concurrency is not deeply stress-tested.
---
## [F4.2] — Validation Tool Exposure
PRD text: * **Mapping:** F4.2.

### Q1: Implementation
src/mcp_tools.py::mcp_validate_inputs
src/mcp_tools.py::mcp_validate_config
src/services/validation.py::ValidationService.validate_config
src/services/validators/schema_validator.py::SchemaValidator.validate

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_validate_config_returns_validation
  Integration (real):    tests/integration/test_schema_validator_integration.py::test_schema_validator_pipeline
  Oracle/E2E (pipeline): tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_list_tools_and_validate_inputs

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  tool-level validation | YES | YES
  cross-workflow usage | YES | PARTIAL

### Q6: Confidence
HIGH
Risk: provider/runtime edge-cases may still bypass some validation branches.
---
## [UNNUMBERED-003] — v26.05 Required Capability
PRD text: ✅ **Required Capability (v26.05):**

### Q1: Implementation
src/main.py::main
src/services/architect.py::ArchitectService.select_solver
src/nodes/reviewer_node.py::reviewer_node
src/utils/metrics.py::MetricsCollector.build_workflow_summary

### Q2: DRY
DUPLICATED
If duplicated: capability statements are repeated across docs/PRD/PRD_v2605.md sections.

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_solver_selection.py::test_select_solver_prefers_expected_solver
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::test_full_graph_pipeline
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_pelec

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  end-to-end capability | YES | PARTIAL

### Q6: Confidence
MEDIUM
Risk: broad capability statement spans multiple features and is only partially captured by current tests.
---
## [UNNUMBERED-004] — Provider Dependency Risk
PRD text: - Provider dependency risk (Anthropic API required)

### Q1: Implementation
src/config.py::get_llm_client
src/config.py::_LLMGateCompletions.create
src/main.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_config.py::test_detects_mcp
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_extended_infrastructure_backlog
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  provider abstraction | YES | PARTIAL

### Q6: Confidence
LOW
Risk: provider dependency is documented but risk mitigation coverage (fallback behavior across providers) is incomplete.
---
## [UNNUMBERED-005] — v26.05 Required Evidence
PRD text: **Required Evidence (v26.05):**

### Q1: Implementation
src/benchmark_runner.py::run_model_benchmark
scripts/aggregate_metrics.py::main
scripts/compare_models.py::main
src/utils/metrics.py::MetricsCollector.write_jsonl

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_contains_schema_valid_field
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_pelec

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
If multiple phases:
  Phase | Impl | Tests
  evidence capture | YES | YES
  evidence synthesis/reporting | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: core evidence artifacts are generated, but camera-ready evidence completeness remains partially manual.
---
## Session complete
Criteria audited: 29
Batch: batch_02
Worktree: wt-3
HEAD: e2603fa968244ca07b2aa8710074f97a0ed06833
