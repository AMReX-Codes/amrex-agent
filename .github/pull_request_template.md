## Summary

## Related or overlapping functionality / DRY guidance
- What other functionality overlaps this change, and can it be reused to avoid duplication?
- If adding a non-optional variable or function argument (esp. node updates), how does that align with `src/models/graph_state_canonical.py` and the written node contracts in `tests/contracts`?
- Does this decrease pytest coverage or add tests in `tests/unit` or `tests/integration`?
- [ ] This embeds a significant architectural decision that needs an ADR.
  - If checked, add an ADR under `docs/adr/` (one short file describing context, decision, consequences).

## Impact checklist
- [ ] fixes a bug or incorrect behavior
- [ ] adds new capabilities
- [ ] changes answers in the test suite to more than roundoff level
- [ ] likely affects downstream users or results
- [ ] includes docs updates (code/docs), if appropriate
- [ ] none of the above

## Tests run (CI runs: `pytest tests/unit`, `pytest tests/quality`, `pytest tests/integration -m "integration_l1 or integration_l2 or integration_l3 or integration_l4 or integration_full"`)
- [ ] tests/unit: `pytest tests/unit`
- [ ] tests/quality: `pytest tests/quality`
- [ ] integration ladder (CI): `pytest tests/integration -m "integration_l1 or integration_l2 or integration_l3 or integration_l4 or integration_full"`
- [ ] other (list):
- Output/summary:
- If tests require repos/schemas/indices or real services, note markers used.
- `requires_solver(...)` implies repo + schema + default indices are available locally.
- Use `-k pelec|erf|amrex|warpx` to filter solver-specific tests.

Examples:
```bash
pytest tests/unit --tb=short -q
pytest tests/quality --tb=short -q
pytest tests/integration -m "integration_l1 or integration_l2 or integration_l3 or integration_l4 or integration_full" --tb=short -q
pytest -m "e2e and demo" tests/e2e/test_demo_smoke.py --tb=short -q
```

## Tests not run in CI (required if any)
- CI runs `tests/unit`, `tests/quality`, and `tests/integration` with `integration_l1..l4` + `integration_full` markers via micromamba; list anything else not covered by CI here.
- [ ] None
- [ ] tests/e2e
- [ ] other (list):
- Reason for skip:
- Risk/mitigation:

## API-key/manual tests (optional, include steps)
- Env vars or credentials needed:
- Manual steps/commands:
- Results or logs:

## Integration/E2E markers (optional, manual, may require API key)
- Note: integration ladder runs in CI; `tests/e2e` runs only when selected by path or `-m e2e`.
- [ ] e2e demo (workflow_dispatch): `pytest -m "e2e and demo" tests/e2e/test_demo_smoke.py`
- [ ] other (markers: use_real_services, requires_repos, requires_schema):

## Notes (optional)
- Manual output / logs (short):
- Known limitations:

## Labels (optional)
- [ ] I will check auto-labels after submitting.
- [ ] Labels are okay if slightly off.

## Maintainability note (optional)
- Prefer the most maintainable, DRY, and human-readable option; add duplication only with a clear reason.
