# Coverage Map

This document ties unit-test coverage to the intended design (PRD/Amendments),
canonical graph state, and contract fixtures. Use it to keep test additions
aligned with end-to-end simulation goals.

## Canonical references

- Graph state schema: `src/models/graph_state_canonical.py`
- Node contracts:
  - `tests/contracts/architect_node_contract.json`
  - `tests/contracts/input_writer_node_contract.json`
  - `tests/contracts/reviewer_node_contract.json`
  - `tests/contracts/runner_node_contract.json`

## Coverage principles

- Unit tests should assert outputs compatible with the node contracts above.
- Use the graph-state canonical fields as the source of truth for new fixtures.
- Keep unit tests deterministic; reserve multi-component behavior for
  integration/e2e worktrees.

## Worktree split (unit coverage focus)

1) `wt-coverage-config-rules`
   - Targets: `src/services/config_model_factory.py`,
     `src/services/validators/*`, `src/services/rule_engine.py`,
     `src/services/rules/*`
   - Contract anchors: `tests/contracts/reviewer_node_contract.json`
   - Graph-state anchors: validation fields in `graph_state_canonical.py`

2) `wt-coverage-inputs-pipeline`
   - Targets: `src/services/input_writer.py`,
     `src/services/inputs_file_selector.py`, `src/services/file_generation.py`
   - Contract anchors: `tests/contracts/input_writer_node_contract.json`
   - Graph-state anchors: inputs/baseline fields in `graph_state_canonical.py`

3) `wt-coverage-execution-stack`
   - Targets: `src/services/run_local.py`, `src/services/run_superfacility.py`,
     `src/services/execution_tools.py`
   - Contract anchors: `tests/contracts/runner_node_contract.json`
   - Graph-state anchors: runner status fields in `graph_state_canonical.py`

Optional add-ons if needed:
- `wt-coverage-architect-core` (planner/baseline selection)
- `wt-coverage-indexing-search` (Level0/1/2 indexing/search)

## Mapping template for new tests

When adding tests, note in the test docstring:
- PRD or Amendment reference (if applicable)
- Contract fixture used
- Graph-state field(s) asserted

Example:
"""
PRD FR-5 / Amendment C
Contract: tests/contracts/input_writer_node_contract.json
Graph state: graph_state_canonical.inputs_content
"""

## UNNUMBERED-023: Use Case to Artifact Mapping

Contract:
- Every new oracle gate use case has exactly one validation artifact.
- Every validation artifact maps to exactly one use case.
- Artifact format is `tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[<use_case_id>]`.

| use_case_id | validation_artifact |
|---|---|
| oracle_easy_amrex_advection_amrcore | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_easy_amrex_advection_amrcore] |
| oracle_easy_pelec_pmf | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_easy_pelec_pmf] |
| oracle_easy_pelelmex_flamesheet | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_easy_pelelmex_flamesheet] |
| oracle_easy_erf_bubble | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_easy_erf_bubble] |
| oracle_easy_remora_seamount | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_easy_remora_seamount] |
| oracle_easy_remora_upwelling | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_easy_remora_upwelling] |
| oracle_easy_pelec_sedov | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_easy_pelec_sedov] |
| oracle_easy_erf_squallline_2d | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_easy_erf_squallline_2d] |
| oracle_medium_erf_densitycurrent | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_medium_erf_densitycurrent] |
| oracle_medium_erf_abl | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_medium_erf_abl] |
| oracle_medium_pelec_tg | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_medium_pelec_tg] |
| oracle_medium_pelelmex_taylorgreen | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_medium_pelelmex_taylorgreen] |
| oracle_medium_pelelmex_counterflow | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_medium_pelelmex_counterflow] |
| oracle_medium_remora_doublegyre | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_medium_remora_doublegyre] |
| oracle_medium_remora_channel_test | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_medium_remora_channel_test] |
| oracle_medium_remora_doublyperiodic | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_medium_remora_doublyperiodic] |
| oracle_hard_pelec_jetflame_conflict | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_hard_pelec_jetflame_conflict] |
| oracle_hard_pelelmex_jetincrossflow | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_hard_pelelmex_jetincrossflow] |
| oracle_hard_incflo_benchmark_godunov | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_hard_incflo_benchmark_godunov] |
| oracle_hard_warpx_laser_acceleration | tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[oracle_hard_warpx_laser_acceleration] |
