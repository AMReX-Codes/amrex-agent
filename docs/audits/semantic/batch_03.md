# Audit batch_03
HEAD: e2603fa968244ca07b2aa8710074f97a0ed06833

## [UNNUMBERED-001] — Max LOC per new file
PRD text: - Max LOC per new file: `<=100` (PRD2 standard, decomposition required above this threshold).

### Q1: Implementation
src/services/sweep_orchestrator.py::_create_children
src/services/sweep_orchestrator.py::_run_architect_phase
src/services/sweep_orchestrator.py::_run_reviewer_phase

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_rule_engine_orchestrator.py::TestRuleEngineValidate.test_validate_runs_all_solver_rules
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: No automated guard enforces a strict <=100 LOC threshold for every new file.
---
## [UNNUMBERED-001] — Orchestration complexity <=10
PRD text: - no orchestration function >10 complexity.

### Q1: Implementation
src/services/sweep_orchestrator.py::orchestrate_sweep
src/main.py::create_amrex_agent_graph
src/main.py::run_agent

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_graph_execution.py::TestGraphExecutionEngine.test_recursion_limit_set_to_50
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: `radon` is unavailable, so complexity threshold is not directly measured.
---
## [UNNUMBERED-001] — Benchmark builder complexity
PRD text: - no benchmark record builder function exceeds complexity threshold.

### Q1: Implementation
src/benchmark_runner.py::_derive_benchmark_metrics_fields
src/benchmark_runner.py::_normalize_benchmark_record
src/benchmark_runner.py::_write_jsonl

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_contains_schema_valid_field
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Complexity threshold is asserted indirectly via tests but not measured with `radon` here.
---
## [UNNUMBERED-001] — Global function complexity
PRD text: - no function exceeds complexity threshold.

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
Risk: No repo-level complexity gate was found and `radon` is unavailable in this environment.
---
## [UNNUMBERED-002] — Radon complexity evidence
PRD text: - `radon cc` shows no new function >10.

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
Risk: `radon` binary is missing (`command -v radon` returned no path).
---
## [UNNUMBERED-002] — New file size discipline
PRD text: - no new file >100 LOC without helper extraction.

### Q1: Implementation
src/services/sweep_orchestrator.py::_coerce_status
src/services/sweep_orchestrator.py::_advance_status
src/services/sweep_orchestrator.py::update_parent_state

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_rule_engine_orchestrator.py::TestRuleEngineValidate.test_validate_passes_correct_context
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Helper extraction exists in some large modules, but no CI guard enforces this rule globally.
---
## [UNNUMBERED-002] — Backward-compatible output keys
PRD text: - regression tests confirm backward-compatible output keys still present.

### Q1: Implementation
src/benchmark_runner.py::_write_jsonl
src/benchmark_runner.py::_normalize_benchmark_record

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_no_new_required_field_breaks_existing
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Integration coverage for exact key stability across all downstream consumers is limited.
---
## [UNNUMBERED-002] — Parser/validator mode unit tests
PRD text: - each parser/validator mode has dedicated unit tests.

### Q1: Implementation
src/main.py::parse_args
src/services/validators/schema_validator.py::SchemaSyntaxValidator.validate
src/services/validators/config_validator.py::ConfigValidator.validate

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_cli.py::TestCLIEntryPoint.test_run_mode_flag_sets_config
  Integration (real):    tests/integration/test_schema_validator_integration.py::test_schema_validator_flags_type_mismatch_and_syntax
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Parser modes are well-tested, but exhaustive validator mode-by-mode matrix coverage is partial.
---
## [UNNUMBERED-003] — Amendment module decomposition
PRD text: - no new amendment module >100 LOC without documented helper extraction.

### Q1: Implementation
src/models/graph_state_canonical.py::GraphState
src/services/sweep_orchestrator.py::_run_architect_phase
src/services/sweep_orchestrator.py::_run_reviewer_phase

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_graph_state_init.py::test_graph_state_has_b1_b2_defaults
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Comments indicate stateless additive design, but no explicit amendment-size enforcement exists.
---
## [UNNUMBERED-003] — Per-phase unit and fan-out/fan-in integration
PRD text: - unit tests per phase + integration test for fan-out/fan-in.

### Q1: Implementation
src/main.py::create_amrex_agent_graph
src/services/sweep_orchestrator.py::orchestrate_sweep

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_graph_wiring.py::TestGraphConditionalWiring.test_analysis_has_conditional_edges
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
planning/execution/analysis | src/main.py graph wiring | tests/unit/test_graph_wiring.py
fan-out/fan-in sweep | src/services/sweep_orchestrator.py | tests/integration/test_sweep_orchestration.py

### Q6: Confidence
HIGH
Risk: E2E fan-out coverage is lightweight versus production-scale sweeps.
---
## [UNNUMBERED-004] — Unit+integration for node/service paths
PRD text: - unit + integration tests for each new node/service path.

### Q1: Implementation
src/nodes/architect_node.py::architect_node
src/nodes/reviewer_node.py::reviewer_node
src/nodes/runner_node.py::runner_node
src/services/sweep_orchestrator.py::orchestrate_sweep

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_node.py::test_success_maps_plan_and_baseline
  Integration (real):    tests/integration/test_input_writer_pipeline.py::TestInputWriterPipelineIntegration.test_full_pipeline_load_modify_write_pelec
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
planning | architect/reviewer nodes | unit + integration present
execution | input_writer/runner nodes | unit + integration present
analysis | analysis/visualization nodes | unit + integration present

### Q6: Confidence
MEDIUM
Risk: “each new path” cannot be fully proven without change-scoped metadata.
---
## [UNNUMBERED-005] — Stateless deployment
PRD text: - Stateless deployment: no migration required.

### Q1: Implementation
src/models/graph_state_canonical.py::GraphState
src/models/graph_state_canonical.py::GRAPH_STATE_B1_B2_DEFAULTS
src/services/workflow_store.py::WorkflowStore.upsert_session

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_graph_state_init.py::test_b1_b2_defaults_are_additive
  Integration (real):    tests/integration/test_infrastructure.py::TestIntegrationInfrastructure.test_l1_state_has_required_fields
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: SQLite store schema is stable but still a persisted state surface requiring upgrade caution.
---
## [F4.3] — Orchestration options assessment section
PRD text: Section requirement: **20.4 Orchestration Options Assessment (LangGraph vs Academy vs Alternatives)** *(Feature ID: F4.3

### Q1: Implementation
docs/PRD/PRD_v2605.md::20.4 section

### Q2: DRY
DRY

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
Risk: Requirement appears in PRD text, but no dedicated implementation artifact was found in docs outside PRD.
---
## [F5.1] — Mapping reference
PRD text: * **Mapping:** F5.1, F5.2.

### Q1: Implementation
docs/PRD/PRD_v2605.md::F5.1 mapping rows

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
Risk: Mapping statement is present in PRD, but no executable acceptance check was identified.
---
## [F5.2] — Mapping reference
PRD text: * **Mapping:** F5.2.

### Q1: Implementation
docs/PRD/PRD_v2605.md::F5.2 mapping rows

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
Risk: Mapping statement is documentation-only with no direct code-level verifier.
---
## [F5.3] — Extensibility and interoperability section
PRD text: Section requirement: **20.5 Extensibility & Interoperability Paths** *(Feature ID: F5.3)*

### Q1: Implementation
docs/PRD/PRD_v2605.md::20.5 section
docs/mcp.md::MCP interoperability surface
src/mcp_tools.py::mcp_execute_workflow

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_execute_workflow_runs_steps_in_order
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Interoperability exists for MCP; broader alternatives matrix is not executable.
---
## [F5.3] — Interface via new nodes or MCP/A2A workflows
PRD text: The system must interface with other codes and external agents by **adding LangGraph nodes** or **invoking MCP/A2A workf

### Q1: Implementation
src/graph.py::create_graph
src/mcp_tools.py::mcp_execute_workflow
src/tool_registry.py::ToolRegistry

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_graph_wiring.py::TestIntentClarificationWiring.test_intent_extraction_node_in_graph
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: A2A-specific workflow coverage appears limited relative to MCP path coverage.
---
## [F5.3] — New code integration <=300 LOC + solver config
PRD text: - ✅ New code integration requires \<300 LOC and a solver config entry.

### Q1: Implementation
database/configs/__init__.py::discover_code_configs
src/services/config_model_factory.py::ConfigModelFactory.resolve_schema_path

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_config_factory_edge_cases.py::test_create_from_schema_skips_cpp_expression_default
  Integration (real):    tests/integration/test_config_model_factory_integration.py::test_hydrate_skips_cpp_expression_value
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Solver config extension is implemented, but explicit LOC<=300 compliance is not automatically enforced.
---
## [F5.3] — External calls schema-validated + logged history
PRD text: - ✅ External tool calls are schema-validated and logged in `workflow_history`.

### Q1: Implementation
src/mcp_tools.py::get_tool_specs
tests/quality/test_mcp_contract_schemas.py::test_mcp_contract_examples_match_schema
src/utils/state_management.py::append_to_history
src/main.py::main (workflow_history serialization)

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_mcp_execute_workflow_defaults_steps
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Schema validation is explicit for contracts, but per-call workflow_history linkage is not uniformly asserted for every tool.
---
## [F5.3] — A2A retries + error propagation
PRD text: - ✅ A2A integration supports retries and error propagation into the main workflow.

### Q1: Implementation
src/services/sweep_orchestrator.py::_advance_status
src/services/sweep_orchestrator.py::_poll_until_complete
src/services/sweep_orchestrator.py::update_parent_state

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_retry_guidance.py::test_retry_guidance_switch_baseline_on_schema_missing
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_sweep_orchestration_end_to_end
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
submit/poll/retry | src/services/sweep_orchestrator.py | tests/integration/test_sweep_orchestration.py

### Q6: Confidence
MEDIUM
Risk: Retry/error propagation is implemented for sweep orchestration, but explicit A2A protocol harness coverage is limited.
---
## [F5.3] — Schema-driven, observable, reproducible integrations
PRD text: **Required Behavior:** New nodes and A2A integrations must be schema-driven, observable, and reproducible.

### Q1: Implementation
tests/quality/test_mcp_contract_schemas.py::test_mcp_contract_examples_match_schema
src/models/graph_state_canonical.py::GraphState
src/services/workflow_store.py::WorkflowStore

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_workflow_store.py::test_workflow_store_roundtrip
  Integration (real):    tests/integration/test_contract_state_pollution.py::TestDownstreamNodeDataAccess.test_reviewer_reads_from_architect_details
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Observability and schema checks are strong; reproducibility guarantees are partial outside benchmark harness.
---
## [F6.1] — Documentation mapping
PRD text: * **Mapping:** F6.1.

### Q1: Implementation
docs/PRD/PRD_v2605.md::F6.1 mapping rows

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
Risk: Mapping-only statement has no direct executable validation artifact.
---
## [F6.2] — Standards and capability alignment section
PRD text: Section requirement: **17.1 Standards & Capability Alignment** *(Feature ID: F6.2)*

### Q1: Implementation
docs/standards.md::Standards checklist and evidence mapping
docs/PRD/PRD_v2605.md::17.1 Standards & Capability Alignment

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_component5f_standards.py::test_metadata_keys_standard
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Standards coverage table is documented, but some rows point to aspirational follow-up tasks.
---
## [F6.2] — Capability reporting breadth
PRD text: - Planning, retrieval, validation, execution, analysis, visualization, and collaboration capabilities must be reported w

### Q1: Implementation
docs/standards.md::Capability coverage (Agents4Science-aligned)

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_component5f_standards.py::test_metadata_dict_structure
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
planning/retrieval/validation/execution/analysis/visualization/collaboration | docs/standards.md capability table | tests/unit/test_component5f_standards.py

### Q6: Confidence
MEDIUM
Risk: Capability reporting exists in docs; runtime telemetry-level proof is incomplete.
---
## [F6.2] — Required behavior traceability
PRD text: **Required Behavior:** Document standards compliance and Agents4Science coverage with explicit traceability to features/

### Q1: Implementation
docs/standards.md::Standards to feature/test mapping
docs/coverage_map.md::feature/test anchors

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_component5f_standards.py::test_function_parameters_consistent
  Integration (real):    tests/integration/test_contract_state_pollution.py::TestDownstreamNodeDataAccess.test_reviewer_reads_from_architect_details
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Traceability is documentation-centric and can drift without periodic automated checks.
---
## [F6.2] — Standards checklist mapped to evidence
PRD text: - ✅ Standards checklist mapped to features and evidence artifacts.

### Q1: Implementation
docs/standards.md::Standards checklist and evidence mapping

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_component5f_standards.py::test_metadata_portability
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Mapping quality depends on manual maintenance of evidence links.
---
## [F6.2] — Agents4Science capability table
PRD text: - ✅ Agents4Science capability table with coverage status and references.

### Q1: Implementation
docs/standards.md::Agents4Science capability stages (reference)

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_component5f_standards.py::test_deprecated_keys_aliased
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: External taxonomy updates could age the table without automated sync.
---
## [F6.2] — Gap flagging with plan/risk notes
PRD text: - ✅ Gaps flagged with planned work or risk notes.

### Q1: Implementation
docs/standards.md::Gaps and risk notes
docs/standards.md::Structured gap log

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_component5f_standards.py::test_no_internal_vars_in_metadata
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Gap status can become stale if not tied to release gates.
---
## [UNNUMBERED-001] — Instrumentation scope creep risk
PRD text: 1. **Instrumentation Scope Creep:** Current coverage 10-30%, target 100% by Week 2 → must prioritize minimal invasive ch

### Q1: Implementation
src/utils/metrics.py::metrics_extra
src/main.py::main (metrics context usage)

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_metrics_collector.py::test_metrics_collector_aggregates_llm_tokens
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Metric hooks exist but complete table-level coverage is not yet demonstrably 100%.
---
## [UNNUMBERED-002] — Claim/evidence/gap table structure
PRD text: | Claim | Required Evidence | Current Coverage | Gap |

### Q1: Implementation
docs/standards.md::Structured gap log
docs/coverage_map.md::evidence mapping

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_component5f_standards.py::test_metadata_dict_structure
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Table exists but not all claims have machine-checked evidence completeness.
---
## [UNNUMBERED-003] — Required capability (v26.05)
PRD text: ✅ **Required Capability (v26.05):**

### Q1: Implementation
docs/PRD/PRD_v2605.md::required capability sections
docs/standards.md::capability coverage

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_component5f_standards.py::test_metadata_portability
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Criterion text is broad and truncated, so implementation mapping is partially inferential.
---
## [UNNUMBERED-004] — Provider dependency risk
PRD text: - Provider dependency risk (Anthropic API required)

### Q1: Implementation
src/config.py::AMReXAgentConfig
src/utils/llm_calls.py::call_llm_json

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_llm_fallback.py::test_llm_fallback_structured_returns_none_on_error
  Integration (real):    tests/integration/test_infrastructure.py::TestIntegrationInfrastructure.test_integration_level_detection
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Multi-provider fallback exists, but operational dependency risk still depends on runtime credentials.
---
## [UNNUMBERED-005] — Required evidence (v26.05)
PRD text: **Required Evidence (v26.05):**

### Q1: Implementation
docs/PRD/PRD_v2605.md::evidence sections
docs/coverage_map.md::artifact mapping

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_component5f_standards.py::test_metadata_keys_standard
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Broad requirement with truncated context limits precise verifiability.
---
## [UNNUMBERED-006] — Validation overhead risk
PRD text: - **Validation Overhead:** Must manually verify agent outputs before allowing HPC access

### Q1: Implementation
src/utils/gate.py::run_preconfirm_gate
src/models/gate_approval.py::GateApprovalRecord
src/main.py::main (gate approvals persisted)

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_gate_approvals_state.py::test_gate_approval_record_validates_correctly
  Integration (real):    tests/integration/test_infrastructure.py::TestIntegrationInfrastructure.test_l1_state_has_required_fields
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Manual verification path exists but policy automation for HPC admission appears partial.
---
## [UNNUMBERED-007] — Camera-ready metric objective
PRD text: **Objective:** Capture a complete set of metrics required for camera-ready paper Tables 1-5

### Q1: Implementation
src/benchmark_runner.py::run_model_benchmark
src/benchmark_runner.py::_derive_benchmark_metrics_fields
scripts/aggregate_metrics.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Metric capture is broad but “complete for Tables 1-5” is not explicitly asserted by a single acceptance test.
---
## [UNNUMBERED-008] — Rationale for arXiv-grade evidence
PRD text: **Rationale:** Workshop paper describes system capabilities; arXiv paper must prove them with ablations and comparisons.

### Q1: Implementation
scripts/compare_models.py::main
scripts/run_benchmark.py::main
src/benchmark_runner.py::run_model_benchmark

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_wall_time_seconds_present
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Benchmark plumbing exists, but explicit ablation-comparison acceptance checks are limited.
---
## [UNNUMBERED-009] — Gate 2 actuals
PRD text: - Actual: (must match for Gate 2 pass)

### Q1: Implementation
src/policy/gate_policy.py::evaluate_gate_policy
src/utils/gate.py::run_preconfirm_gate

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_gate_approvals_state.py::test_gate_approval_record_validates_correctly
  Integration (real):    tests/integration/test_infrastructure.py::TestIntegrationInfrastructure.test_l1_state_has_required_fields
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Gate wording is truncated, so exact “actuals must match” target is not fully verifiable from this criterion line alone.
---
## Session complete
Criteria audited: 37
Batch: batch_03
Worktree: wt-4
HEAD: e2603fa968244ca07b2aa8710074f97a0ed06833
