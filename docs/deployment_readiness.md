# Testing, Deployment, and Readiness Plan

This document is a user-facing guide for how to validate the system, deploy it,
and decide if it is ready for release or facility use.

## Scope

- TDD discipline and test pyramid enforcement.
- Deployment prerequisites and verification steps.
- Success criteria mapped to evidence artifacts.
- Release gates and readiness checklist.

## Testing Strategy

### TDD plan (enforcement)

1) Define acceptance checklist before implementation.
2) Write unit tests for rules/validators/router decisions first.
3) Add integration tests for cross-node/service behavior.
4) Update e2e smoke tests for solver-facing changes.
5) For refactors, add characterization tests before edits.

### Test pyramid targets (by count)

- 60-70% unit tests.
- 20-30% integration tests.
- 5-10% e2e tests.

### Coverage requirements

- Unit coverage for new rules/validators.
- Integration coverage for any new node or cross-node behavior.
- E2E smoke coverage for solver-facing changes or demos.

### Required test locations

- Unit: `tests/unit/`
- Integration: `tests/integration/`
- E2E: `tests/e2e/`

### Acceptance criteria

1) Every new feature PR includes unit + integration tests (minimum).
2) Solver-facing change includes an e2e smoke update.
3) CI runs unit/integration on every commit; e2e runs nightly or on release gates.
4) Flaky tests are quarantined within 24 hours and tracked.

### Current gaps

- No explicit acceptance checklist template in repo.
- Limited/unknown coverage mapping for PRD requirements to tests.

## Deployment Plan

### Local (single-user CLI)

Prereqs:
- Python environment per `environment.yaml`.
- Repo cloned with solver paths configured.
- LLM provider keys (CBORG/ALCF) in environment as needed.

Verification steps:
- `python amrex_agent.py --help` succeeds.
- `python amrex_agent.py --prompt "..." --run-mode dry` generates scripts.

### Facility (NERSC/Perlmutter via MCP)

Prereqs:
- `mcp_server.py` deployed via systemd or similar supervisor.
- Shared indices + database path configured.
- SFAPI credentials available for staging/submission when needed.

Verification steps:
- MCP server launches without import errors.
- MCP tool invocation returns expected JSON.
- SFAPI auth test passes (token or client key).

### Benchmark (paper-grade evaluation)

Prereqs:
- Frozen indices and fixed seeds recorded.
- Deterministic model configs.
- Benchmark scripts and output directories created.

Verification steps:
- Benchmark run produces `summary.csv`, `by_model.csv`, `by_solver.csv`,
  `by_strategy.csv`, and `raw_metrics.jsonl`.
- Runs are reproducible from a stored manifest.

## Success Criteria and Evidence

Success criteria should be mapped to measurable artifacts.

| Criterion | Evidence/Artifact | Location |
| --- | --- | --- |
| 20-25 case benchmark runs across target models | Benchmark outputs + manifest | `scripts/` outputs |
| Camera-ready tables reproducible | Aggregated CSV + table scripts | `scripts/generate_paper_tables.py` |
| Demo bundles ready (ERF, REMORA, PeleLMeX) | Demo run dirs + outputs | `demo/` and `output/` |
| Validation catches >=90% injected physics errors | Validator tests + metrics | `tests/` + metrics outputs |

## Release Gates

1) Unit + integration tests pass on every commit.
2) E2E smoke tests pass for solver-facing changes.
3) Deployment verification steps are documented and executed.
4) Success criteria artifacts exist and are linked in release notes.

## Open Questions / To-Do

- Where to store acceptance checklists and mapping tables.
- Which CI workflow runs e2e tests and on what cadence.
- Who owns flaky test quarantine tracking.
