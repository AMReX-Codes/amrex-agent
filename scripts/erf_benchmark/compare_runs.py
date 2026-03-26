#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import statistics
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


def _read_csv_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _category_variance(category_rows: list[dict[str, str]]) -> float:
    per_cat: dict[str, list[float]] = {}
    for row in category_rows:
        try:
            score = float(row.get("weighted_score", "0") or 0.0)
        except ValueError:
            score = 0.0
        per_cat.setdefault(row.get("category", ""), []).append(score)
    vals = [sum(scores) / len(scores) for key, scores in per_cat.items() if key and scores]
    return round(statistics.pvariance(vals), 6) if len(vals) > 1 else 0.0


def _catastrophic_miss_count(failure_rows: list[dict[str, str]]) -> int:
    return len({(row.get("strategy", ""), row.get("row_id", "")) for row in failure_rows if row.get("row_id")})


def build_tiebreak_metrics(
    summary: dict[str, Any],
    category_rows: list[dict[str, str]],
    failure_rows: list[dict[str, str]],
) -> dict[str, Any]:
    mean_holdout = (
        float(summary.get("simple_weighted_score", 0.0)) + float(summary.get("hierarchical_weighted_score", 0.0))
    ) / 2.0
    return {
        "mean_holdout_weighted_score": round(mean_holdout, 6),
        "category_variance": _category_variance(category_rows),
        "catastrophic_misses": _catastrophic_miss_count(failure_rows),
    }


def select_better_candidate(baseline_metrics: dict[str, Any], candidate_metrics: dict[str, Any]) -> str:
    left = candidate_metrics
    right = baseline_metrics
    if left["mean_holdout_weighted_score"] != right["mean_holdout_weighted_score"]:
        return "candidate" if left["mean_holdout_weighted_score"] > right["mean_holdout_weighted_score"] else "baseline"
    if left["category_variance"] != right["category_variance"]:
        return "candidate" if left["category_variance"] < right["category_variance"] else "baseline"
    if left["catastrophic_misses"] != right["catastrophic_misses"]:
        return "candidate" if left["catastrophic_misses"] < right["catastrophic_misses"] else "baseline"
    return "tie"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare ERF benchmark baseline vs candidate runs.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline-category-report", type=Path, default=None)
    parser.add_argument("--candidate-category-report", type=Path, default=None)
    parser.add_argument("--baseline-failures", type=Path, default=None)
    parser.add_argument("--candidate-failures", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("benchmark/erf_llm_compare/runs/compare_summary.json"))
    args = parser.parse_args()

    baseline_summary = _read_json(args.baseline)
    candidate_summary = _read_json(args.candidate)
    verdict = evaluate_candidate_vs_baseline(baseline_summary, candidate_summary)
    baseline_metrics = build_tiebreak_metrics(
        baseline_summary,
        _read_csv_rows(args.baseline_category_report),
        _read_csv_rows(args.baseline_failures),
    )
    candidate_metrics = build_tiebreak_metrics(
        candidate_summary,
        _read_csv_rows(args.candidate_category_report),
        _read_csv_rows(args.candidate_failures),
    )
    verdict["tiebreak"] = {
        "baseline": baseline_metrics,
        "candidate": candidate_metrics,
        "better": select_better_candidate(baseline_metrics, candidate_metrics),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print(f"accepted={verdict['accepted']}")
    return 0 if verdict["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
