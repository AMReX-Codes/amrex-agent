# Audit batch_13
HEAD: 0e88de1ba97d93067b080783a7a74f9f5b9758d8

## UNNUMBERED-239 — Aggregation Errors by Tier and Node
PRD text: - ✅ Aggregation scripts report errors by tier and node.

### Q1: Implementation
src/benchmark_runner.py::_derive_validation_fields
src/benchmark_runner.py::_write_jsonl

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_contains_schema_valid_field
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Aggregation reports validation categories (schema/physics/resource), but not a full node-by-tier matrix.
---
## UNNUMBERED-240 — Structured Retry Guidance + Bounded Retries
PRD text: **Required Behavior:** Provide structured retry guidance and bounded retries.

### Q1: Implementation
src/nodes/reviewer_node.py::reviewer_node
src/nodes/analysis_node.py::analysis_node
src/router_func.py::route_after_reviewer

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_retry_guidance.py::test_retry_guidance_switch_inputs_on_persistent_unknowns
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::TestFullGraphExecution::test_graph_handles_recursion_limit
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Guidance structure is implemented, but evidence-link requirements are not consistently included.
---
## UNNUMBERED-241 — Retry Guidance Fields (Type/Action/Evidence)
PRD text: - ✅ Retry guidance includes error type, recommended action, and evidence links.

### Q1: Implementation
src/nodes/reviewer_node.py::reviewer_node
src/nodes/analysis_node.py::analysis_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_retry_guidance.py::test_analysis_retry_guidance_from_issues
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Recommended actions exist, but explicit error taxonomy and evidence links are not first-class fields.
---
## UNNUMBERED-242 — Retries Stop at max_retries + Final Failure Recorded
PRD text: - ✅ Retries stop at `max_retries` with final failure state recorded.

### Q1: Implementation
src/nodes/reviewer_node.py::reviewer_node
src/services/reviewer.py::ReviewerOrchestrator.validate_plan
src/router_func.py::route_after_reviewer

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_reviewer_orchestrator.py::TestReviewerOrchestrator::test_max_retries_termination
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::TestFullGraphExecution::test_graph_handles_recursion_limit
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Dual retry counters (`retry_count`, `iteration`) can drift if node contracts are bypassed.
---
## UNNUMBERED-243 — Correction Cycles Logged for Convergence
PRD text: - ✅ Correction cycles are logged for convergence analysis.

### Q1: Implementation
src/nodes/reviewer_node.py::reviewer_node
src/models/graph_state_canonical.py::GraphState
src/main.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_retry_guidance.py::test_retry_guidance_switch_inputs_on_persistent_unknowns
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::TestFullGraphExecution::test_happy_path_full_workflow
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_pelec

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Convergence data is logged in workflow fields, but no dedicated convergence-analysis report artifact is produced.
---
## UNNUMBERED-244 — Session Lifecycle + Tool Handler Responsibilities
PRD text: **Required Behavior:** Define session lifecycle and tool handler responsibilities.

### Q1: Implementation
src/services/workflow_store.py::WorkflowStore.upsert_session
src/session_manager.py::merge_session_context
src/tool_registry.py::dispatch_tool
src/interactive_service.py::invoke_tool

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_interactive_service.py::test_invoke_tool_blocks_critical_without_approval
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
Session persistence + merge | YES | YES
Tool dispatch responsibilities | YES | YES
Explicit lifecycle state machine | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: Responsibilities are implemented across modules, but a formal lifecycle-state contract is not centralized.
---
## UNNUMBERED-245 — Session Lifecycle States (creation/active/completed/archived)
PRD text: - ✅ Session lifecycle includes creation, active, completed, and archived states.

### Q1: Implementation
src/services/workflow_store.py::WorkflowStore.upsert_session
src/services/workflow_store.py::WorkflowStore.get_session

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_workflow_store.py::test_workflow_store_roundtrip
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Creation/update timestamps exist, but explicit active/completed/archived lifecycle state transitions are not implemented.
---
## UNNUMBERED-246 — Tool Handlers Validate Input + Structured Output
PRD text: - ✅ Tool handlers validate inputs and emit structured outputs.

### Q1: Implementation
src/mcp_tools.py::mcp_validate_inputs
src/mcp_tools.py::mcp_validate_config
src/mcp_tools.py::get_tool_specs
src/mcp_tools.py::mcp_execute_workflow

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_validate_inputs_requires_path
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_list_tools_and_validate_inputs
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Input schema definitions are rich, but runtime schema coercion/rejection relies partly on handler-level manual checks.
---
## UNNUMBERED-247 — Session Isolation Enforced
PRD text: - ✅ Session isolation is enforced.

### Q1: Implementation
src/session_manager.py::merge_session_context
src/session_manager.py::persist_session_result
src/mcp_tools.py::mcp_list_sweeps
src/services/workflow_store.py::WorkflowStore.get_session

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
Risk: Isolation is keyed by `session_id`, but no hard tenancy boundary exists beyond identifier scoping.
---
## UNNUMBERED-248 — Versioned Migrations + Backup/Restore Steps
PRD text: **Required Behavior:** Provide versioned schema migrations and backup/restore steps.

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
HIGH
Risk: No formal migration/backup runbook for workflow store schema upgrades is implemented in code/docs.
---
## UNNUMBERED-249 — Versioned Schema Changes + Migration Notes
PRD text: - ✅ Schema changes are versioned with migration notes.

### Q1: Implementation
database/scripts/build_schema.py::SchemaBuilder.save
src/services/schema_staleness.py::check_schema_staleness

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_db_mismatch_policy.py::TestSchemaStalenessCheck::test_schema_without_repo_commits_ok
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Schema version metadata exists, but explicit migration notes/process artifacts are not maintained in-repo.
---
## UNNUMBERED-250 — Backup/Restore Procedure Documented
PRD text: - ✅ Backup/restore procedure documented.

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
HIGH
Risk: Absence of backup/restore documentation increases operational risk for state-store failures.
---
## UNNUMBERED-251 — Workflow State Queryable for Audits
PRD text: - ✅ Workflow state is queryable for audits.

### Q1: Implementation
src/services/workflow_store.py::WorkflowStore.get_session
src/mcp_tools.py::mcp_get_sweep_status
src/mcp_tools.py::mcp_list_sweeps

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
HIGH
Risk: Queryability is present, but audit query APIs are narrow (session/sweep focused).
---
## UNNUMBERED-252 — Concurrency Limits + WAL + Deployment Validation
PRD text: **Required Behavior:** Define concurrency limits, WAL settings, and deployment validation steps.

### Q1: Implementation
src/services/workflow_store.py::WorkflowStore._connect
docs/deployment_readiness.md::Deployment Plan

### Q2: DRY
DUPLICATED
If duplicated: docs/PRD/PRD_v2605.md, docs/deployment_readiness.md.

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_workflow_store.py::test_concurrent_sweep_writes_do_not_corrupt
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: WAL is implemented, but explicit tested concurrency-limit enforcement and deployment validation automation are missing.
---
## UNNUMBERED-253 — WAL Enabled + Verified at Startup
PRD text: - ✅ WAL mode enabled and verified at startup.

### Q1: Implementation
src/services/workflow_store.py::WorkflowStore._connect
src/services/workflow_store.py::WorkflowStore._init_db

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_workflow_store.py::test_workflow_store_roundtrip
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: WAL is set programmatically, but there is no explicit startup assertion test for journal mode.
---
## UNNUMBERED-254 — Concurrency Limits Documented for 3-5 Users
PRD text: - ✅ Concurrency limits documented for 3-5 users.

### Q1: Implementation
docs/PRD/PRD_v2605.md::(deployment/concurrency section)

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
LOW
Risk: Documentation claim exists in PRD narrative, but no executable concurrency limit control is implemented.
---
## UNNUMBERED-255 — Deployment Config Env Var Validation
PRD text: - ✅ Deployment config includes environment variable validation.

### Q1: Implementation
src/config.py::load_config
src/config.py::get_llm_client
src/services/run_superfacility_tools.py::find_nersc_clients

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_config.py::TestConfigValidation::test_missing_api_key_raises_error
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): tests/e2e/test_readme_command_runner.py::test_readme_command_runner_execute_full_file_manual

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Validation exists for key provider paths, but environment completeness checks are not centralized into one deployment validator.
---
## UNNUMBERED-256 — Standardized Multi-Simulation Communication
PRD text: Standardized communication is required for multi-simulation workflows such as parameter sweeps or UQ ensembles, where a 

### Q1: Implementation
src/models/sweep_schemas.py::SweepSpec
src/services/sweep_orchestrator.py::orchestrate_sweep
src/mcp_tools.py::mcp_get_sweep_status

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_sweep_orchestrator.py::test_sweep_spec_validates_against_schema
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Sweep communication is structured, but explicit A2A protocol contracts are not implemented.
---
## UNNUMBERED-257 — A2A Schema Validation + Versioning
PRD text: **Required Behavior:** Enforce schema validation and versioning for A2A messages.

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
HIGH
Risk: No A2A message envelope schema/version enforcement is present in source.
---
## UNNUMBERED-258 — A2A protocol_version + trace_id Required
PRD text: - ✅ All A2A messages include `protocol_version` and `trace_id`.

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
HIGH
Risk: Missing protocol/trace envelope fields blocks reliable cross-agent tracing.
---
## UNNUMBERED-259 — Schema Validation Before Dispatch
PRD text: - ✅ Schema validation runs before dispatch.

### Q1: Implementation
src/tool_registry.py::dispatch_tool
src/mcp_tools.py::get_tool_specs

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_list_tools_inprocess
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_list_tools_and_validate_inputs
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Tool schemas are declared, but explicit server-side schema validation before handler dispatch is not evident in local dispatch code.
---
## UNNUMBERED-260 — Invalid Messages Rejected with Clear Errors
PRD text: - ✅ Invalid messages are rejected with clear errors.

### Q1: Implementation
src/mcp_tools.py::mcp_validate_inputs
src/mcp_tools.py::mcp_validate_config
mcp_server.py::call_tool

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_validate_inputs_requires_path
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_list_tools_and_validate_inputs
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Error payloads are clear but not normalized under a single cross-tool error schema.
---
## UNNUMBERED-261 — Inheritance Contracts + Backoff Policies + Metrics
PRD text: **Required Behavior:** Enforce inheritance contracts and backoff policies with metrics.

### Q1: Implementation
src/models/sweep_schemas.py::validate_transition
src/config.py::_LLMRetryCompletions.create
src/utils/metrics.py::MetricsCollector.record_llm_usage

### Q2: DRY
DUPLICATED
If duplicated: src/config.py, src/services/embedding.py (separate backoff implementations).

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_sweep_orchestrator.py::test_sweep_spec_validates_against_schema
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Backoff+metrics exist for LLM calls, but policy linkage to polling/inheritance contracts is incomplete.
---
## UNNUMBERED-263 — Polling Exponential Backoff + Max Cap
PRD text: - ✅ Polling uses exponential backoff with max cap.

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
HIGH
Risk: Polling uses fixed interval sleeps, increasing rate-limit and latency inefficiency risk.
---
## UNNUMBERED-264 — Polling Outcomes + Latencies Logged
PRD text: - ✅ Polling outcomes and latencies are logged.

### Q1: Implementation
src/services/run_superfacility_tools.py::monitor_job (outcome polling only)

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
LOW
Risk: Final outcomes are returned, but explicit per-poll latency metrics logging is not implemented.
---
## Session complete
Criteria audited: 25
Batch: batch_13
Worktree: wt-4
HEAD: 0e88de1ba97d93067b080783a7a74f9f5b9758d8
