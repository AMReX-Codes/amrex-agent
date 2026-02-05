# AMReXAgent Test Suite

This directory contains unit, integration, and quality tests for the AMReXAgent.
Tests are organized by intent and are auto-marked by path.

## Structure

- `tests/unit`: Fast tests with isolated dependencies or mocks.
- `tests/integration`: Multi-component tests across the workflow ladder.
- `tests/quality`: Style and metadata consistency checks.

## Markers

Markers are registered in `pyproject.toml`. Auto-marking by path:
- `tests/unit` → `@pytest.mark.unit`
- `tests/integration` → `@pytest.mark.integration`
- `tests/quality` → `@pytest.mark.quality`
`tests/e2e` is opt-in and only runs when selected by path or `-m e2e`.
Resource markers:
- `requires_solver("PeleC")` names the solver/code a test targets.
- `requires_repos("PeleC")` and `requires_schema("PeleC")` gate tests on local assets.
- `requires_indices("faiss" | "level0" | "level1" | "level2")` gate tests on index files.
- `use_real_services` or `use_mock_services` describes service dependencies.
`requires_solver(...)` bundles repo + schema + default index checks (hierarchical if `indexing_hierarchical`, otherwise `faiss`).

Additional markers exist for integration ladder levels and components; keep them
consistent with `pyproject.toml`.

## Selection Shortcuts

Custom flags are provided in `tests/conftest.py`:
```bash
pytest --unit
pytest --integration
pytest --quality
```

You can also run by marker or path:
```bash
pytest -m unit
pytest tests/integration -m "not slow"
pytest tests/quality
pytest tests/e2e -m e2e -k pelec
```

## Coverage

Coverage defaults are configured in `pyproject.toml`. For local runs:
```bash
pytest --unit --cov --cov-report=term-missing
```

## Coverage Planning

Current coverage planning lives in `docs/coverage_map.md`. It links:
- PRD/Amendments → unit tests
- Canonical graph state → test fixtures
- Node contract fixtures → unit test assertions

When adding unit tests, prefer fixtures that mirror the contract shapes in
`tests/contracts` and the fields defined in
`src/models/graph_state_canonical.py`.

## README Command Parity Policy

When editing `README.md` or other docs with bash command blocks:
- Keep commands and flags in sync with the current CLI behavior.
- If a command changes, update the README and note the verification in the PR
  template "Tests run" section.
- Prefer commands that are runnable on a clean checkout (call out any required
  env vars or API keys).

## Contributing

- Add new tests under the correct directory.
- Use markers for ladder levels or components as needed.
- Keep tests deterministic and avoid external network calls.
