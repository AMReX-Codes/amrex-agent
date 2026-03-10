# Audit batch_08
HEAD: 7e5903071fc0a73f464eb0a748157152f30bd9f7

## UNNUMBERED-111 — Tier 1 Blocking + Retrieval Retry
PRD text: - ✅ Tier 1 errors block execution and trigger targeted retrieval retries.

### Q1: Implementation
src/services/reviewer.py::ReviewerOrchestrator.validate_plan
src/nodes/reviewer_node.py::reviewer_node
src/nodes/architect_node.py::architect_node

### Q2: DRY
DUPLICATED
If duplicated: src/services/reviewer.py, src/nodes/reviewer_node.py (separate blocking/retry decision paths).

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_reviewer_orchestrator.py::TestReviewerOrchestrator::test_fail_on_critical_error
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::TestFullGraphExecution::test_graph_handles_recursion_limit
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Critical blocking exists, but explicit Tier-1 classification and targeted retrieval retry are not encoded as first-class policy.
---
## UNNUMBERED-112 — Tier 2 Warning + UQ Recommendation
PRD text: - ✅ Tier 2 issues surface as warnings with UQ recommendations.

### Q1: Implementation
database/scripts/build_schema.py::SchemaBuilder._get_param_priority
tests/unit/test_critical_parameter_coverage.py::TestCriticalParameterCoverage.test_tier2_stability_parameters_present
src/services/architect.py::ArchitectService._get_tier_params

### Q2: DRY
DUPLICATED
If duplicated: database/scripts/build_schema.py, src/services/architect.py, tests/unit/test_critical_parameter_coverage.py.

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_critical_parameter_coverage.py::TestCriticalParameterCoverage.test_tier2_stability_parameters_present
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Tier metadata exists, but there is no explicit runtime Tier-2 warning channel coupled to UQ recommendation output.
---
## UNNUMBERED-113 — Tier 3/4 Non-Blocking Logging
PRD text: - ✅ Tier 3/4 issues logged without blocking.

### Q1: Implementation
database/scripts/build_schema.py::SchemaBuilder._get_param_priority

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
Risk: Tier-3/4 runtime behavior is not implemented beyond static priority tagging in schema generation.
---
## UNNUMBERED-114 — Source Code Truth Authoritative Schema
PRD text: **Required Behavior:** Source code truth must be the authoritative schema for parameter existence and type checks.

### Q1: Implementation
src/services/validators/schema_validator.py::SchemaSyntaxValidator.validate
src/services/validators/schema_validator.py::SchemaSyntaxValidator._validate_type_syntax
src/services/rules/schema_existence.py::SchemaExistenceRule.check

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_schema_validator.py::test_schema_validator_missing_schema_returns_critical
  Integration (real):    tests/integration/test_schema_validator_integration.py::test_schema_validator_flags_type_mismatch_and_syntax
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_pelec

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: If schema files are stale, correctness depends on mismatch-policy handling rather than hard fail by default.
---
## UNNUMBERED-115 — ParmParse Scraping Coverage
PRD text: - ✅ ParmParse scraping covers required solver sources.

### Q1: Implementation
database/scripts/build_schema.py::SchemaBuilder.scan_source_code
database/scripts/build_schema.py::SchemaBuilder._scan_file
database/scripts/build_schema.py::build_schema_auto_compose

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_schema_scraper.py::TestParmParseExtraction.test_parmparse_extraction_basic
  Integration (real):    tests/integration/test_input_writer_pipeline.py::TestInputWriterPipelineIntegration.test_schema_resolution_with_real_pelec
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Coverage quality varies by solver-specific `schema_source_patterns` and may miss edge files without explicit pattern entries.
---
## UNNUMBERED-116 — Unknown Param Rejection + Suggestions
PRD text: - ✅ Unknown parameters are rejected with suggestions.

### Q1: Implementation
src/services/validators/schema_validator.py::SchemaSyntaxValidator.validate
src/services/config_model_factory.py::ConfigModelFactory.build_parameter_resolution_feedback
src/services/config_model_factory.py::ConfigModelFactory._build_suggested_params

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_config_model_modification.py::TestApplyModifications.test_unknown_parameter_permissive
  Integration (real):    tests/integration/test_schema_validator_integration.py::test_schema_validator_flags_unknown_parameter
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Reviewer rejects unknown parameters, but suggestion quality depends on remap heuristics/LLM remap and is not guaranteed deterministic.
---
## UNNUMBERED-117 — Schema Version + Solver + Commit Metadata
PRD text: - ✅ Schema versions are recorded with solver and commit metadata.

### Q1: Implementation
database/scripts/build_schema.py::SchemaBuilder.save
database/scripts/build_schema.py::build_schema_auto_compose
src/services/schema_staleness.py::check_schema_staleness

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_db_mismatch_policy.py::TestSchemaStalenessCheck::test_matching_commits_no_staleness
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Legacy schemas without `repo_commits` reduce staleness guarantees.
---
## UNNUMBERED-118 — Input Writer Uses Typed Pydantic Objects
PRD text: The `Input Writer` node must manipulate typed Pydantic objects instead of raw text strings. This prevents syntax corrupt

### Q1: Implementation
src/services/input_writer.py::InputWriterService.apply_plan
src/services/config_model_factory.py::ConfigModelFactory.create_from_schema
src/services/config_model_factory.py::ConfigModelFactory.hydrate

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_config_model_modification.py::TestApplyModifications.test_type_coercion_string_to_float
  Integration (real):    tests/integration/test_input_writer_pipeline.py::TestInputWriterPipelineIntegration.test_full_pipeline_load_modify_write_pelec
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_pelec

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
Load-Modify-Write | YES | YES
Legacy fallback raw-dict path | YES | PARTIAL

### Q6: Confidence
HIGH
Risk: `_apply_plan_legacy` still exists and can bypass typed-object guarantees if invoked.
---
## UNNUMBERED-119 — Structured Modify + Dependency + Serialization
PRD text: **Required Behavior:** Apply modifications to structured configs, enforce dependencies, and serialize consistently.

### Q1: Implementation
src/services/config_model_factory.py::ConfigModelFactory.apply_modifications
src/services/rule_engine.py::RuleEngine.enforce
src/services/inputs_file_writer.py::InputsFileWriter.serialize

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_rule_engine_orchestrator.py::TestRuleEngineEnforce::test_enforce_auto_corrects_fixable
  Integration (real):    tests/integration/test_input_writer_pipeline.py::TestInputWriterPipelineIntegration.test_rule_engine_auto_correction_pelec
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_erf

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
Modify structured model | YES | YES
Dependency enforcement | YES | YES
Serialization | YES | YES

### Q6: Confidence
HIGH
Risk: Non-auto-correctable dependency violations are not always hard-blocked in InputWriterService itself.
---
## UNNUMBERED-120 — Parse to Structured Objects Before Modification
PRD text: - ✅ Inputs are parsed into structured objects before modification.

### Q1: Implementation
src/services/input_writer.py::InputWriterService.apply_plan
src/services/config_model_factory.py::ConfigModelFactory.hydrate

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_input_writer_apply_plan.py::test_apply_plan_writes_inputs
  Integration (real):    tests/integration/test_input_writer_pipeline.py::TestInputWriterPipelineIntegration.test_hydration_from_dict_pattern_pelec
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: If schema loading fails, fallback to empty schema weakens guarantees.
---
## UNNUMBERED-121 — Dependency Rules Auto-Fix or Block Invalid Combos
PRD text: - ✅ Dependency rules auto-fix or block invalid combinations.

### Q1: Implementation
src/services/rule_engine.py::RuleEngine.enforce
src/services/rules/common.py::BuildFlagDependencyRule.check
src/services/rules/common.py::BuildFlagDependencyRule.auto_correct

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_rule_engine_orchestrator.py::TestRuleEngineEnforce::test_enforce_preserves_unfixable
  Integration (real):    tests/integration/test_input_writer_pipeline.py::TestInputWriterPipelineIntegration.test_build_flag_constraints_pelec
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Auto-fix path exists, but explicit blocking for unresolved invalid combinations is inconsistent across call sites.
---
## UNNUMBERED-122 — Lossless AMReX Serialization
PRD text: - ✅ Outputs serialize back to AMReX inputs format without loss.

### Q1: Implementation
src/services/inputs_file_writer.py::InputsFileWriter.serialize
src/services/inputs_file_writer.py::InputsFileWriter._ghostwrite
src/services/input_writer.py::apply_plotfile_vars_to_inputs_text

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_inputs_file_writer.py::TestInputsFileWriter.test_full_round_trip_no_changes
  Integration (real):    tests/integration/test_input_writer_pipeline.py::TestInputWriterPipelineIntegration.test_ghostwriter_format_preservation_pelec
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: `modified_keys`-scoped writes can intentionally omit untouched fields from re-emission semantics.
---
## UNNUMBERED-123 — Explicit Contracts + Deterministic Transitions + Valid Outputs
PRD text: **Required Behavior:** Ensure node contracts are explicit, state transitions are deterministic, and node outputs are val

### Q1: Implementation
tests/contracts/architect_node_contract.json::(contract definition)
tests/contracts/reviewer_node_contract.json::(contract definition)
src/models/state_transitions.py::validate_transition
src/router_func.py::route_after_reviewer

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_router_logic.py::TestRouteAfterReviewer::test_route_after_reviewer_retry_with_attempts_remaining
  Integration (real):    tests/integration/test_contract_state_pollution.py::TestWorkflowHistoryCanonicalFormat::test_canonical_workflow_entry_format
  Oracle/E2E (pipeline): tests/e2e/test_readme_command_runner.py::test_readme_command_runner_execute_amrex_agent_only

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
Contract specs | YES | YES
Deterministic routing | YES | YES
Runtime contract enforcement | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: Contracts are strong in tests/docs, but runtime enforcement is not uniformly strict for all nodes.
---
## UNNUMBERED-124 — Nodes Read/Write Declared State Fields Only
PRD text: - ✅ Each node reads/writes only its declared state fields.

### Q1: Implementation
src/models/graph_state_canonical.py::GraphState
tests/quality/test_contract_schema_alignment.py::test_contracts_reference_graphstate_fields
tests/integration/test_contract_state_pollution.py::TestNoPollutionPhilosophy.test_architect_node_returns_only_utility_flags

### Q2: DRY
DUPLICATED
If duplicated: tests/quality/test_contract_schema_alignment.py, tests/integration/test_contract_state_pollution.py.

### Q3: Test pyramid
  Unit (mocked deps):    tests/quality/test_contract_schema_alignment.py::test_contracts_reference_graphstate_fields
  Integration (real):    tests/integration/test_contract_state_pollution.py::TestDownstreamNodeDataAccess::test_reviewer_reads_from_architect_details
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Some nodes still write pragmatic convenience copies at top-level, which weakens strict no-pollution intent.
---
## UNNUMBERED-125 — Failure Routing Back to Architect + Retry Guidance
PRD text: - ✅ Node failures route back to Architect with retry guidance.

### Q1: Implementation
src/nodes/reviewer_node.py::reviewer_node
src/nodes/analysis_node.py::analysis_node
src/router_func.py::route_after_reviewer
src/router_func.py::route_after_analysis

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
Risk: Router uses status/mode heuristics; misclassified failures can still route to terminal instead of retry.
---
## UNNUMBERED-126 — Node Outputs Persisted in workflow_history
PRD text: - ✅ Node outputs are persisted in `workflow_history` for auditability.

### Q1: Implementation
src/nodes/architect_node.py::architect_node
src/nodes/reviewer_node.py::reviewer_node
src/nodes/input_writer_node.py::input_writer_node
src/nodes/runner_node.py::runner_node
src/nodes/analysis_node.py::analysis_node
src/nodes/visualization_node.py::visualization_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_input_writer_node.py::test_success_path_maps_outputs
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::TestFullGraphExecution::test_happy_path_full_workflow
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_pelec

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Some legacy helpers still support string-history compatibility, which can blur canonical-only expectations.
---
## UNNUMBERED-127 — Per-Node LLM and Numerical Error Sources
PRD text: Each node must report **(a) LLM error sources** and **(b) numerical analysis error sources** when applicable. These are 

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
Risk: Error provenance is not standardized at node level, limiting audit and postmortem quality.
---
## UNNUMBERED-128 — error_estimates Append Contract
PRD text: - ✅ Each node appends `error_estimates` with **source, severity, and confidence**.

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
Risk: No `error_estimates` field plumbing means downstream aggregation requirements cannot be satisfied.
---
## UNNUMBERED-129 — Analysis Numerical Error Bounds
PRD text: - ✅ Analysis node includes **numerical error bounds** when available (e.g., discretization order, CFL/step constraints).

### Q1: Implementation
src/services/analysis.py::AnalysisService.analyze_simulation (issues/warnings extraction only)
src/nodes/analysis_node.py::analysis_node

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_analysis_service.py::TestAnalyzeSimulation::test_analyze_simulation_unstable_with_runtime_warnings
  Integration (real):    tests/integration/l3_postprocessing/test_analysis_parsing.py::TestAnalysisNodeParsingIntegration::test_cfl_violation_detection
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: CFL/instability issues are detected, but formal numerical error bounds are not emitted as structured outputs.
---
## UNNUMBERED-130 — Summary Aggregation of Top Error Sources by Node
PRD text: - ✅ Summary aggregation reports top error sources by node for camera-ready tables.

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
Risk: Existing metrics aggregation focuses tokens/retrieval/validation, not ranked per-node error-source tables.
---
## UNNUMBERED-132 — Canonical State Schema (Metrics/Retries/Artifacts)
PRD text: **Required Behavior:** Enforce a canonical state schema with explicit fields for metrics, retries, and artifacts.

### Q1: Implementation
src/models/graph_state_canonical.py::GraphState
src/main.py::initialize_state
tests/unit/test_graph_state_init.py::test_schema_has_node_required_fields

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_graph_state_init.py::test_all_new_fields_have_defaults
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::TestFullGraphExecution::test_state_initialization
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_erf

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: `src/models.py` legacy TypedDict still exists, creating dual-schema maintenance risk.
---
## UNNUMBERED-133 — Nodes R/W Declared Fields (Canonical Enforcement)
PRD text: - ✅ Each node reads/writes only declared fields.

### Q1: Implementation
src/models/graph_state_canonical.py::GraphState
tests/quality/test_contract_schema_alignment.py::test_contracts_reference_graphstate_fields
src/models/state_transitions.py::validate_transition

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/quality/test_contract_schema_alignment.py::test_contracts_reference_graphstate_fields
  Integration (real):    tests/integration/test_contract_state_pollution.py::TestContractSpecCompliance::test_contracts_enforce_workflow_history_reading
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Contract conformance is mostly test-enforced; runtime guardrails are partial.
---
## UNNUMBERED-134 — Metrics Persist to workflow_history.json or metrics.jsonl
PRD text: - ✅ Metrics fields persist to disk in `workflow_history.json` or `metrics.jsonl`.

### Q1: Implementation
src/main.py::main
src/utils/metrics.py::MetricsCollector.write_jsonl

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_metrics_collector.py::test_metrics_collector_aggregates_llm_tokens
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::TestFullGraphExecution::test_happy_path_full_workflow
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_pelelmex_jicf_short

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Persistence to disk depends on CLI flags (`--save-workflow`) and runtime context for path resolution.
---
## UNNUMBERED-135 — State Versioning + Backward Compatibility
PRD text: - ✅ State versioning supports backward compatibility.

### Q1: Implementation
src/models/state_compatibility.py::ensure_history_fields
src/models/state_compatibility.py::add_history_entry
src/models/graph_state_canonical.py::GRAPH_STATE_B1_B2_DEFAULTS

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_graph_state_init.py::test_new_fields_do_not_shadow_existing
  Integration (real):    tests/integration/test_contract_state_pollution.py::TestWorkflowHistoryCanonicalFormat::test_canonical_workflow_entry_format
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Backward-compatibility helpers exist, but explicit `state_version` tagging/migration version registry is absent.
---
## UNNUMBERED-136 — State Schema Table (Required/Optional)
PRD text: 1) State schema table with required/optional fields.

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
Risk: TypedDict provides field definitions, but no maintained required/optional schema table artifact is generated.
---
## Session complete
Criteria audited: 25
Batch: batch_08
Worktree: wt-4
HEAD: 7e5903071fc0a73f464eb0a748157152f30bd9f7
