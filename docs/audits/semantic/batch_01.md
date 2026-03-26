# Audit batch_01
HEAD: e2603fa968244ca07b2aa8710074f97a0ed06833

## [B3-01] — Amendment B3 Benchmark V&V Instrumentation
PRD text: Section requirement: AMENDMENT B3: Benchmark V&V Instrumentation

### Q1: Implementation
src/benchmark_runner.py::_normalize_benchmark_record
src/benchmark_runner.py::_derive_validation_fields
src/benchmark_runner.py::_derive_iteration_fields
src/benchmark_runner.py::_derive_benchmark_metrics_fields
src/benchmark_runner.py::_derive_gate_approval_fields
src/benchmark_runner.py::_write_jsonl

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_no_new_required_field_breaks_existing
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_benchmark_context_solver_metadata_persists_to_jsonl
  Oracle/E2E (pipeline): tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Instrumentation is concentrated in benchmark JSONL normalization, so future schema drift could silently reduce completeness.
---
## [B3-02] — gate_approvals Present at Session Start
PRD text: session begins. `gate_approvals` must be in GraphState.

### Q1: Implementation
src/models/graph_state_canonical.py::GraphState
src/models/graph_state_canonical.py::GRAPH_STATE_B1_B2_DEFAULTS

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_gate_approvals_state.py::test_gate_approvals_independent_across_state_copies
  Integration (real):    tests/integration/test_contract_state_pollution.py::test_gate_approvals_list_not_shared_between_states
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: GraphState is TypedDict-only, so runtime callers can still pass malformed gate approval entries.
---
## [B3.1-01] — Feature B JSONL Fields Overview
PRD text: Section requirement: B3.1 Feature B — Benchmark JSONL Output Fields

### Q1: Implementation
src/benchmark_runner.py::_normalize_benchmark_record
src/benchmark_runner.py::_write_jsonl

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_contains_schema_valid_field
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_benchmark_context_solver_metadata_persists_to_jsonl
  Oracle/E2E (pipeline): tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Required-field enforcement relies on defaulting behavior rather than strict schema validation.
---
## [B3.1-02] — Required Unit Test Entry
PRD text: | `tests/unit/test_benchmark_runner.py` | `test_jsonl_includes_feature_b_required_fields` | unit | B3.1 required fields

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
Risk: The explicitly named unit test does not exist, so traceability to the criterion is missing.
---
## [B3.1-03] — benchmark_runner Required Output Fields
PRD text: `src/benchmark_runner.py`. All fields are required in output. Fields that

### Q1: Implementation
src/benchmark_runner.py::_derive_validation_fields
src/benchmark_runner.py::_derive_iteration_fields
src/benchmark_runner.py::_derive_benchmark_metrics_fields
src/benchmark_runner.py::_derive_gate_approval_fields

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_no_new_required_field_breaks_existing
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_benchmark_context_solver_metadata_persists_to_jsonl
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Several fields default to placeholder values (`False`, `0`, `[]`), which may mask missing upstream data.
---
## [B3.1-04] — GraphState Field Confirmation for Output
PRD text: must be confirmed to exist in canonical GraphState or added if absent.

### Q1: Implementation
src/models/graph_state_canonical.py::GraphState
src/benchmark_runner.py::_normalize_benchmark_record

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_field_null_with_reason_when_unavailable
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Some normalized fields (`wall_time_seconds`, `architect_time_seconds`) are not canonical GraphState keys and are synthesized fallback metrics.
---
## [B3.2-01] — Missing Solver Family Case Coverage
PRD text: - At least one case per missing solver family.

### Q1: Implementation
benchmark/cases/pelec.yaml::<suite cases>
benchmark/cases/pelelmex.yaml::<suite cases>
benchmark/cases/erf.yaml::<suite cases>
benchmark/cases/remora.yaml::<suite cases>
tests/integration/test_oracle_benchmarks.py::_oracle_catalog

### Q2: DRY
DUPLICATED
If duplicated: benchmark/cases/*.yaml and tests/integration/test_oracle_benchmarks.py (hard-coded override catalog for non-benchmark-backed families).

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_benchmark_alignment_contract
  Oracle/E2E (pipeline): tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Coverage exists for several solver families, but non-benchmark-backed overrides indicate incomplete canonical cataloging.
---
## [B3.2-02] — Oracle Expansion Methodology
PRD text: Section requirement: B3.2 Oracle Expansion Methodology

### Q1: Implementation
tests/integration/test_oracle_benchmarks.py::_ORACLE_GATE_CASES_RAW
tests/integration/test_oracle_benchmarks.py::_synchronize_oracle_cases_with_benchmark
tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced
  Oracle/E2E (pipeline): tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Easy/Medium/Hard tiers | YES | YES
Extended backlog xfail | YES | YES

### Q6: Confidence
HIGH
Risk: Methodology is test-embedded and may drift without an external design artifact.
---
## [B4-01] — Amendment B4 Deferred Design
PRD text: Section requirement: AMENDMENT B4: Paper Validator — Design Specification (Deferred)

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
Risk: No paper-validator design implementation is present in src/tests.
---
## [B4.1-01] — B4.1 Overview
PRD text: Section requirement: B4.1 Overview

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
Risk: No overview artifact tied to B4.1 exists in code or tests.
---
## [B4.2-01] — B4.2 Graph Topology Addition
PRD text: Section requirement: B4.2 Graph Topology Addition

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
Risk: No paper-validator node is added in graph wiring.
---
## [B4.3-01] — B4.3 Paper Parser Service
PRD text: Section requirement: B4.3 Paper Parser Service

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
Risk: No parser service for paper validation is implemented.
---
## [B4.4-01] — B4.4 Validation Manifest Schema
PRD text: Section requirement: B4.4 Validation Manifest Schema

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
Risk: No manifest schema for paper-validator outputs is present.
---
## [B4.5-01] — B4.5 Paper Validator Mode 1
PRD text: Section requirement: B4.5 Paper Validator Node — Mode 1

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
Phase | Impl | Tests
Mode 1 | NO | NO

### Q6: Confidence
NONE
Risk: Mode 1 validator node behavior is entirely absent.
---
## [B4.6-01] — B4.6 Paper Validator Mode 2
PRD text: Section requirement: B4.6 Paper Validator Node — Mode 2

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
Phase | Impl | Tests
Mode 2 | NO | NO

### Q6: Confidence
NONE
Risk: Mode 2 validator node behavior is entirely absent.
---
## [B4.7-01] — B4.7 New CLI Arguments
PRD text: Section requirement: B4.7 New CLI Arguments

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
Risk: CLI parser has no paper-validator-specific arguments.
---
## [B4.8-01] — B4.8 Implementation Sequencing
PRD text: Section requirement: B4.8 Implementation Sequencing

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
Phase | Impl | Tests
Design sequence | NO | NO

### Q6: Confidence
NONE
Risk: No staged sequencing artifact for B4 implementation exists.
---
## [UNNUMBERED-001-01] — New File LOC <= 100
PRD text: - Max LOC per new file: `<=100` (PRD2 standard, decomposition required above this threshold).

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
Risk: No repository policy/test enforces this LOC threshold for new files.
---
## [UNNUMBERED-001-02] — Orchestration Complexity <= 10
PRD text: - no orchestration function >10 complexity.

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
Risk: No automatic orchestration complexity gate exists in test suite or CI config.
---
## [UNNUMBERED-001-03] — Benchmark Record Builder Complexity
PRD text: - no benchmark record builder function exceeds complexity threshold.

### Q1: Implementation
src/benchmark_runner.py::_normalize_benchmark_record
src/benchmark_runner.py::_derive_validation_fields
src/benchmark_runner.py::_derive_iteration_fields
src/benchmark_runner.py::_derive_benchmark_metrics_fields
src/benchmark_runner.py::_derive_gate_approval_fields

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_no_new_required_field_breaks_existing
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: `radon` is unavailable in environment, so complexity threshold compliance is unverified.
---
## [UNNUMBERED-001-04] — Global Function Complexity Threshold
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
LOW
Risk: No complexity tooling/check is configured to enforce a global threshold.
---
## [UNNUMBERED-002-01] — radon cc No New Function > 10
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
LOW
Risk: `python -m radon cc` failed because `radon` is not installed.
---
## [UNNUMBERED-002-02] — New File >100 LOC Helper Extraction
PRD text: - no new file >100 LOC without helper extraction.

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
Risk: No check enforces this threshold or requires helper extraction documentation.
---
## [UNNUMBERED-002-03] — Backward-Compatible Output Keys Regression Coverage
PRD text: - regression tests confirm backward-compatible output keys still present.

### Q1: Implementation
tests/unit/test_benchmark_runner.py::test_jsonl_no_new_required_field_breaks_existing
tests/unit/test_benchmark_runner.py::test_jsonl_field_null_with_reason_when_unavailable

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_no_new_required_field_breaks_existing
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_benchmark_context_solver_metadata_persists_to_jsonl
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Coverage focuses on benchmark JSONL fields; broader workflow output key compatibility is not comprehensively validated.
---
## [UNNUMBERED-002-04] — Dedicated Unit Tests per Parser/Validator Mode
PRD text: - each parser/validator mode has dedicated unit tests.

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
Phase | Impl | Tests
Parser/validator mode-specific suites | NO | NO

### Q6: Confidence
NONE
Risk: No paper parser/validator mode implementation exists, so dedicated unit tests are also absent.
---
## [UNNUMBERED-003-01] — Amendment Module LOC and Helper Extraction
PRD text: - no new amendment module >100 LOC without documented helper extraction.

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
Risk: No amendment-specific structural guardrails are implemented.
---
## [UNNUMBERED-003-02] — Unit per Phase + Fan-out/Fan-in Integration
PRD text: - unit tests per phase + integration test for fan-out/fan-in.

### Q1: Implementation
src/graph.py::create_graph
tests/unit/test_graph_wiring.py::test_sweep_detection_with_sweep_routes_to_handler
tests/unit/test_graph_wiring.py::test_oracle_paths_unaffected_by_sweep_wiring

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_graph_wiring.py::test_sweep_detection_with_sweep_routes_to_handler
  Integration (real):    tests/integration/test_sweep_orchestration.py::test_detect_sweep_single_param
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Fan-out sweep path | PARTIAL | YES
Fan-in aggregation path | NO | NO

### Q6: Confidence
MEDIUM
Risk: Fan-out detection is tested, but explicit fan-in merge/integration behavior is not evidenced.
---
## [UNNUMBERED-001-05] — Instrumentation Scope Creep Risk
PRD text: 1. **Instrumentation Scope Creep:** Current coverage 10-30%, target 100% by Week 2 → must prioritize minimal invasive ch

### Q1: Implementation
src/benchmark_runner.py::_normalize_benchmark_record

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_contains_schema_valid_field
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_benchmark_context_solver_metadata_persists_to_jsonl
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Instrumentation is minimally invasive, but full 100% coverage target is not measured or enforced.
---
## [UNNUMBERED-002-05] — Claim/Evidence Coverage Matrix
PRD text: | Claim | Required Evidence | Current Coverage | Gap |

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
Risk: No claim-to-evidence matrix artifact is present in repo for this amendment block.
---
## [UNNUMBERED-003-03] — Required Capability v26.05
PRD text: ✅ **Required Capability (v26.05):**

### Q1: Implementation
src/benchmark_runner.py::_normalize_benchmark_record
src/models/graph_state_canonical.py::GraphState
tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_no_new_required_field_breaks_existing
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced
  Oracle/E2E (pipeline): tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Core capability pieces exist, but B4 paper-validator capabilities remain unimplemented.
---
## Session complete
Criteria audited: 30
Batch: batch_01
Worktree: wt-2
HEAD: e2603fa968244ca07b2aa8710074f97a0ed06833
