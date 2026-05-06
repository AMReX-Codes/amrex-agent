from __future__ import annotations

import json
from pathlib import Path

from scripts.erf_benchmark.compare_runs import (
    build_tiebreak_metrics,
    evaluate_candidate_vs_baseline,
    select_better_candidate,
)
from scripts.erf_benchmark.lib.explainability_scoring import (
    build_call_records,
    summarize_explainability,
)
from scripts.erf_benchmark.generate_prompt_matrix import build_prompt_matrix_rows
from scripts.erf_benchmark.make_splits import build_splits
from scripts.erf_benchmark.run_llm_compare_benchmark import (
    extract_case_reselection_fallback,
    extract_iteration1_case,
    detect_llm_unavailable,
    extract_selected_case,
    extract_selected_inputs,
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


def test_build_prompt_matrix_rows_with_physics_waves_uses_catalog_metadata() -> None:
    paths = [Path("Exec/CanonicalFlows/SquallLine_2D/inputs_ml")]
    catalog = {
        ("Exec/CanonicalFlows/SquallLine_2D", "inputs_ml"): {
            "case_name": "SquallLine_2D",
            "description": "2D squall line benchmark with moist dynamics.",
            "physics": ["moist", "atmosphere", "convection"],
            "difficulty_tier": "hard",
            "prompt_length_band": "long",
            "concept_density": "high",
            "specialized_knowledge": True,
            "novelty_tier": "config-extension",
        }
    }
    rows = build_prompt_matrix_rows(
        paths,
        wave_ids=("wave_phys0", "wave_phys1", "wave_phys2", "wave_phys3"),
        case_catalog=catalog,
    )
    assert [row["wave_id"] for row in rows] == ["wave_phys0", "wave_phys1", "wave_phys2", "wave_phys3"]
    assert rows[-1]["difficulty_tier"] == "hard"
    assert rows[-1]["concept_density"] == "high"
    assert "Prompt complexity target: long." in rows[-1]["prompt_text"]


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


def test_score_rows_normalizes_absolute_paths() -> None:
    rows = [
        {
            "row_id": "a",
            "target_case_relpath": "Exec/ABL/MOST_test_suite",
            "target_inputs_relpath": "Exec/ABL/MOST_test_suite/inputs_anel_most",
        }
    ]
    predictions = {
        "a": {
            "selected_case": "/home/user/ERF/Exec/ABL/MOST_test_suite/inputs_anel_most",
            "selected_inputs": "/home/user/ERF/Exec/ABL/MOST_test_suite/inputs_anel_most",
        }
    }
    scored = score_rows(rows, predictions)
    assert scored["case_accuracy"] == 1.0
    assert scored["inputs_accuracy"] == 1.0
    assert scored["weighted_score"] == 1.0


def test_score_rows_supports_prefix_expectations() -> None:
    rows = [
        {
            "row_id": "a",
            "expected_case_prefix": "Exec/CanonicalFlows/SquallLine_2D",
            "expected_inputs_prefix": "Exec/CanonicalFlows/SquallLine_2D/inputs",
        }
    ]
    predictions = {
        "a": {
            "selected_case": "Exec/CanonicalFlows/SquallLine_2D",
            "selected_inputs": "Exec/CanonicalFlows/SquallLine_2D/inputs_moisture_SAM",
        }
    }
    scored = score_rows(rows, predictions)
    assert scored["case_accuracy"] == 1.0
    assert scored["inputs_accuracy"] == 1.0


def test_detect_llm_unavailable_from_metrics_and_summary() -> None:
    metrics = [
        {"type": "retrieval_strategy", "data": {"fallback_reason": "llm_unavailable"}},
    ]
    payload = {"stages": {"input_writer": {"retrieval": {"last": {"fallback_reason": None}}}}}
    assert detect_llm_unavailable(metrics_events=metrics, workflow_summary=payload) is True
    assert detect_llm_unavailable(metrics_events=[], workflow_summary=payload) is False


def test_detect_llm_unavailable_from_workflow_payload_history() -> None:
    payload = {
        "workflow_history": [
            {
                "details": {
                    "metrics": {
                        "retrieval": {
                            "last": {
                                "fallback_reason": "llm_unavailable",
                            }
                        }
                    }
                }
            }
        ]
    }
    assert detect_llm_unavailable(metrics_events=[], workflow_payload=payload) is True


def test_extract_selected_values_from_workflow_history() -> None:
    payload = {
        "workflow_history": [
            {
                "details": {
                    "selected_case": "/tmp/ERF/Exec/Wave/CaseA",
                    "inputs_file_selected": "/tmp/ERF/Exec/Wave/CaseA/inputs_base",
                }
            }
        ]
    }
    assert extract_selected_case(payload) == "Exec/Wave/CaseA"
    assert extract_selected_inputs(payload) == "Exec/Wave/CaseA/inputs_base"


def test_extract_iteration1_case_prefers_explicit_field() -> None:
    payload = {
        "iteration1_case": "/tmp/PeleLMeX/Exec/Plasma/FlameSheetIons",
        "workflow_history": [
            {"node": "architect", "details": {"selected_case": "Exec/Plasma/PremBunsen3DKuhl"}}
        ],
    }
    assert extract_iteration1_case(payload) == "Exec/Plasma/FlameSheetIons"


def test_extract_iteration1_case_falls_back_to_first_architect_entry() -> None:
    payload = {
        "workflow_history": [
            {"node": "reviewer", "details": {}},
            {"node": "architect", "details": {"selected_case": "/repo/Exec/Plasma/IonizedAirWave"}},
            {"node": "architect", "details": {"selected_case": "Exec/Plasma/PremBunsen3DKuhl"}},
        ]
    }
    assert extract_iteration1_case(payload) == "Exec/Plasma/IonizedAirWave"


def test_extract_case_reselection_fallback_checks_payload_then_history() -> None:
    payload_top = {"case_reselection_fallback": True}
    assert extract_case_reselection_fallback(payload_top) is True

    payload_history = {
        "workflow_history": [
            {"node": "architect", "details": {"case_reselection_fallback": False}},
            {"node": "architect", "details": {"case_reselection_fallback": True}},
        ]
    }
    assert extract_case_reselection_fallback(payload_history) is True


def test_compare_runs_acceptance_logic() -> None:
    baseline = {
        "holdout_weighted_score": 0.91,
        "simple_weighted_score": 0.92,
        "hierarchical_weighted_score": 0.93,
        "paraphrase_weighted_score": 0.90,
        "category_min_weighted_score": 0.80,
        "non_erf_sanity_weighted_score": 0.88,
        "explainability_pass": True,
        "explainability_mean_score": 0.95,
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

    candidate_explain_bad = dict(candidate)
    candidate_explain_bad["explainability_pass"] = False
    verdict_explain_bad = evaluate_candidate_vs_baseline(baseline, candidate_explain_bad)
    assert verdict_explain_bad["accepted"] is False
    assert verdict_explain_bad["checks"]["explainability_gate"] is False


def test_compare_runs_tiebreak_prefers_lower_variance_then_misses() -> None:
    baseline_metrics = build_tiebreak_metrics(
        {"simple_weighted_score": 0.90, "hierarchical_weighted_score": 0.92},
        [
            {"strategy": "simple", "category": "A", "weighted_score": "0.9"},
            {"strategy": "hierarchical", "category": "A", "weighted_score": "0.9"},
            {"strategy": "simple", "category": "B", "weighted_score": "0.7"},
            {"strategy": "hierarchical", "category": "B", "weighted_score": "0.7"},
        ],
        [{"strategy": "simple", "row_id": "x"}],
    )
    candidate_metrics = build_tiebreak_metrics(
        {"simple_weighted_score": 0.90, "hierarchical_weighted_score": 0.92},
        [
            {"strategy": "simple", "category": "A", "weighted_score": "0.8"},
            {"strategy": "hierarchical", "category": "A", "weighted_score": "0.8"},
            {"strategy": "simple", "category": "B", "weighted_score": "0.8"},
            {"strategy": "hierarchical", "category": "B", "weighted_score": "0.8"},
        ],
        [],
    )
    assert select_better_candidate(baseline_metrics, candidate_metrics) == "candidate"


def test_explainability_records_and_summary() -> None:
    row = {
        "row_id": "r1",
        "prompt_text": "Run a 2D squall line simulation",
        "expected_solver": "ERF",
        "expected_case_prefix": "Exec/CanonicalFlows/SquallLine_2D",
        "expected_inputs_prefix": "Exec/CanonicalFlows/SquallLine_2D/inputs",
    }
    payload = {"plan": {"selected_solver": "ERF"}}
    llm_usage_events = [
        {"type": "llm_usage", "stage": "architect", "data": {"model": "m1", "provider": "p1"}},
        {"type": "llm_usage", "stage": "input_writer", "data": {"model": "m1", "provider": "p1"}},
    ]
    records = build_call_records(
        row=row,
        strategy="simple",
        payload=payload,
        llm_usage_events=llm_usage_events,
        selected_case="Exec/CanonicalFlows/SquallLine_2D",
        selected_inputs="Exec/CanonicalFlows/SquallLine_2D/inputs_moisture_SAM",
        row_events=[],
        unavailable=False,
    )
    assert len(records) == 2
    assert records[0]["correctness_score"] == 1.0
    summary = summarize_explainability(records, threshold=0.9)
    assert summary["explainability_pass"] is True
    assert summary["explainability_fail_count"] == 0
