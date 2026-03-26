"""Unit tests for helper-extraction policy on large new files."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

GRAPH_MODULE_NAME = "src/graph.py"
PLAN_MODULE_NAME = "src/services/plan.py"
REPO_ROOT = Path(__file__).resolve().parents[2]

GRAPH_SPEC = importlib.util.spec_from_file_location(
    GRAPH_MODULE_NAME,
    REPO_ROOT / "src" / "graph.py",
)
assert GRAPH_SPEC is not None and GRAPH_SPEC.loader is not None
GRAPH_MODULE = importlib.util.module_from_spec(GRAPH_SPEC)
sys.modules[GRAPH_MODULE_NAME] = GRAPH_MODULE
GRAPH_SPEC.loader.exec_module(GRAPH_MODULE)

PLAN_SPEC = importlib.util.spec_from_file_location(
    PLAN_MODULE_NAME,
    REPO_ROOT / "src" / "services" / "plan.py",
)
assert PLAN_SPEC is not None and PLAN_SPEC.loader is not None
PLAN_MODULE = importlib.util.module_from_spec(PLAN_SPEC)
sys.modules[PLAN_MODULE_NAME] = PLAN_MODULE
PLAN_SPEC.loader.exec_module(PLAN_MODULE)

SimulationPlan = PLAN_MODULE.SimulationPlan
SimulationPlanFactory = PLAN_MODULE.SimulationPlanFactory
find_feature_blocks_missing_tests_fixtures = PLAN_MODULE.find_feature_blocks_missing_tests_fixtures
find_feature_blocks_missing_helper_extraction = PLAN_MODULE.find_feature_blocks_missing_helper_extraction
validate_new_file_helper_extraction = PLAN_MODULE.validate_new_file_helper_extraction
validate_feature_blocks_tests_fixtures = PLAN_MODULE.validate_feature_blocks_tests_fixtures
_paper_validator_enabled = GRAPH_MODULE._paper_validator_enabled
_route_after_architect = GRAPH_MODULE._route_after_architect
_route_after_clarification = GRAPH_MODULE._route_after_clarification
_route_after_paper_validator = GRAPH_MODULE._route_after_paper_validator
_route_after_sweep_detection = GRAPH_MODULE._route_after_sweep_detection
clarification_handler_node = GRAPH_MODULE.clarification_handler_node
create_graph = GRAPH_MODULE.create_graph
sweep_execution_handler_node = GRAPH_MODULE.sweep_execution_handler_node


def test_simulation_plan_serialization_summary_and_confidence() -> None:
    plan = SimulationPlan(
        selected_solver="PeleC",
        selected_case="Exec/Case",
        modifications=[("amr.n_cell", "64 64 64")],
        reasoning="x" * 240,
        solver_confidence=0.8,
        baseline_confidence=0.6,
        cbr_confidence=0.5,
        used_llm=True,
        indexing_strategy="hierarchical",
    )

    as_dict = plan.to_dict()
    assert as_dict["selected_solver"] == "PeleC"

    as_json = plan.to_json(indent=2)
    assert '"selected_solver": "PeleC"' in as_json

    assert math.isclose(plan.get_overall_confidence(), 0.61, rel_tol=1e-9)
    summary = plan.get_summary()
    assert "Simulation Plan Summary" in summary
    assert "Reasoning:" in summary
    assert "..." in summary


def test_create_from_rag_requires_baseline_result() -> None:
    with pytest.raises(ValueError, match="baseline_result is required"):
        SimulationPlanFactory.create_from_rag(
            solver_name="PeleC",
            baseline_result={},
            cbr_plan={},
            docs=[],
            user_prompt="run",
        )


def test_create_from_rag_converts_dict_modifications_and_builds_reasoning() -> None:
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={
            "selected_case": {"case": "Exec/Flame", "metadata": {"repo_path": "Exec/Fallback"}},
            "confidence": 0.77,
            "candidates": [{"case": "Exec/Flame"}],
        },
        cbr_plan={
            "modifications": [
                {"parameter": "amr.n_cell", "value": "128 128 128"},
                {"parameter": "max_step", "value": 50},
            ],
            "confidence": 0.9,
            "similar_cases": ["case-a", "case-b"],
        },
        docs=[{"title": "doc1"}],
        user_prompt="simulate flame",
        solver_confidence=0.95,
        used_llm=True,
    )

    assert plan.selected_case == "Exec/Flame"
    assert plan.modifications == [("amr.n_cell", "128 128 128"), ("max_step", 50)]
    assert "patterns from: case-a, case-b" in plan.reasoning
    assert plan.documentation_context == [{"title": "doc1"}]
    assert plan.case_candidates == [{"case": "Exec/Flame"}]
    assert plan.used_llm is True


def test_create_from_rag_uses_fallback_case_and_preserves_non_dict_modifications() -> None:
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={"selected_case": {"metadata": {"repo_path": "Exec/Fallback"}}},
        cbr_plan={"modifications": [["amr.plot_int", 10]], "reasoning": "provided"},
        docs=[],
        user_prompt="run",
    )

    assert plan.selected_case == "Exec/Fallback"
    assert plan.reasoning == "provided"
    assert plan.modifications == [("amr.plot_int", 10)]


def test_create_from_simple_paths() -> None:
    with pytest.raises(ValueError, match="missing solver"):
        SimulationPlanFactory.create_from_simple(
            requirements={},
            baseline={},
            modifications=[],
            visualization={},
            analysis={},
            user_prompt="run",
        )

    plan = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "WarpX"},
        baseline={
            "name": "BaseCase",
            "path": "Exec/Base",
            "match_score": 0.88,
            "match_rationale": "nearest known setup",
        },
        modifications=[("max_step", 100)],
        visualization={"kind": "slice"},
        analysis={"check": "ok"},
        user_prompt="test",
    )

    assert plan.selected_solver == "WarpX"
    assert plan.selected_case == "Exec/Base"
    assert "nearest known setup" in plan.reasoning
    assert plan.cbr_confidence == 1.0
    assert plan.indexing_strategy == "simple"

    plan_no_mods = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "PeleC"},
        baseline={"code_name": "PeleC", "case_dir": "Exec/Alt", "total_score": 0.7},
        modifications=[],
        visualization={},
        analysis={},
        user_prompt="test",
    )
    assert plan_no_mods.cbr_confidence == 0.0
    assert plan_no_mods.baseline_confidence == 0.7


def test_from_dict_filters_unknown_fields_and_converts_mod_lists() -> None:
    data = {
        "selected_solver": "PeleC",
        "selected_case": "Exec/Case",
        "modifications": [["max_step", 20]],
        "reasoning": "ok",
        "unused_field": "ignored",
    }

    plan = SimulationPlanFactory.from_dict(data)
    assert plan.selected_solver == "PeleC"
    assert plan.modifications == [("max_step", 20)]


def test_migrate_legacy_dict_paths() -> None:
    migrated = SimulationPlanFactory._migrate_legacy_dict(
        {
            "solver": "PeleC",
            "baseline": {"path": "Exec/Legacy"},
            "modifications": [{"parameter": "amr.n_cell", "value": "32 32 32"}],
            "reasoning": "legacy",
        }
    )
    assert migrated["selected_solver"] == "PeleC"
    assert migrated["selected_case"] == "Exec/Legacy"
    assert migrated["modifications"] == [("amr.n_cell", "32 32 32")]

    migrated_unknown_case = SimulationPlanFactory._migrate_legacy_dict(
        {"selected_solver": "WarpX", "modifications": []}
    )
    assert migrated_unknown_case["selected_case"] == "unknown"

    with pytest.raises(ValueError, match="missing solver/selected_solver"):
        SimulationPlanFactory._migrate_legacy_dict({"baseline": {}, "modifications": []})


def test_feature_block_tests_fixtures_validator() -> None:
    markdown_ok = """
## [F-001] First Feature
Tests/Fixtures: tests/unit/test_one.py, tests/integration/fixtures/sample.json

## [F-002] Second Feature
tests/fixtures: tests/unit/test_two.py
""".strip()
    result_ok = validate_feature_blocks_tests_fixtures(markdown_ok)
    assert result_ok["feature_blocks_validation_passed"] is True
    assert result_ok["feature_blocks_validation_reason"] == "ok"
    assert result_ok["feature_blocks_missing_tests_fixtures"] == []

    markdown_bad = """
## [F-003] Missing Mapping
Scope: docs only

## [F-004] Empty Mapping
Tests/Fixtures:
""".strip()
    result_bad = validate_feature_blocks_tests_fixtures(markdown_bad)
    assert result_bad["feature_blocks_validation_passed"] is False
    assert result_bad["feature_blocks_validation_reason"] == "missing_tests_fixtures_mapping"
    assert result_bad["feature_blocks_missing_tests_fixtures"] == [
        "## [F-003] Missing Mapping",
        "## [F-004] Empty Mapping",
    ]
    assert find_feature_blocks_missing_tests_fixtures("No feature blocks here.") == []


def test_new_file_helper_extraction_validator() -> None:
    markdown_ok = """
## [F-020] Large New Module
New files:
- src/new_module.py (132 LOC)
Helper Extraction: split parser and formatter helpers into dedicated functions.
Tests/Fixtures: tests/unit/test_new_module.py

## [F-021] Small New Module
New files:
- src/small_module.py (88 LOC)
Tests/Fixtures: tests/unit/test_small_module.py
""".strip()
    result_ok = validate_new_file_helper_extraction(markdown_ok)
    assert result_ok["new_file_helper_extraction_validation_passed"] is True
    assert result_ok["new_file_helper_extraction_validation_reason"] == "ok"
    assert result_ok["new_file_helper_extraction_missing"] == []

    markdown_bad = """
## [F-022] Missing Helper Extraction
New files:
- src/large_module.py (145 LOC)
Tests/Fixtures: tests/unit/test_large_module.py
""".strip()
    result_bad = validate_new_file_helper_extraction(markdown_bad)
    assert result_bad["new_file_helper_extraction_validation_passed"] is False
    assert (
        result_bad["new_file_helper_extraction_validation_reason"]
        == "missing_helper_extraction_for_large_new_file"
    )
    assert result_bad["new_file_helper_extraction_missing"] == [
        "## [F-022] Missing Helper Extraction"
    ]
    assert find_feature_blocks_missing_helper_extraction("No feature blocks here.") == []


def test_graph_routes_cover_feature_block_and_existing_branches() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"

    assert _route_after_sweep_detection({"sweep_id": "sweep-1"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"

    assert _paper_validator_enabled({}) is False
    assert _paper_validator_enabled({"config": {}}) is False
    assert _paper_validator_enabled({"config": {"paper_validator_enabled": True}}) is True
    assert _paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True

    assert _route_after_architect({"config": {"paper_validator_enabled": True}}) == "paper_validator_node"
    assert _route_after_architect({"config": {"paper_validator_enabled": False}}) == "intent_extraction_node"

    assert _route_after_paper_validator({"paper_validation_passed": False}) == "end"

    assert (
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": "## [F-100] Missing\nScope: x",
            }
        )
        == "end"
    )

    assert (
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_validation_required": True,
                "feature_blocks_validation_passed": False,
            }
        )
        == "end"
    )

    assert (
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": "## [F-101] Good\nTests/Fixtures: tests/unit/test_ok.py",
                "claim_evidence_matrix_required": True,
                "claim_evidence_matrix_complete": False,
            }
        )
        == "end"
    )

    assert (
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": "## [F-102] Good\nTests/Fixtures: tests/unit/test_ok.py",
                "claim_evidence_matrix_required": True,
                "claim_evidence_matrix_complete": True,
            }
        )
        == "intent_extraction_node"
    )

    assert (
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": (
                    "## [F-200] Needs helper\n"
                    "New files:\n"
                    "- src/feature.py (120 LOC)\n"
                    "Tests/Fixtures: tests/unit/test_feature.py"
                ),
            }
        )
        == "end"
    )

    assert (
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": (
                    "## [F-201] Helper documented\n"
                    "New files:\n"
                    "- src/feature.py (120 LOC)\n"
                    "Helper Extraction: split into parse/validate helpers.\n"
                    "Tests/Fixtures: tests/unit/test_feature.py"
                ),
            }
        )
        == "intent_extraction_node"
    )

    assert (
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "new_file_helper_extraction_validation_required": True,
                "new_file_helper_extraction_validation_passed": False,
            }
        )
        == "end"
    )

    assert _route_after_paper_validator({"paper_validation_passed": True}) == "intent_extraction_node"


def test_graph_handlers_and_wiring_cover_helper_extraction_routes() -> None:
    clarification_state = {"clarification_questions": ["q1"]}
    sweep_state = {"sweep_id": "sweep-1", "sweep_parameter": "max_step"}

    assert clarification_handler_node(clarification_state) is clarification_state
    assert sweep_execution_handler_node(sweep_state) is sweep_state

    app = create_graph().compile()
    graph_def = app.get_graph()
    nodes = set(graph_def.nodes.keys())
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert "sweep_detection_node" in nodes
    assert "architect_node" in nodes
    assert "paper_validator_node" in nodes
    assert "intent_extraction_node" in nodes
    assert "clarification_node" in nodes
    assert "clarification_handler" in nodes
    assert "sweep_execution_handler" in nodes
    assert "input_writer_node" in nodes

    assert ("__start__", "sweep_detection_node") in edges
    assert ("architect_node", "paper_validator_node") in edges
    assert ("architect_node", "intent_extraction_node") in edges
    assert ("paper_validator_node", "intent_extraction_node") in edges
    assert ("paper_validator_node", "__end__") in edges
    assert ("clarification_handler", "clarification_node") in edges
    assert ("clarification_handler", "paper_manifest_gate_node") in edges
    assert ("sweep_execution_handler", "architect_node") in edges
    assert ("input_writer_node", "__end__") in edges
