# Handoff: REMORA Hierarchical Support

## Branch / Commit
- Branch: `remora_hierarchical_support`
- Base commit with Level-0 refactor + prompt suite: `c82dcd0`

## What is implemented
- Level-0 solver routing refactor to config-driven metadata:
  - `database/configs/base_amrex_config.py`
  - solver-specific metadata in config files (`amrex`, `pelec`, `pelelmex`, `incflo`, `erf`, `remora`, `warpx`)
  - `database/indexing/level0_builder.py` uses strict category sources
- REMORA/ERF alignment updates:
  - REMORA lineage/guidance updated to reflect ERF setup relationship
  - ERF capability summary expanded from actual `ERF/Exec/*` case coverage
- Deterministic prompt suite and A/B tooling:
  - `tests/data/level0_ab_prompts.json`
  - `tests/unit/test_level0_prompt_suite.py`
  - `scripts/eval_level0_ab.py`
- Baseline selection tie-breaker boost for configured priority cases:
  - `src/services/architect.py` (`_apply_priority_case_boost`)
  - favors canonical cases like `Exec/Upwelling` when scores are close
  - adds `score_raw` and `score_bonus` fields on boosted candidates

## Why `Upwelling_ML` was selected
- Baseline selection is Level-2 weighted semantic ranking, not Input Writer "newest" logic.
- Input Writer "newest" only selects inputs file **within** an already selected case.
- `Upwelling_ML` can outrank due to richer metadata embeddings unless priority-case boosting is applied.

## Required operator step after code changes
- Rebuild active Level-0 FAISS indices, or stale artifacts will keep old routing behavior:
  - `python database/scripts/build_all_indices.py --level 0 --output database/faiss`

## Tests run
- `pytest tests/unit`
- Result at time of run: `640 passed, 26 skipped, 3 warnings`

## Suggested next validation
1. Rebuild Level-0 indices as above.
2. Re-run:
   - `python amrex_agent.py --indexing-strategy hierarchical --prompt "Run wind-driven upwelling over a periodic channel."`
3. Confirm solver is `REMORA` and baseline favors `Exec/Upwelling` over `Exec/Upwelling_ML` when scores are close.
