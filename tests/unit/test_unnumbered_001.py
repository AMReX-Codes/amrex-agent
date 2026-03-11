"""Session 16 tests for global function complexity criterion wiring."""

from __future__ import annotations

import pytest

from src.graph import (
    _paper_validator_mode2_enabled,
    _route_after_clarification,
    _route_after_input_writer,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    feature_a_dependency_handler_node,
    global_function_complexity_handler_node,
    sweep_execution_handler_node,
)
from src.services.plan import (
    GLOBAL_FUNCTION_COMPLEXITY_DEFAULT_THRESHOLD,
    GLOBAL_FUNCTION_COMPLEXITY_ID,
    SimulationPlan,
    SimulationPlanFactory,
    build_global_complexity_report,
    global_function_complexity_failure_reason,
    global_function_complexity_passed,
)


def _sample_plan() -> SimulationPlan:
    return SimulationPlan(
        selected_solver="PeleLMeX",
        selected_case="Exec/FlameSheet",
        modifications=[("amr.max_level", 2)],
        reasoning="baseline",
        solver_confidence=0.9,
        baseline_confidence=0.8,
        cbr_confidence=0.7,
    )


def test_simulation_plan_methods_cover_summary_and_serialization():
    plan = _sample_plan()

    as_dict = plan.to_dict()
    assert as_dict["selected_solver"] == "PeleLMeX"

    as_json = plan.to_json()
    assert '"selected_solver": "PeleLMeX"' in as_json

    assert plan.get_overall_confidence() == pytest.approx(0.79)
    summary = plan.get_summary()
    assert "Simulation Plan Summary" in summary
    assert "Overall:" in summary


def test_create_from_rag_requires_baseline_result():
    with pytest.raises(ValueError, match="baseline_result is required"):
        SimulationPlanFactory.create_from_rag(
            solver_name="PeleLMeX",
            baseline_result={},
            cbr_plan={},
            docs=[],
            user_prompt="run",
        )


def test_create_from_rag_converts_dict_modifications_and_generates_reasoning():
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={
            "selected_case": {"case": "Exec/CaseA", "metadata": {"repo_path": "fallback"}},
            "confidence": 0.65,
            "candidates": [{"case": "Exec/CaseA"}],
        },
        cbr_plan={
            "modifications": [{"parameter": "max_step", "value": 20}],
            "similar_cases": ["CaseA", "CaseB"],
        },
        docs=[{"doc": "x"}],
        user_prompt="prompt",
        solver_confidence=0.75,
        used_llm=True,
    )

    assert plan.selected_case == "Exec/CaseA"
    assert plan.modifications == [("max_step", 20)]
    assert "CaseA" in plan.reasoning
    assert plan.used_llm is True
    assert plan.indexing_strategy == "hierarchical"


def test_create_from_simple_handles_match_rationale_and_confidence():
    plan = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "PeleLMeX"},
        baseline={
            "name": "Flame",
            "path": "Exec/Flame",
            "match_score": 0.66,
            "match_rationale": "Closest setup.",
        },
        modifications=[],
        visualization={"plots": []},
        analysis={"checks": []},
        user_prompt="run flame",
    )

    assert plan.selected_solver == "PeleLMeX"
    assert plan.selected_case == "Exec/Flame"
    assert plan.baseline_confidence == pytest.approx(0.66)
    assert "Closest setup" in plan.reasoning


def test_create_from_simple_raises_when_solver_missing():
    with pytest.raises(ValueError, match="missing solver"):
        SimulationPlanFactory.create_from_simple(
            requirements={},
            baseline={},
            modifications=[],
            visualization={},
            analysis={},
            user_prompt="run",
        )


def test_from_dict_filters_unknown_fields_and_converts_list_modifications():
    plan = SimulationPlanFactory.from_dict(
        {
            "selected_solver": "PeleLMeX",
            "selected_case": "Exec/Flame",
            "modifications": [["max_step", 10]],
            "reasoning": "ok",
            "unknown": "ignored",
        }
    )
    assert plan.modifications == [("max_step", 10)]


def test_from_dict_migrates_legacy_dict():
    plan = SimulationPlanFactory.from_dict(
        {
            "solver": "PeleC",
            "baseline": {"path": "Exec/Jet", "code": "PeleC"},
            "modifications": [{"parameter": "dt", "value": 1e-6}],
            "reasoning": "legacy",
        }
    )

    assert plan.selected_solver == "PeleC"
    assert plan.selected_case == "Exec/Jet"
    assert plan.modifications == [("dt", 1e-6)]


def test_from_dict_migration_raises_if_solver_missing():
    with pytest.raises(ValueError, match="missing solver"):
        SimulationPlanFactory.from_dict({"baseline": {}})


def test_build_global_complexity_report_flags_violations():
    source = """
def simple(x):
    return x

def complex_fn(a, b, c):
    if a and b and c:
        return 1
    if a:
        return 2
    if b:
        return 3
    if c:
        return 4
    return 0
"""
    report = build_global_complexity_report(source, threshold=3)

    assert report["criterion"] == GLOBAL_FUNCTION_COMPLEXITY_ID
    assert report["threshold"] == 3
    assert len(report["functions"]) == 2
    assert report["passes"] is False
    assert report["violations"][0]["name"] == "complex_fn"


def test_build_global_complexity_report_default_threshold():
    report = build_global_complexity_report("def a():\n    return 1\n")
    assert report["threshold"] == GLOBAL_FUNCTION_COMPLEXITY_DEFAULT_THRESHOLD
    assert report["passes"] is True


def test_global_complexity_passed_checks_gate_approval_first():
    state = {
        "global_complexity_report": {"passes": False},
        "gate_approvals": [
            {
                "decision": "approved",
                "details": {"criterion": GLOBAL_FUNCTION_COMPLEXITY_ID},
            }
        ],
    }
    assert global_function_complexity_passed(state) is True
    assert global_function_complexity_failure_reason(state) == "global_function_complexity_satisfied"


def test_global_complexity_passed_checks_report_fallbacks():
    assert global_function_complexity_passed({"global_complexity_report": {"passes": True}}) is True
    assert global_function_complexity_passed({"global_complexity_report": {"violations": [1]}}) is False
    assert global_function_complexity_passed({}) is False
    assert (
        global_function_complexity_failure_reason({})
        == "global_function_complexity_threshold_exceeded"
    )


def test_graph_clarification_and_sweep_routes():
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({}) == "input_writer_node"

    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": "s1"}) == (
        "sweep_execution_handler"
    )
    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": None}) == (
        "architect_node"
    )
    assert _route_after_sweep_detection({"sweep_id": None}) == "feature_a_dependency_handler"


def test_paper_validator_mode2_enabled_paths():
    assert _paper_validator_mode2_enabled({"paper_validator_enabled": True}) is True
    assert _paper_validator_mode2_enabled({"config": {"paper_validator_enabled": True}}) is True

    class Cfg:
        paper_validator_enabled = True

    assert _paper_validator_mode2_enabled({"config": Cfg()}) is True
    assert _paper_validator_mode2_enabled({}) is False


def test_route_after_input_writer_covers_complexity_and_mode2_routes():
    assert _route_after_input_writer({}) == "end"

    blocked = _route_after_input_writer(
        {
            "enforce_global_function_complexity": True,
            "global_complexity_report": {"passes": False},
        }
    )
    assert blocked == "global_function_complexity_handler"

    to_mode2 = _route_after_input_writer(
        {
            "enforce_global_function_complexity": True,
            "global_complexity_report": {"passes": True},
            "paper_validator_enabled": True,
            "validation_manifest": {"ok": True},
        }
    )
    assert to_mode2 == "paper_validator_node"


def test_graph_handlers_record_rejections_and_dedupe_errors():
    dep_updates = feature_a_dependency_handler_node(
        {"gate_approvals": "invalid", "errors_active": ["feature_a_dependency_unverified"]}
    )
    assert dep_updates["mode"] == "terminal"
    assert dep_updates["reviewer_failure_category"] == "dependency_gate"

    complexity_updates = global_function_complexity_handler_node(
        {
            "gate_approvals": [],
            "errors_active": ["global_function_complexity_threshold_exceeded"],
            "global_complexity_report": {"passes": False},
        }
    )
    assert complexity_updates["mode"] == "terminal"
    assert complexity_updates["reviewer_failure_category"] == "complexity_gate"
    assert complexity_updates["gate_approvals"][-1]["details"]["criterion"] == (
        GLOBAL_FUNCTION_COMPLEXITY_ID
    )
    assert complexity_updates["errors_active"].count(
        "global_function_complexity_threshold_exceeded"
    ) == 1


def test_graph_placeholder_nodes_return_state():
    state = {"clarification_questions": ["q"], "sweep_id": "s1", "sweep_parameter": "x"}
    assert clarification_handler_node(state) is state
    assert sweep_execution_handler_node(state) is state


def test_create_graph_wires_global_complexity_handler():
    graph = create_graph().compile().get_graph()
    nodes = set(graph.nodes)
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert "global_function_complexity_handler" in nodes
    assert ("input_writer_node", "global_function_complexity_handler") in edges
    assert ("global_function_complexity_handler", "__end__") in edges
