#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate_candidate_vs_baseline(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    strategy_threshold: float = 0.90,
    category_floor: float = 0.75,
    sanity_regression_tolerance: float = 0.03,
) -> dict[str, Any]:
    checks = {
        "holdout_non_regression": candidate.get("holdout_weighted_score", 0.0) >= baseline.get("holdout_weighted_score", 0.0),
        "strategy_threshold": candidate.get("simple_weighted_score", 0.0) >= strategy_threshold
        and candidate.get("hierarchical_weighted_score", 0.0) >= strategy_threshold,
        "paraphrase_non_regression": candidate.get("paraphrase_weighted_score", 0.0) >= baseline.get("paraphrase_weighted_score", 0.0),
        "category_guardrail": candidate.get("category_min_weighted_score", 0.0) >= category_floor,
        "non_erf_sanity_tolerance": candidate.get("non_erf_sanity_weighted_score", 0.0)
        >= (baseline.get("non_erf_sanity_weighted_score", 0.0) - sanity_regression_tolerance),
    }
    return {"accepted": all(checks.values()), "checks": checks}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare ERF benchmark baseline vs candidate runs.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("benchmark/erf_llm_compare/runs/compare_summary.json"))
    args = parser.parse_args()

    verdict = evaluate_candidate_vs_baseline(_read_json(args.baseline), _read_json(args.candidate))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print(f"accepted={verdict['accepted']}")
    return 0 if verdict["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

