# Audit batch_04
HEAD: e2603fa968244ca07b2aa8710074f97a0ed06833

## [UNNUMBERED-010] — Interactive gating and evidence capture
PRD text: **Required Behavior:** Interactive gating, retrieval evidence, and metrics must be captured for baseline selection workf

### Q1: Implementation
src/interactive_service.py::invoke_tool
src/policy/gate_policy.py::evaluate_gate_policy
src/services/architect.py::ArchitectService.select_solver
src/services/architect.py::ArchitectService.select_baseline
src/benchmark_runner.py::_write_jsonl

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_interactive_service.py::test_invoke_tool_writes_gate_approval_record
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_list_tools_and_validate_inputs
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Retrieval evidence is recorded indirectly (history/plan fields), not as a single explicit audit payload.
---
## [UNNUMBERED-011] — L0/L2 consistency
PRD text: - ✅ Solver and baseline selection match L0/L2 evidence.

### Q1: Implementation
src/services/architect.py::ArchitectService.select_solver
src/services/architect.py::ArchitectService.select_baseline
src/services/architect.py::ArchitectService._apply_solver_selection_trace
src/nodes/architect_node.py::architect_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_node_history.py::test_history_includes_level0_and_level2_override_trace
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: L2 evidence quality still depends on local index quality/availability.
---
## [UNNUMBERED-012] — metrics.jsonl strategy and iteration
PRD text: - ✅ Metrics captured in `metrics.jsonl` with strategy and iteration.

### Q1: Implementation
src/benchmark_runner.py::_derive_iteration_fields
src/benchmark_runner.py::_write_jsonl
src/utils/metrics.py::MetricsCollector.build_workflow_summary
scripts/aggregate_metrics.py::_extract_strategy

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_iteration_count_present
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_benchmark_harness_generates_metrics_bundle
  Oracle/E2E (pipeline): tests/e2e/test_readme_command_runner.py::test_readme_commands_registry_entries_execute

### Q4: Mock fidelity
DRIFTED
If drifted: tests/integration/fixtures/state_initialization.py uses `max_iterations` while canonical schema defines `max_retries`.

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Iteration is explicit, but strategy may be absent unless upstream payload includes retrieval/indexing strategy fields.
---
## [UNNUMBERED-013] — README rationale
PRD text: - ✅ README explains solver/baseline rationale.

### Q1: Implementation
README.md::(strategy and baseline override sections)

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    tests/e2e/test_readme_command_registry.py::test_registry_points_to_existing_targets
  Oracle/E2E (pipeline): tests/e2e/test_readme_command_runner.py::test_readme_commands_registry_entries_execute

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: README covers behavior but does not fully tie rationale back to every PRD acceptance clause.
---
## [UNNUMBERED-014] — Solver disambiguation alternatives
PRD text: **Required Behavior:** Solver disambiguation must show alternatives and evidence with confidence.

### Q1: Implementation
src/services/architect.py::ArchitectService.select_solver
src/services/architect.py::ArchitectService._apply_level2_case_name_override
src/nodes/architect_node.py::architect_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_solver_selection.py::test_level0_confidence_threshold
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Solver alternatives/rejection rationale are not exposed as a structured alternatives list.
---
## [UNNUMBERED-015] — Alternatives with rejection reasons
PRD text: - ✅ Alternatives listed with rejection reasoning.

### Q1: Implementation
src/services/architect.py::ArchitectService.select_baseline
src/services/architect.py::ArchitectService.select_solver

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_baseline_selection.py::test_level2_fallback_ranking
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Candidates are listed, but explicit rejected-alternative reasoning is not implemented.
---
## [UNNUMBERED-016] — L0 citations and confidence
PRD text: - ✅ Evidence includes L0 citations and confidence.

### Q1: Implementation
src/services/architect.py::ArchitectService.select_solver
src/services/plan.py::SimulationPlan
src/nodes/architect_node.py::architect_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_node_history.py::test_history_includes_level0_and_level2_override_trace
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Confidence is present but source citation granularity (document-level L0 citations) is missing.
---
## [UNNUMBERED-017] — User sees context before approval
PRD text: - ✅ User can view detailed context before approval.

### Q1: Implementation
src/utils/gate.py::run_preconfirm_gate
src/interactive_service.py::invoke_tool

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_interactive_service.py::test_preconfirm_gate_writes_gate_approval_record
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: CLI preconfirm prints context, but MCP gating returns structured gate status without a rich context preview channel.
---
## [UNNUMBERED-018] — Gate 6 reviewer threshold
PRD text: - Reviewer must catch ≥90% for Gate 6 pass

### Q1: Implementation
src/services/validators/physics_validator.py::PhysicsValidator.validate
src/services/rule_engine.py::RuleEngine.validate

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_physics_validator.py::test_rule_engine_error_is_reported
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: No explicit measured Gate 6 recall metric test asserting the ≥90% threshold.
---
## [UNNUMBERED-019] — Physics inconsistency validation and fixes
PRD text: **Required Behavior:** Validation must catch physics inconsistencies and provide actionable fixes.

### Q1: Implementation
src/services/validators/physics_validator.py::PhysicsValidator.validate
src/services/rule_engine.py::RuleEngine.validate
src/services/reviewer.py::ReviewerService.validate_plan

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_physics_validator.py::test_rejects_multiple_solvers
  Integration (real):    tests/integration/l5_full_pipeline/test_schema_validation.py::test_pipeline_rejects_invalid_schema
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
DRIFTED
If drifted: tests/integration/fixtures/state_initialization.py uses `max_iterations` and `run_status` instead of canonical `max_retries` and `job_status`.

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Validation catches inconsistencies, but actionable fix quality depends on rule message quality and is uneven across solvers.
---
## [UNNUMBERED-020] — ≥90% injected physics errors caught
PRD text: - ✅ ≥90% injected physics errors caught (Gate 6 threshold).

### Q1: Implementation
src/services/validators/physics_validator.py::PhysicsValidator.validate
src/services/rules/physics.py::(solver-specific rule functions)

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_physics_validator.py::test_rejects_unknown_solver
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: No test or benchmark computes/locks an injected-error catch-rate at or above 90%.
---
## [UNNUMBERED-021] — Fix suggestions include evidence
PRD text: - ✅ Error output includes fix suggestions with evidence.

### Q1: Implementation
src/services/rules/base.py::RuleViolation
src/services/validators/physics_validator.py::PhysicsValidator.validate
src/services/feedback_generator.py::FeedbackGenerator.generate

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_feedback_generator.py::test_generates_actionable_feedback
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Suggested fixes exist via `RuleViolation.suggested_fix`, but explicit evidence linkage is inconsistent.
---
## [UNNUMBERED-022] — Structured validation metrics
PRD text: - ✅ Validation metrics captured in structured output.

### Q1: Implementation
src/benchmark_runner.py::_derive_validation_fields
src/benchmark_runner.py::_write_jsonl
src/utils/metrics.py::_aggregate_validation

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_contains_physics_valid_field
  Integration (real):    tests/integration/helpers/schema_validator.py::validate_graph_state_schema
  Oracle/E2E (pipeline): tests/e2e/test_readme_command_runner.py::test_readme_commands_registry_entries_execute

### Q4: Mock fidelity
DRIFTED
If drifted: integration fixture state includes legacy aliases (`max_iterations`) not canonical (`max_retries`).

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Structured fields exist, but coverage depends on review payload completeness.
---
## [UNNUMBERED-023] — Use case to artifact mapping
PRD text: **Required Behavior:** Each new capability use case maps to at least one test/fixture or benchmark artifact.

### Q1: Implementation
docs/coverage_map.md::(coverage mapping sections)
tests/integration/test_oracle_benchmarks.py::(benchmark-backed gates)

### Q2: DRY
DUPLICATED
If duplicated: docs/coverage_map.md and docs/deployment_readiness.md both partially map similar coverage metadata.

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_benchmark_alignment_contract
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Mapping is partial and not enforced as a strict one-to-one requirement for every new use case.
---
## [UNNUMBERED-024] — Use case references artifact
PRD text: - ✅ Each use case references a test, fixture, or benchmark artifact.

### Q1: Implementation
docs/deployment_readiness.md::(testing strategy table)
docs/coverage_map.md::(worktree/test mapping)

### Q2: DRY
DUPLICATED
If duplicated: docs/deployment_readiness.md, docs/coverage_map.md.

### Q3: Test pyramid
  Unit (mocked deps):    tests/quality/test_standards.py::test_contract_test_paths_exist
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Documentation references many artifacts, but no automated check guarantees every use case has one.
---
## [UNNUMBERED-025] — UC4-UC7 cost and iteration metrics
PRD text: - ✅ Cost/iteration metrics are measurable for UC4-UC7.

### Q1: Implementation
src/benchmark_runner.py::_derive_iteration_fields
src/utils/metrics.py::MetricsCollector.build_workflow_summary
scripts/aggregate_metrics.py::to_raw_record

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_iteration_count_present
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_benchmark_harness_generates_metrics_bundle
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
DRIFTED
If drifted: legacy test fixtures populate `max_iterations`; canonical schema uses `max_retries`.

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Iteration metrics are measurable, but UC4-UC7 traceability tags are not explicitly encoded in metric records.
---
## [UNNUMBERED-026] — Use case trace to Phase 1 feature IDs
PRD text: - ✅ Use cases trace to feature IDs in Phase 1.

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
N/A

### Q6: Confidence
NONE
Risk: No code/doc artifact was found that enforces use-case-to-Phase-1 feature-ID traceability.
---
## [UNNUMBERED-027] — A2A sweeps reuse baseline and track costs
PRD text: **Required Behavior:** A2A sweeps must reuse baselines, track costs, and surface aggregate outputs.

### Q1: Implementation
src/services/sweep_orchestrator.py::orchestrate_sweep
src/services/sweep_orchestrator.py::_run_architect_phase
src/services/result_aggregator.py::aggregate_results

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_orchestrator.py::test_execution_sweep_architect_runs_once
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Baseline reuse and aggregation exist, but cost tracking for sweeps is not complete.
---
## [UNNUMBERED-028] — Baseline planned once and reused
PRD text: - ✅ Baseline planned once and reused across child workflows.

### Q1: Implementation
src/services/sweep_orchestrator.py::orchestrate_sweep
src/services/sweep_orchestrator.py::_run_architect_phase

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_orchestrator.py::test_execution_sweep_architect_runs_once
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Reuse assumes child-specific plan mutations do not require re-planning for every parameter.
---
## [UNNUMBERED-029] — Sweep savings vs naive
PRD text: - ✅ Sweep reports cost and token savings vs naive runs.

### Q1: Implementation
scripts/aggregate_metrics.py::_group_summary
src/services/result_aggregator.py::aggregate_results

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_result_aggregator.py::test_successful_children_aggregated
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Sweep summaries aggregate metrics but do not compute explicit naive-vs-sweep savings deltas.
---
## [UNNUMBERED-030] — Post-run aggregated outputs
PRD text: - ✅ Aggregated results produced post-run.

### Q1: Implementation
src/services/result_aggregator.py::aggregate_results
src/mcp_tools.py::mcp_get_sweep_results

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_result_aggregator.py::test_summary_json_has_required_keys
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Aggregation works when child result summaries are present and well-formed.
---
## [UNNUMBERED-031] — Camera-ready and node contract alignment
PRD text: **Required Behavior:** As described in this section; must align with camera-ready goals and existing node contracts.

### Q1: Implementation
docs/standards.md::(contract and test mapping)
tests/integration/test_contract_state_pollution.py::TestContractSpecCompliance.test_contracts_enforce_workflow_history_reading
tests/quality/test_standards.py::(quality gates)

### Q2: DRY
DUPLICATED
If duplicated: contract alignment checks are split between `tests/integration/test_contract_state_pollution.py` and `tests/quality/test_standards.py`.

### Q3: Test pyramid
  Unit (mocked deps):    tests/integration/test_contract_state_pollution.py::TestContractSpecCompliance.test_architect_contract_specifies_no_pollution
  Integration (real):    tests/integration/test_contract_state_pollution.py::TestContractSpecCompliance.test_contracts_enforce_workflow_history_reading
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Contract checks exist, but camera-ready quantitative alignment is not comprehensively machine-enforced.
---
## [UNNUMBERED-032] — MCP shared indices/isolation/inheritance
PRD text: **Required Behavior:** MCP workflows must support shared indices, isolation, and inheritance.

### Q1: Implementation
src/mcp_tools.py::mcp_query_knowledge
src/services/workflow_store.py::WorkflowStore
src/session_manager.py::merge_session_context
src/session_manager.py::persist_session_result

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_workflow_store.py::test_workflow_store_roundtrip
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_list_tools_and_validate_inputs
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Isolation is implemented, but explicit parent-child inheritance semantics are minimal and not benchmarked.
---
## [UNNUMBERED-033] — No concurrent state collisions
PRD text: - ✅ No workflow state collisions for concurrent users.

### Q1: Implementation
src/services/workflow_store.py::WorkflowStore._connect
src/services/workflow_store.py::WorkflowStore.upsert_session
src/mcp_tools.py::mcp_list_sweeps

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_workflow_store.py::test_concurrent_sweep_writes_do_not_corrupt
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: WAL and session keying are present, but no stress test demonstrates 3-5+ concurrent live writers under load.
---
## [UNNUMBERED-034] — Inheritance cost reduction target
PRD text: - ✅ Inheritance reduces planning cost by ≥60%.

### Q1: Implementation
src/session_manager.py::merge_session_context
src/mcp_tools.py::mcp_execute_workflow

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_execute_workflow_runs_steps_in_order
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
NONE
Risk: No metric or benchmark asserts a measured ≥60% planning cost reduction from inheritance.
---
## Session complete
Criteria audited: 25
Batch: batch_04
Worktree: wt-5
HEAD: $(git rev-parse HEAD)
