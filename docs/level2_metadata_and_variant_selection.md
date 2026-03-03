# Level-2 Metadata and Variant Selection

## Context
This note captures why baseline case selection can drift toward variants like `Exec/Upwelling_ML` instead of canonical starter cases like `Exec/Upwelling`, and what was changed to stabilize behavior.

## Observed behavior
For prompts such as:
- `Run wind-driven upwelling over a periodic channel.`

the system selected:
- solver: `REMORA` (correct)
- baseline: `Exec/Upwelling_ML` (sometimes undesired)

This is a **Level-2 baseline ranking** effect, not an Input Writer file-choice effect.

## Why this happens (Level-2 metadata effects)
Baseline ranking uses weighted semantic/metadata scoring from Level-2 indices. If a variant case has richer or more directly aligned metadata tokens, it can outrank the canonical case even when both are valid.

Important distinction:
- Level-2 chooses the **case directory**.
- Input Writer "newest" chooses an **inputs file inside the chosen case**.

So selecting `Upwelling_ML` happens before Input Writer logic.

## Change implemented
A small, explicit tie-breaker was added in baseline selection:
- file: `src/services/architect.py`
- method: `_apply_priority_case_boost`
- behavior:
  - exact priority-case path match: `+0.08`
  - prefix/suffix path match: `+0.04`

This keeps semantic ranking primary, but nudges selection toward configured canonical priority cases when scores are close.

Additional test coverage:
- `tests/unit/test_architect_baseline_selection.py`
- `TestPriorityCaseBoost::test_priority_case_boost_prefers_canonical_case`

## Practical implication
If `priority_cases` includes `Exec/Upwelling`, a near-tie where `Exec/Upwelling_ML` is only marginally higher can be flipped to `Exec/Upwelling`.

## Long-term better solution
The current boost is a pragmatic fix. Longer-term, selection quality should improve by modeling case maturity/variant intent directly rather than relying on post-score nudges.

Recommended options:
1. Add Level-2 metadata fields (or config schema) for:
   - development stage (production, experimental, research, ml-prototype)
   - variant type (canonical, tutorial, extended, ml-augmented)
   - recommended_for_initial_runs (bool)
2. Add an LLM reranking step over top-K Level-2 candidates that explicitly reasons about user intent vs variant maturity.
3. Combine both:
   - deterministic metadata gating first
   - LLM rerank only when confidence margin is small

## Rebuild/validation notes
After metadata/indexing changes, rebuild indices to avoid stale behavior:
- `python database/scripts/build_all_indices.py --level 0 --output database/faiss`

Validation commands:
- `pytest tests/unit`
- `python amrex_agent.py --indexing-strategy hierarchical --prompt "Run wind-driven upwelling over a periodic channel."`

## Current status
- Priority-case booster implemented and tested.
- Full unit suite pass at last run: `640 passed, 26 skipped, 3 warnings`.
