# Audit batch_09
HEAD: d6fbb576a490fec69ff33d462d5e8822224dfc88

## [UNNUMBERED-137] — Deterministic bounded retry routing
PRD text: **Required Behavior:** Retry routing must be deterministic and bounded, with structured retry guidance.

### Q1: Implementation
src/nodes/architect_node.py::architect_node
src/nodes/reviewer_node.py::reviewer_node
src/nodes/reviewer_node.py::_derive_retry_guidance

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_retry_guidance.py::test_retry_guidance_switch_inputs_on_persistent_unknowns
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::TestErrorRecovery.test_reviewer_rejection_triggers_retry
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
DRIFTED
If drifted: several retry tests/configs still rely on `max_iterations` while canonical state uses `max_retries`.

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Deterministic routing exists, but mixed `max_iterations`/`max_retries` naming can cause confusion.
---
## [UNNUMBERED-138] — Retry count and max_retries stop
PRD text: - ✅ Retry count increments and stops at max_retries.

### Q1: Implementation
src/nodes/architect_node.py::architect_node
src/nodes/reviewer_node.py::reviewer_node
src/services/reviewer.py::ReviewerOrchestrator.validate_plan

### Q2: DRY
DUPLICATED
If duplicated: src/nodes/architect_node.py, src/nodes/reviewer_node.py, src/services/reviewer.py.

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_reviewer_orchestrator.py::TestReviewerOrchestrator.test_max_retries_termination
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::TestErrorRecovery.test_max_retries_enforced
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
DRIFTED
If drifted: `mock_config.max_iterations` is used in unit/integration tests instead of canonical `max_retries`.

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Enforcement exists but is split across layers with inconsistent retry field naming.
---
## [UNNUMBERED-139] — Retry guidance passed and logged
PRD text: - ✅ Retry guidance is passed into Architect and logged in workflow history.

### Q1: Implementation
src/nodes/reviewer_node.py::reviewer_node
src/nodes/architect_node.py::architect_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_retry_guidance.py::test_retry_guidance_switch_inputs_on_persistent_unknowns
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::TestErrorRecovery.test_error_history_tracking
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Guidance is logged, but downstream consumption quality depends on prior node detail completeness.
---
## [UNNUMBERED-140] — Final taxonomy after max retries
PRD text: - ✅ Failures after max retries are recorded with final error taxonomy.

### Q1: Implementation
src/nodes/reviewer_node.py::reviewer_node
src/services/validation_result.py::ValidationResult

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_reviewer_orchestrator.py::TestReviewerOrchestrator.test_max_retries_termination
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::TestErrorRecovery.test_max_retries_enforced
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: terminal failure is recorded, but a formal final error taxonomy field is not explicitly standardized.
---
## [UNNUMBERED-141] — Release of Measurement instrumentation
PRD text: v26.05 is the "Release of Measurement." Every agentic interaction must be instrumented to transform the prototype into a

### Q1: Implementation
src/utils/metrics.py::MetricsCollector.record_event
src/utils/metrics.py::MetricsCollector.build_workflow_summary
src/main.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_metrics_collector.py::test_metrics_collector_aggregates_llm_tokens
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_benchmark_harness_generates_metrics_bundle
  Oracle/E2E (pipeline): tests/e2e/test_readme_command_runner.py::test_readme_commands_registry_entries_execute

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Instrumentation exists, but "every interaction" coverage is not exhaustively enforced by tests.
---
## [UNNUMBERED-142] — Token and cost tracking
PRD text: * **10.1 Token & Cost Tracking:** All 17 LLM call sites must track token counts. The `pricing.yaml` module will map thes

### Q1: Implementation
src/utils/metrics.py::MetricsCollector.record_llm_usage
src/utils/metrics.py::_aggregate_llm_usage
scripts/aggregate_metrics.py::_summarize_items

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_metrics_collector.py::test_metrics_collector_aggregates_llm_tokens
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: token tracking exists, but no `pricing.yaml`/USD mapping implementation was found.
---
## [UNNUMBERED-143] — JSONL metrics persistence
PRD text: * **10.2 JSONL Metrics Persistence:** Every execution must append to `metrics.jsonl`. Fields must include `workflow_id`,

### Q1: Implementation
src/main.py::main
src/utils/metrics.py::MetricsCollector.write_jsonl
src/benchmark_runner.py::_write_jsonl

### Q2: DRY
DUPLICATED
If duplicated: src/utils/metrics.py and src/benchmark_runner.py.

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_iteration_count_present
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_benchmark_harness_generates_metrics_bundle
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
DRIFTED
If drifted: benchmark/integration fixtures still use legacy retry field names (`max_iterations`).

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: metrics are persisted, but `workflow_id` is not guaranteed and `write_jsonl` rewrites files instead of append semantics.
---
## [UNNUMBERED-144] — Automated paper table generation
PRD text: * **10.3 Automated Table Generation:** The `generate_paper_tables.py` script will synthesize these metrics into LaTeX ta

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
Risk: `scripts/generate_paper_tables.py` is referenced in PRD/docs but does not exist in this repository snapshot.
---
## [UNNUMBERED-145] — Multi-user access with shared indices and auditable state
PRD text: **Required Behavior:** Multi-user tool access with shared indices and auditable workflow state.

### Q1: Implementation
mcp_server.py::call_tool
src/interactive_service.py::invoke_tool
src/mcp_tools.py::mcp_query_knowledge
src/services/workflow_store.py::WorkflowStore

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_workflow_store.py::test_workflow_store_roundtrip
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: shared index usage and auditable state exist, but high-concurrency guarantees are only lightly tested.
---
## [UNNUMBERED-146] — 3-5 concurrent users no collisions
PRD text: - ✅ 3-5 concurrent users without state collisions.

### Q1: Implementation
src/services/workflow_store.py::WorkflowStore._connect
src/services/workflow_store.py::WorkflowStore.upsert_session

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
LOW
Risk: WAL mode and key isolation are present, but no explicit 3-5 concurrent user load test was found.
---
## [UNNUMBERED-147] — Tool schema validation consistency
PRD text: - ✅ Tool schemas validate inputs and outputs consistently.

### Q1: Implementation
src/mcp_tools.py::get_tool_specs
tests/quality/test_mcp_contract_schemas.py::test_mcp_contract_examples_match_schema

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_validate_config_requires_config
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_list_tools_and_validate_inputs
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: input schema checks exist, but output schema enforcement is not uniformly strict across all MCP tools.
---
## [UNNUMBERED-148] — Shared indices read-only and versioned
PRD text: - ✅ Shared indices are read-only and versioned.

### Q1: Implementation
src/services/faiss_artifacts.py::ensure_faiss_indices
src/services/faiss_artifacts.py::_load_manifest_from_url

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_faiss_artifacts.py::test_ensure_faiss_indices_returns_existing_paths
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: manifest/hash support exists, but explicit read-only enforcement and index version policy are not implemented in code.
---
## [UNNUMBERED-149] — Child workflow spawn and status polling
PRD text: **Required Behavior:** Spawn child workflows with shared baselines and structured status polling.

### Q1: Implementation
src/services/sweep_orchestrator.py::orchestrate_sweep
src/services/sweep_orchestrator.py::_create_children
src/services/sweep_orchestrator.py::_poll_until_complete

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_orchestrator.py::TestFanOut.test_fanout_spawns_correct_child_count
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: structured polling is robust for modeled status transitions, but relies on external poll/submit callback quality.
---
## [UNNUMBERED-150] — Baseline inheritance without replanning
PRD text: - ✅ Child workflows inherit baseline configs without re-planning.

### Q1: Implementation
src/services/sweep_orchestrator.py::_run_architect_phase
src/services/sweep_orchestrator.py::orchestrate_sweep

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_orchestrator.py::TestExecutionSweep.test_execution_sweep_architect_runs_once
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Base plan reuse is implemented; per-child overrides could still require deeper merge semantics in future.
---
## [UNNUMBERED-151] — Parent status and artifact collection
PRD text: - ✅ Parent can query status and collect analysis artifacts.

### Q1: Implementation
src/mcp_tools.py::mcp_get_sweep_status
src/mcp_tools.py::mcp_get_sweep_results
src/mcp_tools.py::mcp_list_sweeps
src/services/result_aggregator.py::aggregate_results

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_get_sweep_results_returns_summary_when_complete
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: parent-side querying works after filesystem persistence; malformed metadata files remain a failure mode.
---
## [UNNUMBERED-152] — A2A error propagation with retry guidance
PRD text: - ✅ A2A errors propagate into main workflow with retry guidance.

### Q1: Implementation
src/services/sweep_orchestrator.py::update_parent_state
src/services/sweep_orchestrator.py::_extract_failure_reason
src/nodes/reviewer_node.py::_derive_retry_guidance

### Q2: DRY
DUPLICATED
If duplicated: error/retry logic split between `src/services/sweep_orchestrator.py` and `src/nodes/reviewer_node.py`.

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_orchestrator.py::TestPolling.test_polling_failed_updates_count
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: child failure reasons propagate in sweep state, but integration into main-workflow retry guidance is not fully wired.
---
## [UNNUMBERED-153] — Performance and concurrency targets
PRD text: * **13\. Performance:** FAISS retrieval latency \<500ms; E2E plan generation \<3min (excluding simulation). MCP server m

### Q1: Implementation
tests/unit/test_level0_index.py::TestLevel0PerformanceRequirements.test_level0_query_latency
tests/unit/test_level2_index.py::TestLevel2RetrievalSpeed.test_level2_retrieval_speed
src/services/workflow_store.py::WorkflowStore

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level0_index.py::TestLevel0PerformanceRequirements.test_level0_query_latency
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: performance tests exist but thresholds differ from PRD (and no E2E plan-generation timing or MCP concurrency benchmark).
---
## [UNNUMBERED-154] — CLI reflexion guidance usability
PRD text: * **17\. Usability:** CLI ergonomics must provide reflexion guidance (e.g., "Set `pelec.do_react=1` for combustion"). Al

### Q1: Implementation
src/nodes/reviewer_node.py::_derive_retry_guidance
src/nodes/reviewer_node.py::reviewer_node
src/services/feedback_generator.py::FeedbackGenerator.generate

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_retry_guidance.py::test_retry_guidance_switch_inputs_on_persistent_unknowns
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::TestErrorRecovery.test_reviewer_rejection_triggers_retry
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: retry/reflexion guidance exists, but solver-specific ergonomic hint quality is not uniformly validated.
---
## [UNNUMBERED-155] — p95 latency/concurrency/per-node recording requirements
PRD text: **Required Behavior:** Define p95 latency targets for retrieval and planning; enforce concurrency limits and record per-

### Q1: Implementation
src/utils/metrics.py::MetricsCollector.record_event
src/utils/metrics.py::metrics_context
src/services/workflow_store.py::WorkflowStore

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_metrics_collector.py::test_metrics_collector_aggregates_llm_tokens
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: stage-level instrumentation exists, but explicit p95 target enforcement and concurrency limit policies are not implemented.
---
## [UNNUMBERED-156] — p95 FAISS retrieval <500ms
PRD text: - ✅ p95 FAISS retrieval latency \<500ms for L0/L1/L2 on benchmark hardware.

### Q1: Implementation
tests/unit/test_level0_index.py::TestLevel0PerformanceRequirements.test_level0_query_latency
tests/unit/test_level2_index.py::TestLevel2RetrievalSpeed.test_level2_retrieval_speed

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level0_index.py::TestLevel0PerformanceRequirements.test_level0_query_latency
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: no p95 benchmark exists and current tests assert weaker single-run thresholds (<1s or <2s).
---
## [UNNUMBERED-157] — p95 plan generation <3 minutes
PRD text: - ✅ p95 plan generation \<3 minutes for benchmark prompts (excluding simulation).

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
Risk: no timing harness or p95 enforcement for planning latency was found.
---
## [UNNUMBERED-158] — MCP supports 5 concurrent sessions
PRD text: - ✅ MCP server supports 5 concurrent sessions with no state collisions.

### Q1: Implementation
mcp_server.py::call_tool
src/session_manager.py::merge_session_context
src/services/workflow_store.py::WorkflowStore

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
LOW
Risk: session isolation mechanisms exist, but explicit 5-session concurrent validation was not found.
---
## [UNNUMBERED-159] — Per-node latency in metrics.jsonl with stage tags
PRD text: - ✅ Per-node latency recorded in `metrics.jsonl` with stage tags.

### Q1: Implementation
src/utils/metrics.py::MetricsCollector.record_event
src/utils/metrics.py::metrics_context
src/main.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_metrics_collector.py::test_metrics_collector_aggregates_llm_tokens
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: stage tags are recorded, but explicit per-node latency fields are not persisted in current metrics payloads.
---
## [UNNUMBERED-160] — PostgreSQL migration + index growth proof
PRD text: **Required Behavior:** Provide a documented migration path to PostgreSQL and prove index growth does not degrade retriev

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
Risk: runtime implementation remains SQLite WAL; no PostgreSQL migration runbook or index-growth degradation proof was found.
---
## [UNNUMBERED-161] — Migration plan schema mapping and rollback
PRD text: - ✅ Migration plan with schema mapping and rollback path.

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
Risk: no concrete migration artifact with schema mapping + rollback procedure was found in code/docs outside PRD prose.
---
## Session complete
Criteria audited: 25
Batch: batch_09
Worktree: wt-5
HEAD: $(git rev-parse HEAD)
