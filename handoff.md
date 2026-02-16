# Handoff: Parity Indexing Strategies

Branch: wt-parity-indexing-strategies
Focus: Ensure JICF example works across indexing strategies.

Goals
1) Add pytest coverage for simple vs hierarchical vs override_static.
2) Verify behavior is consistent for JICF flows.
3) Capture any strategy-specific failures.

Context
- Indexing strategy controls routing in ArchitectService.
- JICF demo lives in demo/pelelmex.

Key Files
- src/services/architect.py
- demo/pelelmex/README.md
- tests/integration (new tests)
- tests/conftest.py (markers)

Planned Changes
- Add parameterized pytest test for each strategy.
- Reuse JICF prompt or baseline override.
- Mark tests with requires_indices/requires_schema.

Open Questions
- Should override_static require explicit baseline path in tests?
- Which strategy is canonical for JICF demo?

Risks
- Hierarchical strategy depends on L0/L1/L2 indices.
- Tests may be too slow for CI without gating.

Next Steps
- Create a minimal test prompt for JICF.
- Implement strategy markers in pytest.
- Document how to run each strategy test.

Notes
- Keep tests deterministic (fixed baseline where possible).
