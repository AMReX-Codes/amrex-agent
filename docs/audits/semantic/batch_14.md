# Audit batch_14
HEAD: 9054208540330cbfe46e05f330e5fd9ab6cb39b7

## [UNNUMBERED-265] — Summary-to-artifact traceability
PRD text: **Required Behavior:** Link summary statements to measurable artifacts and tests.

### Q1: Implementation
scripts/aggregate_metrics.py::main
scripts/compare_models.py::main

### Q2: DRY
DUPLICATED
If duplicated: scripts/aggregate_metrics.py, scripts/compare_models.py.

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_compare_models.py::test_compare_models_generates_tables
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): tests/e2e/test_readme_command_runner.py::test_readme_command_runner_execute_amrex_agent_only

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Mapping exists in docs/scripts, but there is no enforced one-to-one PRD criterion ledger in code.
---
## [UNNUMBERED-266] — Summary references benchmark tables and validation metrics
PRD text: - ✅ Summary references benchmark tables and validation metrics.

### Q1: Implementation
scripts/aggregate_metrics.py::main
src/benchmark_runner.py::_derive_validation_fields

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_contains_schema_valid_field
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Validation metrics are emitted, but benchmark table generation is split across scripts and not release-gated.
---
## [UNNUMBERED-267] — Claims map to results artifacts
PRD text: - ✅ Claims map to evidence in `results/` or `benchmark_results/`.

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
Risk: Repository uses `output/benchmarks` and `benchmark/runs`; no enforced `results/` or `benchmark_results/` artifact contract found.
---
## [UNNUMBERED-268] — Explicit gap and planned-work callouts
PRD text: - ✅ Gaps or planned work are called out explicitly.

### Q1: Implementation
NOT FOUND

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
MEDIUM
Risk: Gaps are documented in docs, but no machine-checked gap registry enforces freshness/ownership.
---
## [UNNUMBERED-269] — Require unit+integration feature coverage
PRD text: **Required Behavior:** Require unit + integration coverage for each feature and track gaps.

### Q1: Implementation
NOT FOUND

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    tests/quality/test_standards.py::test_docs_tooling_expectations
  Integration (real):    tests/integration/test_schema_validator_integration.py::test_schema_validator_flags_unknown_parameter
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_inline_prompt_pelec

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Coverage expectations are documented but not enforced as a per-feature CI policy.
---
## [UNNUMBERED-270] — Acceptance checklist mapped to tests
PRD text: - ✅ Each feature has an acceptance checklist and mapped tests.

### Q1: Implementation
NOT FOUND

### Q2: DRY
NOT_FOUND

### Q3: Test pyramid
  Unit (mocked deps):    tests/quality/test_contract_schema_alignment.py::test_contracts_reference_graphstate_fields
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
NONE
Risk: Docs explicitly note no checklist template, so feature-level acceptance mapping is incomplete.
---
## [UNNUMBERED-271] — Validator and routing unit/integration coverage
PRD text: - ✅ Unit/integration tests cover new validators and routing logic.

### Q1: Implementation
src/services/validation.py::ValidationService.validate_config
src/router_func.py::route_after_reviewer
src/router_func.py::route_after_analysis

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_router_logic.py::TestGraphRoutingLogic.test_route_after_reviewer_retry_with_attempts_remaining
  Integration (real):    tests/integration/test_schema_validator_integration.py::test_schema_validator_flags_type_mismatch_and_syntax
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Good validator/routing coverage exists, but no dedicated e2e oracle asserts validator error categories end-to-end.
---
## [UNNUMBERED-272] — E2E smoke updates for solver-facing changes
PRD text: - ✅ E2E smoke tests updated for solver-facing changes.

### Q1: Implementation
amrex_agent.py::main
tests/e2e/readme_command_runner.py::run_commands_by_file

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_prompt_file_erf

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Solver smoke tests are present, but they are asset-gated and can skip in many CI/local environments.
---
## [UNNUMBERED-273] — Paper-grade deterministic regression harness
PRD text: Benchmark suites serve as **paper-grade evaluation** and **regression protection**. The benchmark harness must be determ

### Q1: Implementation
src/benchmark_runner.py::run_model_benchmark
tests/integration/test_oracle_benchmarks.py::DeterministicEmbedder._embed

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Harness exists but fixed global seeds and strict deterministic replay controls are not enforced in runner code.
---
## [UNNUMBERED-274] — Required outputs section
PRD text: **Required Outputs:**

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
Risk: Criterion is a heading-only statement with no concrete acceptance text to verify.
---
## [UNNUMBERED-275] — Deterministic reproducible benchmark runs
PRD text: **Required Behavior:** Provide deterministic, reproducible benchmark runs with frozen inputs.

### Q1: Implementation
src/benchmark_runner.py::run_model_benchmark
scripts/run_benchmark.py::main
tests/integration/test_oracle_benchmarks.py::DeterministicEmbedder

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Inputs/case lists are stable, but runner-level seed freezing and replay manifests are incomplete.
---
## [UNNUMBERED-276] — 20-25 benchmark cases across solvers
PRD text: - ✅ Benchmark suite runs 20-25 cases across target solvers.

### Q1: Implementation
tests/integration/test_oracle_benchmarks.py::ORACLE_GATE_CASES
tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    ABSENT
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_distribution_is_balanced
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: 20-case gate exists, but it is tied to oracle routing tests and not automatically executed as a benchmark release job.
---
## [UNNUMBERED-277] — Frozen indices, fixed seeds, recorded model configs
PRD text: - ✅ Frozen indices, fixed seeds, and model configs recorded per run.

### Q1: Implementation
src/benchmark_runner.py::_build_config_for_model
src/benchmark_runner.py::run_model_benchmark
database/scripts/build_faiss_manifest.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_no_level0_regression
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Model configs are recorded, but fixed-seed enforcement and index freeze checks are not hard-validated per benchmark run.
---
## [UNNUMBERED-278] — Required CSV and raw metrics outputs
PRD text: - ✅ Outputs include required CSVs and raw metrics.

### Q1: Implementation
scripts/aggregate_metrics.py::main
src/benchmark_runner.py::_write_jsonl
scripts/compare_models.py::main

### Q2: DRY
DUPLICATED
If duplicated: scripts/aggregate_metrics.py, scripts/compare_models.py.

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_compare_models.py::test_compare_models_generates_tables
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Raw JSONL and several CSVs are generated, but required output set is split across two scripts and not validated as one contract.
---
## [UNNUMBERED-279] — Deployment prerequisites/config/verification docs
PRD text: **Required Behavior:** Document deployment prerequisites, configuration, and verification steps.

### Q1: Implementation
NOT FOUND

### Q2: DRY
DUPLICATED
If duplicated: docs/deployment_readiness.md, demo/README.md, demo/superfacility/README.md.

### Q3: Test pyramid
  Unit (mocked deps):    tests/quality/test_standards.py::test_docs_tooling_expectations
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): tests/e2e/test_readme_command_runner.py::test_readme_command_runner_dry_run

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Local CLI | docs/deployment_readiness.md local section | tests/e2e/test_readme_command_runner.py::test_readme_command_runner_execute_amrex_agent_only
Facility/SFAPI | demo/superfacility/README.md | tests/e2e/test_readme_command_runner.py::test_readme_command_runner_execute_superfacility_sfapi

### Q6: Confidence
MEDIUM
Risk: Documentation is present but verification steps are partially aspirational and not fully enforced in CI.
---
## [UNNUMBERED-280] — Local and facility setup env validation
PRD text: - ✅ Local and facility setups include environment validation.

### Q1: Implementation
src/config.py::detect_environment
src/services/config_service.py::ConfigService.initialize

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_config_service.py::test_initialize_from_config_file
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): tests/e2e/test_readme_command_runner.py::test_readme_command_runner_execute_superfacility_sfapi

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
Local | src/config.py::detect_environment | tests/unit/test_config.py::TestDetectEnvironmentDefaultParameter.test_detect_environment_mcp_branch
Perlmutter/SFAPI | docs/mcp.md SFAPI discovery + run_superfacility tools | tests/e2e/test_readme_command_runner.py::test_readme_command_runner_execute_superfacility_sfapi

### Q6: Confidence
MEDIUM
Risk: Environment detection/credential checks exist, but some validations are runtime best-effort instead of strict preflight gates.
---
## [UNNUMBERED-281] — MCP config and required env vars
PRD text: - ✅ MCP server config includes required environment variables.

### Q1: Implementation
src/config.py::detect_environment
mcp_server.py::call_tool
src/services/run_superfacility_tools.py::_resolve_sfapi_credentials

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_mcp_tools.py::test_get_mcp_tool_specs
  Integration (real):    tests/integration/l1_mcp/test_mcp_stdio.py::test_mcp_stdio_initialize_roundtrip
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Required env vars are documented/discovered, but there is no single strict MCP startup validator that fails fast on all missing keys.
---
## [UNNUMBERED-282] — Reproducible isolated benchmark environment
PRD text: - ✅ Benchmark environment is reproducible and isolated.

### Q1: Implementation
src/config.py::resolve_database_path
src/benchmark_runner.py::run_model_benchmark

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Environment lockfile exists, but benchmark execution is not containerized/pinned by default and can vary by host setup.
---
## [UNNUMBERED-283] — Criterion-to-benchmark-and-test linkage
PRD text: **Required Behavior:** Tie each criterion to benchmark outputs and tests.

### Q1: Implementation
NOT FOUND

### Q2: DRY
DUPLICATED
If duplicated: docs/deployment_readiness.md, docs/standards.md.

### Q3: Test pyramid
  Unit (mocked deps):    tests/quality/test_standards.py::test_docs_includes_resolve
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_benchmark_alignment_contract
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Mapping exists as documentation tables, but there is no executable criterion-to-test trace matrix.
---
## [UNNUMBERED-284] — Success criteria map to measurable artifact/test
PRD text: - ✅ Each success criterion maps to a measurable artifact or test.

### Q1: Implementation
NOT FOUND

### Q2: DRY
DUPLICATED
If duplicated: docs/deployment_readiness.md, docs/standards.md.

### Q3: Test pyramid
  Unit (mocked deps):    tests/quality/test_contract_schema_alignment.py::test_contracts_reference_graphstate_fields
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Evidence mapping is mostly narrative and not enforced by a machine-checked artifact inventory.
---
## [UNNUMBERED-285] — Release-gate validation of criteria
PRD text: - ✅ Criteria are validated during release gates.

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
Risk: Release gates are documented as proposed, but no release-gate automation was found in repo scripts/workflows.
---
## [UNNUMBERED-286] — Gap flags with owner and remediation plan
PRD text: - ✅ Gaps are flagged with owner and remediation plan.

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
Risk: Gap lists exist, but owner assignment and remediation tracking fields are not standardized.
---
## [UNNUMBERED-287] — Versioned accessible appendix artifacts
PRD text: **Required Behavior:** List appendix artifacts and ensure they are versioned and accessible.

### Q1: Implementation
NOT FOUND

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_schema_composition.py::test_composed_schema_has_metadata
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_benchmark_alignment_contract
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Artifacts are in version control, but no dedicated appendix manifest guarantees completeness/accessibility.
---
## [UNNUMBERED-288] — Appendix includes oracles/case lists/schema snapshots
PRD text: - ✅ Appendix items include test oracles, case lists, and schema snapshots.

### Q1: Implementation
tests/integration/test_oracle_benchmarks.py::ORACLE_GATE_CASES
src/benchmark_runner.py::collect_cases
database/scripts/build_schema.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_schema_scraper.py::TestParmParseExtraction.test_parmparse_extraction_basic
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Coverage is strong for listed artifact types, but appendixed packaging is distributed across multiple directories.
---
## [UNNUMBERED-289] — Artifacts include source commit and build date
PRD text: - ✅ Artifacts reference source commit and build date.

### Q1: Implementation
src/benchmark_runner.py::run_model_benchmark

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    ABSENT
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: Build timestamp is recorded (`created_at`), but source commit is not explicitly captured in benchmark manifests.
---
## Session complete
Criteria audited: 25
Batch: batch_14
Worktree: wt-5
HEAD: $(git rev-parse HEAD)
