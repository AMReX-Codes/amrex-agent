"""Session 49 tests for UNNUMBERED-002-01 radon complexity gate."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.graph import (
    CRITICAL_PATH_FEATURES_SECTION,
    REQUIRED_OUTPUTS_SECTION,
    _is_paper_validator_enabled,
    _latest_architect_details,
    _route_after_clarification,
    _route_after_manifest_validation,
    _route_after_radon_cc_gate,
    _route_after_required_outputs,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    critical_path_features_section_node,
    paper_manifest_gate_node,
    radon_cc_gate_node,
    required_outputs_section_node,
    sweep_execution_handler_node,
)
from src.models.paper_validation_manifest import PaperValidationManifest, ValidationCheckResult
from src.services.plan import SimulationPlan, SimulationPlanFactory, evaluate_radon_cc_threshold


def test_evaluate_radon_cc_threshold_paths() -> None:
    assert evaluate_radon_cc_threshold(radon_available=False, flagged_functions=[]) == {
        "valid": False,
        "error": "radon is not installed",
        "offenders": [],
    }
    assert evaluate_radon_cc_threshold(
        radon_available=True, flagged_functions={"bad": "type"}  # type: ignore[arg-type]
    )["error"] == "radon_cc_functions must be a list of mappings"
    assert evaluate_radon_cc_threshold(
        radon_available=True, flagged_functions=[123]  # type: ignore[list-item]
    )["error"] == "radon_cc_functions entries must be mappings"

    passing = evaluate_radon_cc_threshold(
        radon_available=True,
        flagged_functions=[
            {"name": "f", "complexity": "10"},
            {"name": "f2", "complexity": 10.0},
            {"name": "skip-bool", "complexity": True},
            {"name": "skip-float", "complexity": 10.2},
            {"name": "skip-text", "complexity": "not-a-number"},
        ],
    )
    assert passing["valid"] is True
    assert passing["offenders"] == []
    assert (
        evaluate_radon_cc_threshold(
            radon_available=True,
            flagged_functions=None,
        )["valid"]
        is True
    )

    failing = evaluate_radon_cc_threshold(
        radon_available=True,
        flagged_functions=[{"name": "hard_fn", "complexity": 11}],
    )
    assert failing["valid"] is False
    assert failing["error"] == "functions exceed complexity threshold"
    assert failing["offenders"] == [{"name": "hard_fn", "complexity": 11}]

    with pytest.raises(ValueError, match="non-negative"):
        evaluate_radon_cc_threshold(
            radon_available=True,
            flagged_functions=[],
            max_complexity=-1,
        )


def test_simulation_plan_model_helpers() -> None:
    plan = SimulationPlan(
        selected_solver="AMReX",
        selected_case="Exec/FlameSheet",
        modifications=[("amr.n_cell", "64 64 64")],
        reasoning="Detailed reasoning",
        solver_confidence=0.9,
        baseline_confidence=0.8,
        cbr_confidence=0.7,
        used_llm=True,
        indexing_strategy="hierarchical",
    )
    as_dict = plan.to_dict()
    as_json = plan.to_json()
    summary = plan.get_summary()

    assert as_dict["selected_solver"] == "AMReX"
    assert "\"selected_solver\": \"AMReX\"" in as_json
    assert plan.get_overall_confidence() == pytest.approx(0.79)
    assert "Simulation Plan Summary" in summary
    assert "Overall:" in summary


def test_create_from_rag_raises_without_baseline_result() -> None:
    with pytest.raises(ValueError, match="baseline_result is required"):
        SimulationPlanFactory.create_from_rag(
            solver_name="AMReX",
            baseline_result={},
            cbr_plan={},
            docs=[],
            user_prompt="run a case",
        )


def test_create_from_rag_supports_dict_mods_and_reasoning_fallback() -> None:
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={
            "selected_case": {"case": "Exec/Flame", "metadata": {"repo_path": "Exec/Flame"}},
            "confidence": 0.66,
            "candidates": [{"case": "Exec/Alt"}],
        },
        cbr_plan={
            "modifications": [
                {"parameter": "amr.max_level", "value": "2"},
                {"parameter": "amr.n_cell", "value": "128 128 128"},
            ],
            "confidence": 0.55,
            "reasoning": "",
            "similar_cases": ["CaseA", "CaseB"],
        },
        docs=[{"id": "d1"}],
        user_prompt="simulate flame",
        solver_confidence=0.88,
        used_llm=True,
    )

    assert plan.selected_solver == "PeleC"
    assert plan.selected_case == "Exec/Flame"
    assert plan.modifications == [
        ("amr.max_level", "2"),
        ("amr.n_cell", "128 128 128"),
    ]
    assert "patterns from: CaseA, CaseB" in plan.reasoning
    assert plan.baseline_confidence == pytest.approx(0.66)
    assert plan.cbr_confidence == pytest.approx(0.55)
    assert plan.used_llm is True


def test_create_from_rag_uses_explicit_reasoning_and_metadata_fallback_case() -> None:
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="WarpX",
        baseline_result={"selected_case": {"metadata": {"repo_path": "Exec/Laser"}}},
        cbr_plan={"modifications": [("diag.period", "10")], "reasoning": "explicit"},
        docs=[],
        user_prompt="laser wakefield",
    )
    assert plan.selected_case == "Exec/Laser"
    assert plan.reasoning == "explicit"


def test_create_from_simple_paths() -> None:
    plan = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "AMReX"},
        baseline={"code_name": "AMReX", "path": "Exec/Advection", "name": "Advection"},
        modifications=[("amr.n_cell", "64 64 64")],
        visualization={"enabled": True},
        analysis={"enabled": True},
        user_prompt="advection",
    )
    assert plan.selected_solver == "AMReX"
    assert plan.selected_case == "Exec/Advection"
    assert plan.baseline_confidence == pytest.approx(0.5)
    assert plan.cbr_confidence == pytest.approx(1.0)

    no_mod_plan = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "PeleC"},
        baseline={"code": "PeleC", "case_dir": "Exec/Flame", "name": "Flame", "total_score": 0.91},
        modifications=[],
        visualization={},
        analysis={},
        user_prompt="flame",
    )
    assert no_mod_plan.baseline_confidence == pytest.approx(0.91)
    assert no_mod_plan.cbr_confidence == pytest.approx(0.0)
    with_rationale = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "PeleC"},
        baseline={
            "code": "PeleC",
            "case_dir": "Exec/Flame",
            "name": "Flame",
            "match_score": 0.87,
            "match_rationale": "close parameter fit",
        },
        modifications=[],
        visualization={},
        analysis={},
        user_prompt="flame",
    )
    assert "close parameter fit" in with_rationale.reasoning

    with pytest.raises(ValueError, match="missing solver"):
        SimulationPlanFactory.create_from_simple(
            requirements={},
            baseline={"path": "Exec/Missing"},
            modifications=[],
            visualization={},
            analysis={},
            user_prompt="bad request",
        )


def test_from_dict_and_legacy_migration_paths() -> None:
    from_selected = SimulationPlanFactory.from_dict(
        {
            "selected_solver": "AMReX",
            "selected_case": "Exec/Advection",
            "modifications": [["amr.n_cell", "64 64 64"]],
            "reasoning": "from dict",
            "unknown": "ignored",
        }
    )
    assert from_selected.selected_solver == "AMReX"
    assert from_selected.modifications == [("amr.n_cell", "64 64 64")]

    migrated = SimulationPlanFactory.from_dict(
        {
            "solver": "PeleC",
            "baseline": {"path": "Exec/Flame", "code": "PeleC", "case_dir": "Exec/Flame"},
            "modifications": [{"parameter": "amr.max_level", "value": "1"}],
            "reasoning": "legacy",
            "used_llm": True,
        }
    )
    assert migrated.selected_solver == "PeleC"
    assert migrated.selected_case == "Exec/Flame"
    assert migrated.modifications == [("amr.max_level", "1")]
    assert migrated.used_llm is True

    migrated_with_case_dir = SimulationPlanFactory.from_dict(
        {
            "solver": "PeleLMeX",
            "baseline": {"case_dir": "Exec/OnlyCaseDir", "code": "PeleLMeX"},
            "modifications": [],
        }
    )
    assert migrated_with_case_dir.selected_case == "Exec/OnlyCaseDir"

    with pytest.raises(ValueError, match="missing solver/selected_solver"):
        SimulationPlanFactory.from_dict({"baseline": {"path": "Exec/OnlyCase"}})


def test_required_outputs_helpers_and_node_paths() -> None:
    assert REQUIRED_OUTPUTS_SECTION == ("selected_case", "modifications")
    assert _latest_architect_details({}) is None
    assert _latest_architect_details({"workflow_history": "bad"}) is None
    assert _latest_architect_details({"workflow_history": [{"node": "architect"}]}) is None
    assert _latest_architect_details(
        {
            "workflow_history": [
                {"node": "architect", "details": {"selected_case": "first"}},
                {"node": "architect", "details": {"selected_case": "last", "modifications": []}},
            ]
        }
    ) == {"selected_case": "last", "modifications": []}

    valid = required_outputs_section_node({"selected_case": "case-a", "modifications": []})
    assert valid["required_outputs_valid"] is True
    assert valid["required_outputs_missing"] == []
    assert valid["required_outputs_error"] is None

    missing = required_outputs_section_node({})
    assert missing["required_outputs_valid"] is False
    assert missing["required_outputs_missing"] == ["selected_case", "modifications"]
    assert "missing required outputs" in missing["required_outputs_error"]

    non_list = required_outputs_section_node({"selected_case": "case-a", "modifications": "bad"})
    assert non_list["required_outputs_valid"] is False
    assert "modifications must be a list" in non_list["required_outputs_error"]

    mismatch = required_outputs_section_node(
        {
            "selected_case": "case-a",
            "modifications": [{"k": 1}],
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {"selected_case": "case-b", "modifications": [{"k": 2}]},
                }
            ],
        }
    )
    assert mismatch["required_outputs_valid"] is False
    assert "selected_case mismatch" in mismatch["required_outputs_error"]
    assert "modifications mismatch" in mismatch["required_outputs_error"]


def test_graph_route_helpers() -> None:
    assert _route_after_required_outputs({"required_outputs_valid": True}) == "intent_extraction_node"
    assert _route_after_required_outputs({"required_outputs_valid": False}) == "clarification_handler"
    assert _route_after_required_outputs({}) == "clarification_handler"

    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"

    assert _route_after_sweep_detection({"sweep_id": "sweep-1"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"
    assert _route_after_sweep_detection({}) == "architect_node"

    assert _route_after_manifest_validation({"paper_manifest_valid": False}) == "clarification_handler"
    assert _route_after_manifest_validation({"paper_manifest_valid": True}) == "radon_cc_gate_node"
    assert (
        _route_after_manifest_validation(
            {
                "paper_manifest_valid": True,
                "reproducibility_oracle_enabled": True,
                "reproducibility_oracle_valid": False,
            }
        )
        == "clarification_handler"
    )
    assert (
        _route_after_manifest_validation(
            {
                "paper_manifest_valid": True,
                "reproducibility_oracle_enabled": True,
                "reproducibility_oracle_valid": True,
            }
        )
        == "radon_cc_gate_node"
    )

    assert _route_after_radon_cc_gate({"radon_cc_valid": True}) == "input_writer_node"
    assert _route_after_radon_cc_gate({"radon_cc_valid": False}) == "clarification_handler"


def test_critical_path_and_placeholder_nodes(capsys: pytest.CaptureFixture[str]) -> None:
    assert "input_writer_node" in CRITICAL_PATH_FEATURES_SECTION

    default_features = critical_path_features_section_node({})
    assert default_features["critical_path_features_valid"] is True
    assert default_features["critical_path_features_missing"] == []

    features_map = critical_path_features_section_node(
        {"critical_path_features": {name: True for name in CRITICAL_PATH_FEATURES_SECTION}}
    )
    assert features_map["critical_path_features_valid"] is True

    missing = critical_path_features_section_node(
        {"critical_path_features": [name for name in CRITICAL_PATH_FEATURES_SECTION if name != "architect_node"]}
    )
    assert missing["critical_path_features_valid"] is False
    assert missing["critical_path_features_missing"] == ["architect_node"]

    invalid_type = critical_path_features_section_node({"critical_path_features": "bad"})
    assert invalid_type["critical_path_features_valid"] is False
    assert "must be list, tuple, set, or dict" in invalid_type["critical_path_features_error"]

    clarification_state = {"clarification_questions": ["Need Reynolds number?"]}
    sweep_state = {"sweep_id": "sweep-01", "sweep_parameter": "amr.n_cell"}
    assert clarification_handler_node(clarification_state) == clarification_state
    assert sweep_execution_handler_node(sweep_state) == sweep_state
    captured = capsys.readouterr()
    assert "Clarification needed" in captured.out
    assert "Sweep detected" in captured.out


def test_manifest_and_radon_gate_nodes() -> None:
    assert _is_paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _is_paper_validator_enabled({"paper_validator_enabled": False}) is False
    assert _is_paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True
    assert _is_paper_validator_enabled({"config": object()}) is False
    assert _is_paper_validator_enabled({}) is False

    bypass = paper_manifest_gate_node({})
    assert bypass["paper_manifest_valid"] is True
    assert bypass["paper_manifest_error"] is None

    missing_manifest = paper_manifest_gate_node({"paper_validator_enabled": True})
    assert missing_manifest["paper_manifest_valid"] is False
    assert "required" in missing_manifest["paper_manifest_error"]

    invalid_manifest = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {"document_id": 123, "checks": "bad"},
        }
    )
    assert invalid_manifest["paper_manifest_valid"] is False
    assert invalid_manifest["paper_manifest_error"]

    blocking_manifest = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {
                "document_id": "paper-49",
                "checks": [{"check_id": "c1", "title": "critical", "status": "fail", "blocking": True}],
            },
        }
    )
    assert blocking_manifest["paper_manifest_valid"] is False
    assert "blocking failures" in blocking_manifest["paper_manifest_error"]

    manifest = PaperValidationManifest(
        document_id="paper-49-ok",
        checks=[ValidationCheckResult(check_id="c1", title="pass", status="pass")],
    )
    accepted_manifest = paper_manifest_gate_node(
        {"paper_validator_enabled": True, "paper_validation_manifest": manifest}
    )
    assert accepted_manifest["paper_manifest_valid"] is True
    assert accepted_manifest["paper_manifest_error"] is None
    assert accepted_manifest["paper_validation_manifest"]["document_id"] == "paper-49-ok"

    bypass_radon = radon_cc_gate_node({})
    assert bypass_radon["radon_cc_valid"] is True
    assert bypass_radon["radon_cc_offenders"] == []

    missing_radon = radon_cc_gate_node(
        {"radon_cc_gate_enabled": True, "radon_available": False, "radon_cc_functions": []}
    )
    assert missing_radon["radon_cc_valid"] is False
    assert missing_radon["radon_cc_error"] == "radon is not installed"

    offenders = radon_cc_gate_node(
        {
            "radon_cc_gate_enabled": True,
            "radon_available": True,
            "radon_cc_functions": [{"name": "hard_fn", "complexity": 14}],
        }
    )
    assert offenders["radon_cc_valid"] is False
    assert offenders["radon_cc_offenders"] == [{"name": "hard_fn", "complexity": 14}]

    passing = radon_cc_gate_node(
        {
            "radon_cc_gate_enabled": True,
            "radon_available": True,
            "radon_cc_functions": [{"name": "ok_fn", "complexity": "9"}],
        }
    )
    assert passing["radon_cc_valid"] is True
    assert passing["radon_cc_error"] is None
    assert passing["radon_cc_offenders"] == []


def test_create_graph_compiles_with_radon_gate() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()
    nodes = set(graph_def.nodes.keys())
    assert "paper_manifest_gate_node" in nodes
    assert "radon_cc_gate_node" in nodes
    assert "input_writer_node" in nodes

    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("clarification_node", "paper_manifest_gate_node") in edges
    assert ("paper_manifest_gate_node", "radon_cc_gate_node") in edges
    assert ("paper_manifest_gate_node", "clarification_handler") in edges
    assert ("radon_cc_gate_node", "input_writer_node") in edges
    assert ("radon_cc_gate_node", "clarification_handler") in edges
