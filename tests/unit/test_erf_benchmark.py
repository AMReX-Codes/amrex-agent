from __future__ import annotations

import json
from pathlib import Path

from scripts.erf_benchmark.compare_runs import evaluate_candidate_vs_baseline
from scripts.erf_benchmark.generate_prompt_matrix import build_prompt_matrix_rows
from scripts.erf_benchmark.make_splits import build_splits
from scripts.erf_benchmark.run_llm_compare_benchmark import (
    detect_llm_unavailable,
    score_rows,
)


def test_build_prompt_matrix_rows_is_deterministic() -> None:
    paths = [
        Path("Exec/RegTests/Bubble/inputs"),
        Path("Exec/RegTests/Bubble/inputs_abl"),
    ]
    rows_a = build_prompt_matrix_rows(paths)
    rows_b = build_prompt_matrix_rows(paths)
    assert rows_a == rows_b
    assert rows_a[0]["wave_id"] == "wave0"
    assert rows_a[-1]["wave_id"] == "wave2"


def test_build_splits_reproducible_and_disjoint() -> None:
    row_ids = [f"r{i:03d}" for i in range(20)]
    split_a = build_splits(row_ids, seed=7, holdout_ratio=0.2, paraphrase_ratio=0.3)
    split_b = build_splits(row_ids, seed=7, holdout_ratio=0.2, paraphrase_ratio=0.3)
    assert split_a == split_b
    assert set(split_a["train_ids"]).isdisjoint(set(split_a["holdout_ids"]))
    assert set(split_a["holdout_paraphrase_ids"]).issubset(set(split_a["holdout_ids"]))


def test_score_rows_applies_weighted_rule() -> None:
    rows = [
        {"row_id": "a", "target_case_relpath": "Exec/A", "target_inputs_relpath": "Exec/A/inputs"},
        {"row_id": "b", "target_case_relpath": "Exec/B", "target_inputs_relpath": "Exec/B/inputs"},
    ]
    predictions = {
        "a": {"selected_case": "Exec/A", "selected_inputs": "Exec/A/inputs"},
        "b": {"selected_case": "Exec/B", "selected_inputs": "Exec/other/inputs"},
    }
    scored = score_rows(rows, predictions)
    assert scored["case_accuracy"] == 1.0
    assert scored["inputs_accuracy"] == 0.5
    assert scored["weighted_score"] == 0.85


def test_detect_llm_unavailable_from_metrics_and_summary() -> None:
    metrics = [
        {"type": "retrieval_strategy", "data": {"fallback_reason": "llm_unavailable"}},
    ]
    payload = {"stages": {"input_writer": {"retrieval": {"last": {"fallback_reason": None}}}}}
    assert detect_llm_unavailable(metrics_events=metrics, workflow_summary=payload) is True
    assert detect_llm_unavailable(metrics_events=[], workflow_summary=payload) is False


def test_compare_runs_acceptance_logic() -> None:
    baseline = {
        "holdout_weighted_score": 0.91,
        "simple_weighted_score": 0.92,
        "hierarchical_weighted_score": 0.93,
        "paraphrase_weighted_score": 0.90,
        "category_min_weighted_score": 0.80,
        "non_erf_sanity_weighted_score": 0.88,
    }
    candidate = dict(baseline)
    candidate["holdout_weighted_score"] = 0.92
    verdict = evaluate_candidate_vs_baseline(baseline, candidate)
    assert verdict["accepted"] is True
    assert verdict["checks"]["strategy_threshold"] is True

    candidate_bad = dict(candidate)
    candidate_bad["category_min_weighted_score"] = 0.70
    verdict_bad = evaluate_candidate_vs_baseline(baseline, candidate_bad)
    assert verdict_bad["accepted"] is False
    assert verdict_bad["checks"]["category_guardrail"] is False

