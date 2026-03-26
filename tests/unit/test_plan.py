from __future__ import annotations

from pydantic import ValidationError

from src.services.plan import (
    SimulationPlan,
    SimulationPlanFactory,
    has_checklist_implementation_locations,
)


def test_plan_model_serialization_summary_and_confidence() -> None:
    plan = SimulationPlan(
        selected_solver="PeleLMeX",
        selected_case="Exec/FlameSheet",
        modifications=[("amr.max_level", 2)],
        reasoning="x" * 250,
        solver_confidence=0.9,
        baseline_confidence=0.8,
        cbr_confidence=0.7,
        used_llm=True,
        indexing_strategy="hierarchical",
    )

    as_dict = plan.to_dict()
    assert as_dict["selected_solver"] == "PeleLMeX"

    as_json = plan.to_json(indent=2)
    assert '"selected_case": "Exec/FlameSheet"' in as_json

    assert plan.get_overall_confidence() == 0.2 * 0.9 + 0.5 * 0.8 + 0.3 * 0.7
    summary = plan.get_summary()
    assert "Simulation Plan Summary" in summary
    assert "..." in summary


def test_create_from_rag_requires_baseline_result() -> None:
    try:
        SimulationPlanFactory.create_from_rag(
            solver_name="PeleLMeX",
            baseline_result={},
            cbr_plan={},
            docs=[],
            user_prompt="run",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "baseline_result is required" in str(exc)


def test_create_from_rag_handles_tuple_modifications_and_reasoning() -> None:
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleLMeX",
        baseline_result={
            "selected_case": {
                "case": "Exec/CaseA",
                "metadata": {"repo_path": "Exec/CaseA", "owner": "team"},
            },
            "confidence": 0.88,
            "candidates": [{"case": "Exec/CaseA"}],
        },
        cbr_plan={
            "modifications": [("amr.n_cell", "32 32 32")],
            "confidence": 0.66,
            "reasoning": "explicit reasoning",
        },
        docs=[{"id": "doc-1"}],
        user_prompt="simulate",
        solver_confidence=0.93,
        used_llm=True,
    )

    assert plan.selected_case == "Exec/CaseA"
    assert plan.modifications == [("amr.n_cell", "32 32 32")]
    assert plan.reasoning == "explicit reasoning"
    assert plan.baseline_confidence == 0.88
    assert plan.cbr_confidence == 0.66
    assert plan.used_llm is True
    assert plan.indexing_strategy == "hierarchical"


def test_create_from_rag_converts_dict_modifications_and_builds_reasoning() -> None:
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="IAMR",
        baseline_result={
            "selected_case": {
                "metadata": {"repo_path": "Exec/Default"},
            },
            "confidence": 0.5,
        },
        cbr_plan={
            "modifications": [
                {"parameter": "amr.max_level", "value": 3},
                {"parameter": "plot_int", "value": 10},
            ],
            "similar_cases": ["Case1", "Case2", "Case3", "Case4"],
        },
        docs=[],
        user_prompt="simulate",
    )

    assert plan.modifications == [("amr.max_level", 3), ("plot_int", 10)]
    assert plan.selected_case == "Exec/Default"
    assert plan.reasoning == "CBR plan based on baseline (patterns from: Case1, Case2, Case3)"


def test_create_from_rag_rejects_non_tuple_non_dict_modifications() -> None:
    try:
        SimulationPlanFactory.create_from_rag(
            solver_name="Castro",
            baseline_result={"selected_case": {"case": "Exec/C"}},
            cbr_plan={"modifications": ["raw"], "reasoning": "r"},
            docs=[],
            user_prompt="prompt",
        )
        assert False, "Expected ValidationError"
    except ValidationError:
        assert True


def test_create_from_simple_happy_path_and_optional_reasoning() -> None:
    plan = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "unused"},
        baseline={
            "code": "PeleLMeX",
            "case_dir": "Exec/Flame",
            "name": "Flame",
            "match_rationale": "Best match.",
            "total_score": 0.91,
        },
        modifications=[("amr.max_level", 3)],
        visualization={"plot": True},
        analysis={"enabled": True},
        user_prompt="run",
    )

    assert plan.selected_solver == "PeleLMeX"
    assert plan.selected_case == "Exec/Flame"
    assert "Best match." in plan.reasoning
    assert plan.cbr_confidence == 1.0


def test_create_from_simple_solver_fallbacks_and_defaults() -> None:
    plan = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "IAMR"},
        baseline={"path": "Exec/Fallback", "name": "Fallback", "match_score": 0.6},
        modifications=[],
        visualization={},
        analysis={},
        user_prompt="run",
    )
    assert plan.selected_solver == "IAMR"
    assert plan.selected_case == "Exec/Fallback"
    assert plan.cbr_confidence == 0.0
    assert plan.baseline_confidence == 0.6


def test_create_from_simple_requires_solver() -> None:
    try:
        SimulationPlanFactory.create_from_simple(
            requirements={},
            baseline={},
            modifications=[],
            visualization={},
            analysis={},
            user_prompt="run",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "missing solver" in str(exc)


def test_from_dict_filters_unknown_fields_and_converts_modification_lists() -> None:
    restored = SimulationPlanFactory.from_dict(
        {
            "selected_solver": "PeleC",
            "selected_case": "Exec/Case",
            "modifications": [["plot_int", 20]],
            "reasoning": "ok",
            "unknown": "drop-me",
        }
    )

    assert restored.selected_solver == "PeleC"
    assert restored.modifications == [("plot_int", 20)]
    assert not hasattr(restored, "unknown")


def test_from_dict_migrates_legacy_shape_and_handles_dict_modifications() -> None:
    restored = SimulationPlanFactory.from_dict(
        {
            "solver": "PeleLMeX",
            "baseline": {"path": "Exec/Legacy", "code": "PeleLMeX"},
            "modifications": [{"parameter": "amr.n_cell", "value": "64 64 64"}],
            "used_llm": True,
        }
    )

    assert restored.selected_solver == "PeleLMeX"
    assert restored.selected_case == "Exec/Legacy"
    assert restored.modifications == [("amr.n_cell", "64 64 64")]
    assert restored.used_llm is True


def test_migrate_legacy_dict_requires_solver() -> None:
    try:
        SimulationPlanFactory._migrate_legacy_dict({"baseline": {}})
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "missing solver" in str(exc)


def test_has_checklist_implementation_locations_rejects_invalid_manifest_shapes() -> None:
    assert has_checklist_implementation_locations({}) is False
    assert has_checklist_implementation_locations({"validation_manifest": []}) is False
    assert (
        has_checklist_implementation_locations(
            {"validation_manifest": {"consistency_checklist": "not-a-list"}}
        )
        is False
    )
    assert (
        has_checklist_implementation_locations(
            {"validation_manifest": {"consistency_checklist": [{"implementation_locations": []}]}}
        )
        is False
    )
    assert (
        has_checklist_implementation_locations(
            {"validation_manifest": {"consistency_checklist": ["not-a-dict"]}}
        )
        is False
    )


def test_has_checklist_implementation_locations_accepts_supported_shapes() -> None:
    top_level = {
        "validation_manifest": {
            "consistency_checklist": [
                {"implementation_locations": ["src/graph.py"]},
                {"services": ["src/services/plan.py"]},
                {"implementation_location": "tests/unit/test_plan.py"},
            ]
        }
    }
    assert has_checklist_implementation_locations(top_level) is True

    generic = {
        "validation_manifest": {
            "checklist": [
                {"locations": ["src/graph.py"]},
            ]
        }
    }
    assert has_checklist_implementation_locations(generic) is True

    nested = {
        "validation_manifest": {
            "consistency": {
                "checklist": [
                    {"files": ["src/services/plan.py"]},
                ]
            }
        }
    }
    assert has_checklist_implementation_locations(nested) is True
