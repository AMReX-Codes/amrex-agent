"""Session 129 tests for UNNUMBERED-236 DRY refactor coverage in plan service."""

from __future__ import annotations

import json

import pytest

from src.services.plan import (
    SimulationPlan,
    SimulationPlanFactory,
    _normalize_case_reference,
    _to_int,
    build_baseline_evidence_citations,
    evaluate_radon_cc_threshold,
    normalize_unnumbered_023,
    normalize_unnumbered_236,
)


def test_to_int_converts_valid_values_and_rejects_invalid_values() -> None:
    assert _to_int(True) is None
    assert _to_int(4) == 4
    assert _to_int(4.0) == 4
    assert _to_int(4.2) is None
    assert _to_int(" 11 ") == 11
    assert _to_int("1a") is None


def test_normalize_unnumbered_236_payload_contract() -> None:
    assert normalize_unnumbered_236() == {"valid": True, "error": None, "offenders": []}
    assert normalize_unnumbered_236(error="bad", offenders=[{"name": "f", "complexity": 12}]) == {
        "valid": False,
        "error": "bad",
        "offenders": [{"name": "f", "complexity": 12}],
    }
    assert normalize_unnumbered_236(error="bad", offenders="wrong") == {  # type: ignore[arg-type]
        "valid": False,
        "error": "bad",
        "offenders": [],
    }


def test_evaluate_radon_cc_threshold_paths() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        evaluate_radon_cc_threshold(
            radon_available=True,
            flagged_functions=[],
            max_complexity=-1,
        )

    assert evaluate_radon_cc_threshold(radon_available=False, flagged_functions=[]) == {
        "valid": False,
        "error": "radon is not installed",
        "offenders": [],
    }
    assert evaluate_radon_cc_threshold(  # type: ignore[arg-type]
        radon_available=True,
        flagged_functions={"bad": "payload"},
    )["error"] == "radon_cc_functions must be a list of mappings"
    assert evaluate_radon_cc_threshold(
        radon_available=True,
        flagged_functions=[123],  # type: ignore[list-item]
    )["error"] == "radon_cc_functions entries must be mappings"

    ok = evaluate_radon_cc_threshold(
        radon_available=True,
        flagged_functions=[
            {"name": "good-int", "complexity": 10},
            {"name": "good-float-int", "complexity": 9.0},
            {"name": "skip-bool", "complexity": True},
            {"name": "skip-float", "complexity": 3.2},
            {"name": "skip-text", "complexity": "abc"},
        ],
    )
    assert ok == {"valid": True, "error": None, "offenders": []}

    bad = evaluate_radon_cc_threshold(
        radon_available=True,
        flagged_functions=[{"name": "too-complex", "complexity": 11}],
    )
    assert bad == {
        "valid": False,
        "error": "functions exceed complexity threshold",
        "offenders": [{"name": "too-complex", "complexity": 11}],
    }


def test_normalize_unnumbered_023_supports_tuple_list_dict_and_rejects_others() -> None:
    assert normalize_unnumbered_023(None) == []
    assert normalize_unnumbered_023("bad") == []
    assert normalize_unnumbered_023(
        [
            ("a", "1"),
            ["b", "2"],
            {"parameter": "c", "value": "3"},
            {"other": "missing-keys"},
            "ignore",
        ]
    ) == [("a", "1"), ("b", "2"), ("c", "3"), ("", "")]


def test_case_reference_normalization_and_citations() -> None:
    assert _normalize_case_reference("  Exec/Case ") == "Exec/Case"
    assert _normalize_case_reference("   ") is None
    assert _normalize_case_reference({"case": "Exec/A"}) == "Exec/A"
    assert _normalize_case_reference({"repo_path": "Exec/B"}) == "Exec/B"
    assert _normalize_case_reference({"name": "CaseName"}) == "CaseName"
    assert _normalize_case_reference({"x": "y"}) is None
    assert _normalize_case_reference(3) is None

    citations = build_baseline_evidence_citations(
        baseline_case={"case": "Exec/Base"},
        similar_cases=["Exec/S1", "Exec/S1", {"repo_path": "Exec/S2"}, "   ", 1],
    )
    assert citations == [
        {"citation_type": "baseline", "case": "Exec/Base"},
        {"citation_type": "similar_case", "case": "Exec/S1"},
        {"citation_type": "similar_case", "case": "Exec/S2"},
    ]
    assert build_baseline_evidence_citations({"metadata": {"repo_path": "Exec/Base2"}}, "bad") == [
        {"citation_type": "baseline", "case": "Exec/Base2"}
    ]


def test_simulation_plan_instance_helpers() -> None:
    plan = SimulationPlan(
        selected_solver="PeleC",
        selected_case="Exec/Flame",
        modifications=[("a", "1")],
        reasoning="x" * 220,
        solver_confidence=1.0,
        baseline_confidence=0.5,
        cbr_confidence=0.0,
    )
    as_dict = plan.to_dict()
    assert as_dict["selected_solver"] == "PeleC"
    assert json.loads(plan.to_json())["selected_case"] == "Exec/Flame"
    assert plan.get_overall_confidence() == pytest.approx(0.45)
    assert "..." in plan.get_summary()


def test_create_from_rag_requires_baseline_result() -> None:
    with pytest.raises(ValueError, match="baseline_result is required"):
        SimulationPlanFactory.create_from_rag(
            solver_name="PeleC",
            baseline_result={},
            cbr_plan={},
            docs=[],
            user_prompt="prompt",
        )


def test_create_from_rag_normalizes_modifications_and_reasoning_with_fallbacks() -> None:
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={
            "selected_case": {
                "metadata": {"repo_path": "Exec/Fallback"},
                "case": "Exec/Main",
            },
            "confidence": 0.9,
            "candidates": [{"case": "Exec/Main"}],
        },
        cbr_plan={
            "modifications": [["a", "1"], {"parameter": "b", "value": "2"}],
            "confidence": 0.7,
            "similar_cases": ["Exec/Similar1", "Exec/Similar2"],
        },
        docs=[{"id": "doc1"}],
        user_prompt="run this",
        solver_confidence=0.8,
        used_llm=True,
    )
    assert plan.selected_case == "Exec/Main"
    assert plan.modifications == [("a", "1"), ("b", "2")]
    assert "CBR plan based on Exec/Main" in plan.reasoning
    assert plan.baseline_evidence_citations
    assert plan.used_llm is True
    assert plan.indexing_strategy == "hierarchical"

    fallback_case = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={"selected_case": {"metadata": {"repo_path": "Exec/OnlyMetadata"}}},
        cbr_plan={"modifications": []},
        docs=[],
        user_prompt="x",
    )
    assert fallback_case.selected_case == "Exec/OnlyMetadata"


def test_create_from_simple_paths() -> None:
    with pytest.raises(ValueError, match="missing solver"):
        SimulationPlanFactory.create_from_simple(
            requirements={},
            baseline={},
            modifications=[],
            visualization={},
            analysis={},
            user_prompt="prompt",
        )

    plan = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "AMReX"},
        baseline={
            "case_dir": "Exec/Simple",
            "name": "simple-case",
            "match_rationale": "Close match.",
            "total_score": 0.95,
        },
        modifications=[("amr.n_cell", "64")],
        visualization={"v": 1},
        analysis={"a": 1},
        user_prompt="prompt",
    )
    assert plan.selected_solver == "AMReX"
    assert plan.selected_case == "Exec/Simple"
    assert "Close match." in plan.reasoning
    assert plan.baseline_confidence == 0.95
    assert plan.cbr_confidence == 1.0


def test_from_dict_handles_current_and_legacy_formats() -> None:
    current = SimulationPlanFactory.from_dict(
        {
            "selected_solver": "PeleC",
            "selected_case": "Exec/Flame",
            "modifications": [["a", "1"], {"parameter": "b", "value": "2"}],
            "reasoning": "ok",
            "unknown": "ignored",
        }
    )
    assert current.modifications == [("a", "1"), ("b", "2")]
    assert not hasattr(current, "unknown")

    migrated = SimulationPlanFactory.from_dict(
        {
            "solver": "PeleC",
            "baseline": {"path": "Exec/Legacy", "code": "PeleC"},
            "modifications": [{"parameter": "x", "value": "9"}],
            "used_llm": True,
        }
    )
    assert migrated.selected_solver == "PeleC"
    assert migrated.selected_case == "Exec/Legacy"
    assert migrated.modifications == [("x", "9")]
    assert migrated.reasoning == "Legacy plan"
    assert migrated.used_llm is True


def test_migrate_legacy_dict_fallbacks_and_validation() -> None:
    with pytest.raises(ValueError, match="missing solver/selected_solver"):
        SimulationPlanFactory._migrate_legacy_dict({})

    migrated = SimulationPlanFactory._migrate_legacy_dict(
        {
            "selected_solver": "AMReX",
            "baseline": {"case_dir": "Exec/CaseDir"},
            "modifications": None,
        }
    )
    assert migrated["selected_case"] == "Exec/CaseDir"
    assert migrated["modifications"] == []
    assert migrated["indexing_strategy"] == "simple"
