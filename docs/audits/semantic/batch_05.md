# Audit batch_05
HEAD: 5293b7f3bf83db8a80c9f6c3948bcb23a95b2f7e

## [UNNUMBERED-035] — Metrics Endpoint Workflow/Cost Summary
PRD text: - ✅ Metrics endpoint exposes workflow and cost summaries.

### Q1: Implementation
src/utils/metrics.py::MetricsCollector.build_workflow_summary
src/main.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_metrics_collector.py::test_metrics_collector_aggregates_llm_tokens
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Workflow metrics aggregation | YES | PARTIAL
Cost-summary surface as endpoint | PARTIAL | NO

### Q6: Confidence
MEDIUM
Risk: metrics are persisted as JSONL summaries, but no dedicated MCP/API metrics endpoint is explicitly implemented.
---
## [UNNUMBERED-037] — UC Summary Traceability Requirement
PRD text: **Required Behavior:** Each summarized use case maps to at least one test, fixture, or benchmark artifact.

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
LOW
Risk: use-case mapping exists narratively in PRD text but no executable traceability enforcement was found.
---
## [UNNUMBERED-038] — UC Row Has Traceable Artifact
PRD text: - ✅ Each UC row has a traceable test/fixture or benchmark artifact.

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
LOW
Risk: PRD includes references, but no code-level check guarantees every UC row has a current artifact link.
---
## [UNNUMBERED-039] — UC8-UC20 Metrics Defined/Measurable
PRD text: - ✅ Metrics for UC8-UC20 are defined and measurable.

### Q1: Implementation
src/benchmark_runner.py::_write_jsonl
src/benchmark_runner.py::run_model_benchmark
scripts/aggregate_metrics.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_contains_schema_valid_field
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Metric field emission | YES | YES
UC8-UC20 explicit coverage gate | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: benchmark metric fields are emitted, but direct UC8-UC20-to-metric coverage assertions are not enforced in one place.
---
## [UNNUMBERED-040] — Cross-References Include Feature IDs
PRD text: - ✅ Cross-references include owning feature IDs.

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
LOW
Risk: feature-ID cross-references are documentation-only and are not validated by tooling.
---
## [UNNUMBERED-041] — Edge Cases Deterministic/User-Guided/Logged
PRD text: **Required Behavior:** Edge case handling must be deterministic, user-guided, and logged for analysis.

### Q1: Implementation
src/nodes/clarification_node.py::clarification_node
src/nodes/reviewer_node.py::reviewer_node
src/nodes/reviewer_node.py::_derive_retry_guidance
src/router_func.py::route_after_reviewer
src/router_func.py::route_after_analysis

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_retry_guidance.py::test_retry_guidance_switch_inputs_on_persistent_unknowns
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::TestErrorRecovery.test_max_retries_enforced
  Oracle/E2E (pipeline): tests/integration/l5_full_pipeline/test_full_graph.py::TestFullGraphExecution.test_happy_path_full_workflow

### Q4: Mock fidelity
DRIFTED
If drifted: canonical `clarification_questions` is `List[str]`, while clarification/recovery tests use dict-shaped question objects.

### Q5: Phase completeness
Phase | Impl | Tests
Deterministic edge checks | YES | YES
Guided retry/refinement | YES | YES
Structured logging to history | YES | YES

### Q6: Confidence
HIGH
Risk: schema typing mismatch for clarification payload shape can still cause contract drift.
---
## [UNNUMBERED-042] — Ambiguous Prompts Guided Refinement
PRD text: - ✅ Ambiguous prompts return guided refinement prompts with examples.

### Q1: Implementation
src/nodes/clarification_node.py::_check_level_2_physics_ambiguity
src/nodes/clarification_node.py::_required_field_question
src/nodes/clarification_node.py::clarification_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_clarification_node.py::TestDecisionLevels.test_level_2_physics_ambiguity_requires_priority
  Integration (real):    tests/integration/test_clarification_recovery.py::TestAmbiguousPromptEntersClarification.test_missing_required_field_routes_to_clarification
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
DRIFTED
If drifted: clarification question objects are asserted as dict records in tests while GraphState types `clarification_questions` as `List[str]`.

### Q5: Phase completeness
Phase | Impl | Tests
Ambiguity detection | YES | YES
Guided follow-up questioning | YES | YES
Example-rich prompt templates | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: ambiguous-prompt guidance exists, but example richness is not consistently asserted in tests.
---
## [UNNUMBERED-043] — Unsupported Physics Graceful Alternatives/Failure
PRD text: - ✅ Unsupported physics returns alternatives or fails gracefully.

### Q1: Implementation
src/services/architect.py::ArchitectService.select_solver
src/services/validators/physics_validator.py::PhysicsValidator.validate
src/nodes/reviewer_node.py::reviewer_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_physics_validator.py::TestPhysicsValidator.test_rejects_unknown_solver
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::TestErrorRecovery.test_reviewer_rejection_triggers_retry
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Unsupported-solver detection | YES | YES
Fallback/retry guidance | YES | YES
Alternative baseline suggestion | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: graceful failure path is strong, but explicit alternative suggestion quality depends on heuristic/LLM guidance.
---
## [UNNUMBERED-044] — Retries Bounded and Taxonomy-Logged
PRD text: - ✅ Validation retries are bounded and logged with error taxonomy.

### Q1: Implementation
src/router_func.py::route_after_reviewer
src/nodes/reviewer_node.py::reviewer_node
src/nodes/reviewer_node.py::_derive_retry_guidance
src/services/reviewer.py::ReviewerOrchestrator.validate_plan

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_router_logic.py::TestGraphRoutingLogic.test_route_after_reviewer_max_retries_exceeded
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::TestErrorRecovery.test_max_retries_enforced
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
Retry bound enforcement | YES | YES
Violation categorization/reasons | YES | PARTIAL
History logging of outcomes | YES | YES

### Q6: Confidence
HIGH
Risk: taxonomy semantics are encoded via rule names/reasons, but no single explicit taxonomy schema contract is enforced.
---
## [UNNUMBERED-045] — Deterministic Benchmark Baseline Repro
PRD text: - ✅ Deterministic benchmark mode reproduces baseline selection.

### Q1: Implementation
database/indexing/level0_searcher.py::Level0Searcher.search
tests/integration/test_oracle_benchmarks.py::DeterministicEmbedder._embed
tests/integration/test_oracle_benchmarks.py::run_selection_pipeline

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_no_level0_regression
  Oracle/E2E (pipeline): tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Deterministic embedding/search path | PARTIAL | YES
Baseline reproducibility gate set | YES | YES

### Q6: Confidence
MEDIUM
Risk: deterministic behavior is primarily test-scaffolded (hash embedder), not exposed as a first-class runtime benchmark mode toggle.
---
## [UNNUMBERED-046] — Critical Path Features Section
PRD text: **Critical Path Features (Must-Have for Publication):**

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
Risk: this is a PRD planning section header with no executable implementation artifact.
---
## [UNNUMBERED-047] — Unattended Execution Robust Edge Handling
PRD text: - \* Unattended execution must handle all edge cases robustly

### Q1: Implementation
src/main.py::main
src/main.py::run_agent
src/router_func.py::route_after_reviewer
src/router_func.py::route_after_runner

### Q2: DRY
DUPLICATED
If duplicated: src/graph.py, src/main.py (separate graph construction/execution surfaces can drift).

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_router_logic.py::TestGraphRoutingLogic.test_route_after_reviewer_max_retries_exceeded
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::TestErrorRecovery.test_error_history_tracking
  Oracle/E2E (pipeline): tests/integration/l5_full_pipeline/test_full_graph.py::TestFullGraphExecution.test_happy_path_full_workflow

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
Unattended happy path | YES | YES
Edge-case retry/terminal handling | YES | YES
Comprehensive edge-case closure | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: broad robustness claim exceeds current explicit coverage for all edge-case classes.
---
## [UNNUMBERED-048] — Out-of-Scope Excluded from v26.05 Validation
PRD text: - ✅ Out-of-scope items are explicitly excluded from v26.05 validation.

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
LOW
Risk: exclusion boundaries are documented but not machine-enforced by validation tooling.
---
## [UNNUMBERED-049] — Scope Boundaries Align Camera-Ready
PRD text: - ✅ Scope boundaries align with camera-ready requirements.

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
LOW
Risk: camera-ready alignment exists in PRD narrative without a dedicated enforcement test.
---
## [UNNUMBERED-050] — Feature Blocks Must Include Tests/Fixtures
PRD text: **Required Behavior:** Every feature block includes a `Tests/Fixtures` line mapping to validation artifacts.

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
Risk: no linter/checker was found to enforce this documentation format requirement.
---
## [UNNUMBERED-051] — Features Include Explicit Test/Fixture Mapping
PRD text: - ✅ Each feature includes explicit tests/fixtures mapping.

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
LOW
Risk: mapping appears in PRD content but has no automated consistency check.
---
## [UNNUMBERED-052] — Impl Locations and Tests Kept in Sync
PRD text: - ✅ Implementation locations and tests are kept in sync.

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
LOW
Risk: no synchronization/verification script was found to guard doc-to-code drift.
---
## [UNNUMBERED-053] — Alternative Rejection Reasons Comprehensive
PRD text: - Medium: Alternative rejection reasons must be comprehensive (requires domain knowledge)

### Q1: Implementation
src/services/architect.py::ArchitectService.select_baseline
src/nodes/architect_node.py::architect_node
src/nodes/reviewer_node.py::_derive_retry_guidance

### Q2: DRY
DUPLICATED
If duplicated: src/services/architect.py, src/nodes/reviewer_node.py (parallel reason-generation paths).

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_baseline_selection.py::TestLevel2FallbackRanking.test_level2_fallback_ranking
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::TestErrorRecovery.test_reviewer_rejection_triggers_retry
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
DRIFTED
If drifted: architect-node service tests use `selected_solvers` state key that is not part of canonical GraphState.

### Q5: Phase completeness
Phase | Impl | Tests
Alternative selection/rejection logic | PARTIAL | PARTIAL
Comprehensive domain rationale | PARTIAL | NO

### Q6: Confidence
MEDIUM
Risk: rejection rationale quality is partly heuristic and lacks comprehensive domain-grounded assertions.
---
## [UNNUMBERED-054] — Manual CSV Creation Requirement
PRD text: - Manual CSV creation required

### Q1: Implementation
scripts/aggregate_metrics.py::main
scripts/compare_models.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Automated CSV/aggregation scripts | YES | NO
Manual-only workflow retained | NO | NO

### Q6: Confidence
MEDIUM
Risk: repository now includes aggregation scripts, so PRD statement about required manual CSV creation appears stale.
---
## [UNNUMBERED-055] — Level-4 Depth Guidance
PRD text: - **Level 4 (`####`):** 80-120 lines baseline, but **may expand to 500-1000 lines** when near implementation, high complexity, or needed for camera-ready rigor.

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
Risk: this is authoring guidance text with no executable enforcement.
---
## [UNNUMBERED-056] — Consistency Checklist: Required Behavior Item
PRD text: - Required behavior (what must be true)

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
Risk: checklist guidance is not validated by a documentation lint/CI rule.
---
## [UNNUMBERED-057] — Consistency Checklist: Implementation Locations Item
PRD text: - Implementation locations (files/services)

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
Risk: no automatic check ensures every relevant section includes implementation-location pointers.
---
## [UNNUMBERED-058] — Story 2 Maria Baseline Case
PRD text: * **Story 2:** As Maria, I want a validated baseline case for a premixed methane flame, so I don't start from an empty input file.

### Q1: Implementation
src/services/architect.py::ArchitectService.select_solver
src/services/architect.py::ArchitectService.select_baseline
src/services/architect.py::ArchitectService.execute_planning
tests/integration/test_oracle_benchmarks.py::run_selection_pipeline

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_baseline_selection.py::TestLevel2BaselineScoring.test_level2_baseline_scoring
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): tests/integration/test_oracle_benchmarks.py::test_squall_line_no_level0_regression

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Premixed methane solver routing | YES | YES
Baseline case selection | YES | YES
Validation before execution | YES | PARTIAL

### Q6: Confidence
HIGH
Risk: story-specific PMF/FlameSheet expectations are tested, but validation depth still depends on available local indices/catalog completeness.
---
## [UNNUMBERED-059] — Story 3 Grid Refinement vs Blocking Factors
PRD text: * **Story 3:** As Maria, I want to be warned if my grid refinement ratios are inconsistent with AMReX blocking factors, so I avoid job crashes.

### Q1: Implementation
src/services/rules/common.py::GridConsistencyRule.check
src/services/rules/common.py::GridConsistencyRule.auto_correct
src/services/rule_engine.py::RuleEngine.enforce

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_rule_engine_orchestrator.py::TestRuleEngineEnforce.test_enforce_auto_corrects_fixable
  Integration (real):    tests/integration/test_input_writer_pipeline.py::TestInputWriterPipeline.test_rule_engine_auto_correction_pelec
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Grid/blocking mismatch detection | YES | YES
Auto-correction | YES | YES
Ref-ratio specific warning path | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: blocking-factor consistency is enforced, but explicit `ref_ratio` mismatch warning coverage is weaker than the PRD wording.
---
## [UNNUMBERED-060] — Story 4 Baseline Selection Reasoning Visibility
PRD text: * **Story 4:** As Maria, I want to see the reasoning for a specific baseline selection, so I can learn the Pele repository structure.

### Q1: Implementation
src/services/architect.py::_generate_reasoning_from_plan
src/nodes/architect_node.py::architect_node
src/services/architect.py::ArchitectService.execute_planning

### Q2: DRY
DUPLICATED
If duplicated: src/services/architect.py, src/nodes/architect_node.py (reasoning assembled in service and re-annotated at node layer).

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_architect_node_service.py::TestArchitectNodeServiceOrchestration.test_maps_plan_to_state
  Integration (real):    tests/integration/l5_full_pipeline/test_full_graph.py::TestFullGraphExecution.test_happy_path_full_workflow
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
DRIFTED
If drifted: architect-node service tests use non-canonical `selected_solvers` in mocked state, indicating state-contract drift from `graph_state_canonical.py`.

### Q5: Phase completeness
Phase | Impl | Tests
Reasoning generation | YES | PARTIAL
Reasoning persisted to workflow/state | YES | YES
Pele-structure teaching quality | PARTIAL | NO

### Q6: Confidence
MEDIUM
Risk: reasoning is persisted, but tests do not strongly validate repository-structure educational quality or citation specificity.
---
## Session complete
Criteria audited: 25
Batch: batch_05
Worktree: wt-1
HEAD: 5293b7f3bf83db8a80c9f6c3948bcb23a95b2f7e
