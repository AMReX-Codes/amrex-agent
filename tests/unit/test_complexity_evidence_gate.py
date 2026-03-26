"""Complexity evidence gate tests."""

from __future__ import annotations

import subprocess

import pytest

from src.graph import (
    _paper_validator_enabled,
    _route_after_clarification,
    _route_after_complexity_evidence,
    _route_after_paper_validator,
    _route_after_sweep_detection,
    clarification_handler_node,
    complexity_evidence_handler_node,
    complexity_evidence_node,
    create_graph,
    paper_validator_node,
    session_dependency_handler_node,
    sweep_execution_handler_node,
)
from src.services.plan import (
    SimulationPlan,
    SimulationPlanFactory,
    collect_radon_complexity_evidence,
)
from src.session_manager import SESSION_DEPENDENCY_COMPLETION_MARKER


def test_collect_radon_complexity_evidence_when_missing(monkeypatch):
    monkeypatch.setattr("src.services.plan.shutil.which", lambda _name: None)

    evidence = collect_radon_complexity_evidence()

    assert evidence["criterion"]
    assert evidence["radon_available"] is False
    assert evidence["passed"] is False
    assert "missing" in evidence["detail"]


def test_collect_radon_complexity_evidence_when_available(monkeypatch):
    monkeypatch.setattr("src.services.plan.shutil.which", lambda _name: "/usr/bin/radon")

    def _run(cmd, check, capture_output, text):
        assert cmd == ["/usr/bin/radon", "cc", "src/services/plan.py", "-n", "C"]
        assert check is False
        assert capture_output is True
        assert text is True
        return subprocess.CompletedProcess(cmd, 0, stdout="A (3)", stderr="")

    monkeypatch.setattr("src.services.plan.subprocess.run", _run)

    evidence = collect_radon_complexity_evidence()

    assert evidence["radon_available"] is True
    assert evidence["passed"] is True
    assert evidence["exit_code"] == 0
    assert evidence["output"] == "A (3)"


def test_collect_radon_complexity_evidence_when_invocation_fails(monkeypatch):
    monkeypatch.setattr("src.services.plan.shutil.which", lambda _name: "/usr/bin/radon")

    def _raise(*_args, **_kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("src.services.plan.subprocess.run", _raise)

    evidence = collect_radon_complexity_evidence()

    assert evidence["radon_available"] is False
    assert evidence["passed"] is False
    assert "failed" in evidence["detail"]


def test_simulation_plan_serialization_summary_and_confidence():
    plan = SimulationPlan(
        selected_solver="PeleC",
        selected_case="Exec/CaseA",
        modifications=[("max_step", 100)],
        reasoning="x" * 220,
        solver_confidence=0.5,
        baseline_confidence=0.6,
        cbr_confidence=0.7,
    )

    as_dict = plan.to_dict()
    as_json = plan.to_json(indent=2)
    summary = plan.get_summary()

    assert as_dict["selected_solver"] == "PeleC"
    assert '"selected_solver": "PeleC"' in as_json
    assert pytest.approx(plan.get_overall_confidence(), 0.001) == (0.2 * 0.5 + 0.5 * 0.6 + 0.3 * 0.7)
    assert "Reasoning:" in summary
    assert "..." in summary


def test_create_from_rag_requires_baseline_result():
    with pytest.raises(ValueError):
        SimulationPlanFactory.create_from_rag(
            solver_name="PeleC",
            baseline_result={},
            cbr_plan={},
            docs=[],
            user_prompt="simulate",
        )


def test_create_from_rag_converts_dict_mods_and_builds_reasoning():
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={
            "selected_case": {"case": "Exec/Flame", "metadata": {"repo_path": "Exec/Flame"}},
            "confidence": 0.81,
            "candidates": [{"id": 1}],
        },
        cbr_plan={
            "modifications": [
                {"parameter": "amr.max_level", "value": 2},
                {"parameter": "max_step", "value": 500},
            ],
            "similar_cases": ["A", "B", "C", "D"],
        },
        docs=[{"title": "doc"}],
        user_prompt="prompt",
        solver_confidence=0.9,
        used_llm=True,
    )

    assert plan.modifications == [("amr.max_level", 2), ("max_step", 500)]
    assert "patterns from: A, B, C" in plan.reasoning
    assert plan.selected_case == "Exec/Flame"
    assert plan.baseline_confidence == 0.81
    assert plan.used_llm is True


def test_create_from_rag_uses_case_repo_path_fallback_and_keeps_tuples():
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={
            "selected_case": {"metadata": {"repo_path": "Exec/Fallback"}},
        },
        cbr_plan={
            "modifications": [("a", 1)],
            "reasoning": "explicit",
            "confidence": 0.4,
        },
        docs=[],
        user_prompt="prompt",
    )

    assert plan.selected_case == "Exec/Fallback"
    assert plan.modifications == [("a", 1)]
    assert plan.reasoning == "explicit"


def test_create_from_simple_paths_and_confidence_fields():
    plan = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "PeleLMeX"},
        baseline={
            "code_name": "PeleC",
            "path": "Exec/Simple",
            "name": "SimpleCase",
            "match_rationale": "best match",
            "total_score": 0.91,
        },
        modifications=[("x", 1)],
        visualization={"enabled": True},
        analysis={"enabled": True},
        user_prompt="do it",
    )

    assert plan.selected_solver == "PeleC"
    assert plan.selected_case == "Exec/Simple"
    assert plan.cbr_confidence == 1.0
    assert "best match" in plan.reasoning
    assert plan.baseline_confidence == 0.91


def test_create_from_simple_raises_when_solver_missing():
    with pytest.raises(ValueError):
        SimulationPlanFactory.create_from_simple(
            requirements={},
            baseline={},
            modifications=[],
            visualization={},
            analysis={},
            user_prompt="do it",
        )


def test_from_dict_filters_unknown_fields_and_converts_list_mods():
    plan = SimulationPlanFactory.from_dict(
        {
            "selected_solver": "PeleC",
            "selected_case": "Exec/A",
            "modifications": [["x", 10]],
            "reasoning": "ok",
            "unknown": "drop-me",
        }
    )

    assert plan.selected_solver == "PeleC"
    assert plan.modifications == [("x", 10)]
    assert not hasattr(plan, "unknown")


def test_from_dict_migrates_legacy_shape_and_mod_dicts():
    plan = SimulationPlanFactory.from_dict(
        {
            "solver": "WarpX",
            "baseline": {"path": "Exec/Warp", "code": "WarpX"},
            "modifications": [{"parameter": "foo", "value": 7}],
            "reasoning": "legacy",
            "used_llm": True,
        }
    )

    assert plan.selected_solver == "WarpX"
    assert plan.selected_case == "Exec/Warp"
    assert plan.modifications == [("foo", 7)]
    assert plan.used_llm is True


def test_migrate_legacy_raises_when_solver_unavailable():
    with pytest.raises(ValueError):
        SimulationPlanFactory._migrate_legacy_dict({"baseline": {"path": "Exec/A"}})


def test_graph_routes_and_nodes_cover_session17_paths(monkeypatch):
    monkeypatch.setattr(
        "src.graph.collect_radon_complexity_evidence",
        lambda: {"radon_available": False, "passed": False},
    )

    assert _paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _paper_validator_enabled({"paper_source": "2401.12345"}) is True
    assert _paper_validator_enabled({}) is False

    assert _route_after_paper_validator({"paper_validator_enabled": True}) == "paper_validator_node"
    assert _route_after_paper_validator({}) == "input_writer_node"

    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"paper_source": "paper"}) == "paper_validator_node"
    assert _route_after_clarification({}) == "input_writer_node"

    assert _route_after_sweep_detection({}) == "architect_node"
    assert (
        _route_after_sweep_detection(
            {"sweep_id": "sweep", "enforce_session_dependency_gate": True}
        )
        == "session_dependency_handler"
    )
    assert _route_after_sweep_detection(
        {"sweep_id": "sweep", "session_markers": {SESSION_DEPENDENCY_COMPLETION_MARKER: True}}
    ) == "sweep_execution_handler"

    assert _route_after_complexity_evidence({}) == "end"
    assert _route_after_complexity_evidence(
        {"enforce_radon_complexity_evidence": True, "radon_complexity_evidence": {"radon_available": True}}
    ) == "end"
    assert _route_after_complexity_evidence({"enforce_radon_complexity_evidence": True}) == "complexity_evidence_handler"

    assert session_dependency_handler_node({})["required_marker"] == SESSION_DEPENDENCY_COMPLETION_MARKER

    enforced = complexity_evidence_node({"enforce_radon_complexity_evidence": True})
    assert enforced["radon_complexity_evidence"]["radon_available"] is False

    unchanged = complexity_evidence_node({"enforce_radon_complexity_evidence": False})
    assert "radon_complexity_evidence" not in unchanged

    handler = complexity_evidence_handler_node({"enforce_radon_complexity_evidence": True})
    assert handler["required_marker"] == "radon_complexity_evidence"
    assert "Radon complexity evidence" in handler["dependency_error"]

    assert clarification_handler_node({"clarification_questions": ["q1"]}) == {"clarification_questions": ["q1"]}
    assert sweep_execution_handler_node({"sweep_id": "id", "sweep_parameter": "p"})["sweep_id"] == "id"
    state = {"x": 1}
    assert paper_validator_node(state) is state


def test_graph_contains_complexity_evidence_wiring():
    app = create_graph().compile()
    graph_def = app.get_graph()
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert ("input_writer_node", "complexity_evidence_node") in edges
    assert ("complexity_evidence_node", "complexity_evidence_handler") in edges
    assert ("complexity_evidence_node", "__end__") in edges
    assert ("complexity_evidence_handler", "__end__") in edges
