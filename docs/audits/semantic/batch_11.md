# Audit batch_11
HEAD: 8668e88784c377917afc099c42ab6117a1be1eec

## [UNNUMBERED-189] — Post-Incident Risk Matrix Feedback
PRD text: - ✅ Post-incident updates feed back into the risk matrix.

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
Risk: A static risk register exists in PRD text, but no executable feedback pipeline was found.
---
## [UNNUMBERED-190] — Component Boundaries, Contracts, Dependencies
PRD text: **Required Behavior:** Define component boundaries, data contracts, and external dependencies.

### Q1: Implementation
src/graph.py::create_graph
src/models/graph_state_canonical.py::GraphState
src/nodes/architect_node.py::architect_node
src/nodes/reviewer_node.py::reviewer_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/integration/test_contract_state_pollution.py::test_contracts_enforce_workflow_history_reading
  Integration (real):    tests/integration/test_contract_state_pollution.py::test_canonical_workflow_entry_format
  Oracle/E2E (pipeline): tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
Boundary definitions | YES | YES
Contract definitions | YES | YES
Dependency declaration | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: Contracts are mostly test fixtures/JSON specs, with partial runtime enforcement.
---
## [UNNUMBERED-191] — Component I/O and Responsibilities Listed
PRD text: - ✅ Each component lists inputs, outputs, and primary responsibilities.

### Q1: Implementation
src/nodes/architect_node.py::architect_node
src/nodes/reviewer_node.py::reviewer_node
src/nodes/input_writer_node.py::input_writer_node
src/nodes/runner_node.py::runner_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/integration/test_contract_state_pollution.py::test_contracts_forbid_top_level_computation_output
  Integration (real):    tests/integration/test_contract_state_pollution.py::test_contracts_enforce_workflow_history_reading
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Listings are strongest in contract docs; responsibilities are not centrally enforced beyond tests.
---
## [UNNUMBERED-192] — Per-Component External Service Dependencies
PRD text: - ✅ External service dependencies are declared per component.

### Q1: Implementation
src/nodes/architect_node.py::architect_node
src/nodes/input_writer_node.py::input_writer_node
src/nodes/runner_node.py::runner_node
src/services/embedding_service_factory.py::get_embedding_service

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_embedding.py::test_factory_returns_service_with_instance_cache
  Integration (real):    tests/integration/test_infrastructure.py::test_environment_smoke
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Dependencies are instantiated in code paths, but there is no single machine-readable dependency manifest per component.
---
## [UNNUMBERED-193] — State Persistence Points Documented
PRD text: - ✅ State persistence points are documented.

### Q1: Implementation
src/services/workflow_store.py::WorkflowStore
src/main.py::main
src/benchmark_runner.py::run_model_benchmark

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_workflow_store.py::test_sweep_metadata_json_schema
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Persistence exists in multiple locations, but documentation is distributed across contracts/docs instead of one map.
---
## [UNNUMBERED-194] — Steps Mapped to State Fields and Artifacts
PRD text: **Required Behavior:** Ensure each step maps to explicit state fields and artifacts.

### Q1: Implementation
src/models/graph_state_canonical.py::GraphState
src/nodes/architect_node.py::architect_node
src/nodes/input_writer_node.py::input_writer_node
src/nodes/reviewer_node.py::reviewer_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_graph_state_init.py::test_state_schema_coverage
  Integration (real):    tests/integration/test_contract_state_pollution.py::test_canonical_workflow_entry_format
  Oracle/E2E (pipeline): tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
Phase | Impl | Tests
State-field mapping | YES | YES
Artifact-path mapping | YES | YES

### Q6: Confidence
HIGH
Risk: Mapping relies on discipline between node returns and workflow_history details.
---
## [UNNUMBERED-195] — Each Step Writes Declared GraphState Fields
PRD text: - ✅ Each step writes to declared `GraphState` fields.

### Q1: Implementation
src/models/graph_state_canonical.py::GraphState
src/nodes/architect_node.py::architect_node
src/nodes/reviewer_node.py::reviewer_node
src/nodes/input_writer_node.py::input_writer_node
src/nodes/runner_node.py::runner_node
src/nodes/analysis_node.py::analysis_node
src/nodes/visualization_node.py::visualization_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_graph_state_init.py::test_serialization_matches_workflow_history_pattern
  Integration (real):    tests/integration/l5_full_pipeline/test_schema_validation.py::test_validation_blocks_invalid_inputs
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
ALIGNED

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Some node contracts still describe stricter top-level constraints than runtime code currently uses.
---
## [UNNUMBERED-196] — Stable Artifact Paths Under output/
PRD text: - ✅ Artifacts are persisted with stable paths under `output/`.

### Q1: Implementation
src/main.py::parse_arguments
src/main.py::initialize_state
src/nodes/input_writer_node.py::input_writer_node
scripts/run_benchmark.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): tests/e2e/test_demo_smoke.py::test_demo_amrex_baseline_override

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Paths are stable by convention (`output/` + run timestamp), but not globally schema-validated.
---
## [UNNUMBERED-197] — Failure Paths Capture Recovery Hints and Evidence Links
PRD text: - ✅ Failure paths capture recovery hints and evidence links.

### Q1: Implementation
src/nodes/reviewer_node.py::reviewer_node
src/nodes/analysis_node.py::analysis_node
src/nodes/architect_node.py::architect_node

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_retry_guidance.py::test_retry_guidance_switch_inputs_on_persistent_unknowns
  Integration (real):    tests/integration/l5_full_pipeline/test_error_recovery.py::test_errors_tracked_in_workflow_history
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Retry guidance is present, but explicit evidence-link normalization is inconsistent across nodes.
---
## [UNNUMBERED-198] — Env Pinning, Deployment Topology, Operational Constraints Documentation
PRD text: **Required Behavior:** Document environment pinning, deployment topology, and operational constraints.

### Q1: Implementation
src/config.py::AMReXAgentConfig
docs/deployment_readiness.md::NOT_FOUND

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_config.py::test_config_defaults
  Integration (real):    tests/integration/test_infrastructure.py::test_environment_smoke
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Environment constraints | PARTIAL | PARTIAL
Deployment topology docs | PARTIAL | PARTIAL
Operational constraints | PARTIAL | PARTIAL

### Q6: Confidence
MEDIUM
Risk: Constraints are documented as evolving, not frozen camera-ready artifacts.
---
## [UNNUMBERED-199] — Frozen Environment/Dependency Constraints for Benchmarks
PRD text: - ✅ Environment and dependency constraints are frozen for benchmarks.

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
Risk: Deployment docs explicitly state benchmark standardization is still evolving.
---
## [UNNUMBERED-200] — Reproducible Facility Deployment Config Files
PRD text: - ✅ Facility deployment uses reproducible configuration files.

### Q1: Implementation
src/services/run_superfacility.py::SuperfacilityRunner
src/services/run_superfacility_tools.py::submit_job
src/services/config_service.py::ConfigService.initialize

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_run_superfacility.py::test_submit_dry_run
  Integration (real):    tests/integration/test_infrastructure.py::test_environment_smoke
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Facility config handling exists, but reproducibility guarantees are not validated end-to-end in benchmark flows.
---
## [UNNUMBERED-201] — Monitoring and Logging Sources Documented
PRD text: - ✅ Monitoring and logging sources are documented.

### Q1: Implementation
src/main.py::setup_logging
src/utils/metrics.py::MetricsCollector
src/benchmark_runner.py::_write_jsonl

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_llm_call_count_present
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Logging/metrics capture exists, but no single operator-facing monitoring source map was found.
---
## [UNNUMBERED-202] — Camera-Ready Candidate Evaluation and Decision Rationale
PRD text: **Required Behavior:** Evaluate candidates against camera-ready criteria and document decision rationale.

### Q1: Implementation
scripts/compare_models.py::main
scripts/aggregate_metrics.py::main
src/benchmark_runner.py::run_model_benchmark

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_compare_models.py::test_compare_models_generates_tables
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Candidate evaluation outputs | YES | YES
Decision rationale artifact | PARTIAL | ABSENT

### Q6: Confidence
MEDIUM
Risk: Metrics tables are generated, but explicit final-decision rationale artifacts are not enforced.
---
## [UNNUMBERED-203] — Comparison Table Fields (Persistence, Retries, Gating, MCP/A2A)
PRD text: - ✅ Comparison table includes state persistence, retries, gating, MCP/A2A integration.

### Q1: Implementation
src/benchmark_runner.py::_derive_iteration_fields
src/benchmark_runner.py::_derive_gate_approval_fields
scripts/compare_models.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_gate_approvals_written_to_jsonl
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Retry and gate fields are present, but MCP/A2A-specific comparison columns are not explicitly produced by compare scripts.
---
## [UNNUMBERED-204] — Decision Rationale with Risks and Migration Costs
PRD text: - ✅ Decision rationale documented with risks and migration costs.

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
Risk: No structured, generated artifact linking benchmark outcomes to migration-cost risk decisions was found.
---
## [UNNUMBERED-205] — Benchmark Evidence Supports Final Selection
PRD text: - ✅ Benchmark evidence supports the final selection.

### Q1: Implementation
src/benchmark_runner.py::run_model_benchmark
scripts/compare_models.py::main
scripts/aggregate_metrics.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Evidence generation is implemented, but “final selection” is not programmatically asserted.
---
## [UNNUMBERED-206] — Versioned Indices with Coverage Metadata and Ownership
PRD text: **Required Behavior:** Maintain versioned indices with coverage metadata and ownership.

### Q1: Implementation
database/indexing/level0_builder.py::Level0Builder.build
database/indexing/level1_builder.py::Level1Builder.build
database/indexing/level2_builder.py::Level2Builder.build
database/scripts/build_faiss_manifest.py::main

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level0_index.py::test_level0_build_creates_indices
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Versioned index artifacts | PARTIAL | PARTIAL
Coverage metadata | PARTIAL | PARTIAL
Ownership metadata | NOT_FOUND | ABSENT

### Q6: Confidence
MEDIUM
Risk: Metadata files exist, but ownership/version governance is not explicit in index builders.
---
## [UNNUMBERED-207] — L0/L1/L2 Versioning Tied to Solver Commits
PRD text: - ✅ L0/L1/L2 indices are versioned and tied to solver commits.

### Q1: Implementation
database/indexing/level0_builder.py::Level0Builder.build
database/indexing/level1_builder.py::Level1Builder.build
database/indexing/level2_builder.py::Level2Builder.build

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level0_prompt_suite.py::test_level0_build_outputs
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
LOW
Risk: L0/L1/L2 separation exists, but explicit solver-commit linkage metadata was not found.
---
## [UNNUMBERED-208] — Index Metadata Includes Source Paths, Build Date, Chunk Policy
PRD text: - ✅ Index metadata includes source paths, build date, and chunking policy.

### Q1: Implementation
database/indexing/level1_builder.py::Level1Builder._save_index
database/indexing/level2_builder.py::Level2Builder._save_index
database/scripts/build_faiss_manifest.py::main

### Q2: DRY
DUPLICATED
If duplicated: database/indexing/level1_builder.py, database/indexing/level2_builder.py

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level1_builder.py::test_level1_content_indexed
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: Source paths and manifest generation time exist, but per-index build date and chunk policy are not consistently encoded in metadata JSON.
---
## [UNNUMBERED-209] — Retrieval Coverage Reported Per Solver for Benchmarks
PRD text: - ✅ Retrieval coverage is reported per solver for benchmarks.

### Q1: Implementation
scripts/aggregate_metrics.py::_group_summary
scripts/aggregate_metrics.py::main
src/benchmark_runner.py::run_model_benchmark

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_benchmark_runner.py::test_jsonl_contains_schema_valid_field
  Integration (real):    tests/integration/test_oracle_benchmarks.py::test_squall_line_jsonl_fields_present
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
MEDIUM
Risk: `by_solver.csv` coverage exists, but retrieval-specific solver coverage granularity depends on upstream event completeness.
---
## [UNNUMBERED-210] — Chunking Policy, No Truncation, Embedding Cache Hits
PRD text: **Required Behavior:** Enforce chunking policy, remove truncation, and record embedding cache hits.

### Q1: Implementation
database/indexing/level2_builder.py::Level2Builder.build
src/services/embedding.py::EmbeddingService.expand_documents
database/scripts/cborg_embeddings.py::CBORGEmbeddings.embed_documents

### Q2: DRY
DUPLICATED
If duplicated: src/services/embedding.py, database/scripts/build_index.py

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level2_index.py::test_level2_no_truncation_amendment_c
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
Phase | Impl | Tests
Chunking policy | YES | PARTIAL
No truncation | YES | YES
Cache hit recording | NOT_FOUND | ABSENT

### Q6: Confidence
MEDIUM
Risk: Chunking and truncation are covered, but benchmark-visible cache-hit accounting is missing.
---
## [UNNUMBERED-211] — No Indexed Source File Truncation
PRD text: - ✅ No file truncation for indexed sources.

### Q1: Implementation
database/indexing/level2_builder.py::Level2Builder.build

### Q2: DRY
DRY

### Q3: Test pyramid
  Unit (mocked deps):    tests/unit/test_level2_index.py::test_level2_no_truncation_amendment_c
  Integration (real):    tests/integration/test_jicf_indexing_strategies.py::test_jicf_prompt_across_indexing_strategies
  Oracle/E2E (pipeline): ABSENT

### Q4: Mock fidelity
NO_UNIT_TEST

### Q5: Phase completeness
N/A

### Q6: Confidence
HIGH
Risk: Level2 path is explicitly tested; other indexing paths still use independent chunk/read logic.
---
## [UNNUMBERED-212] — Chunk Boundaries Align to AMReX Block Headers
PRD text: - ✅ Chunk boundaries align to AMReX block headers.

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
Risk: Current chunking is markdown-section or size-based; no AMReX header-aware boundary parser was found.
---
## [UNNUMBERED-213] — Cache Hit Rate Logged During Benchmarks
PRD text: - ✅ Cache hit rate is logged during benchmarks.

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
Risk: Caching is enabled in embeddings, but no benchmark output field/log computes cache hit rate.
---
## Session complete
Criteria audited: 25
Batch: batch_11
Worktree: wt-2
HEAD: 8668e88784c377917afc099c42ab6117a1be1eec
