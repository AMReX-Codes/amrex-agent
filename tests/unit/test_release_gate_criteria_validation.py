"""Unit tests for release-gate criteria validation."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace

GRAPH_MODULE_NAME = "src/graph.py"
GRAPH_PATH = Path(__file__).resolve().parents[2] / "src" / "graph.py"
SPEC = importlib.util.spec_from_file_location(GRAPH_MODULE_NAME, GRAPH_PATH)
assert SPEC is not None and SPEC.loader is not None
GRAPH_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[GRAPH_MODULE_NAME] = GRAPH_MODULE
SPEC.loader.exec_module(GRAPH_MODULE)

def test_compute_confidence_interval_for_multiple_samples() -> None:
    result = GRAPH_MODULE.compute_confidence_interval([0.7, 0.8, 0.9], confidence_level=0.95)

    assert result["confidence_interval_available"] is True
    assert result["sample_size"] == 3
    assert math.isclose(float(result["mean"]), 0.8, rel_tol=1e-9)
    assert float(result["lower_bound"]) < 0.8
    assert float(result["upper_bound"]) > 0.8
    assert math.isclose(float(result["confidence_level"]), 0.95, rel_tol=1e-9)


def test_compute_confidence_interval_handles_empty_and_single_samples() -> None:
    empty_result = GRAPH_MODULE.compute_confidence_interval([])

    assert empty_result["confidence_interval_available"] is False
    assert empty_result["sample_size"] == 0
    assert empty_result["mean"] is None
    assert empty_result["lower_bound"] is None
    assert empty_result["upper_bound"] is None

    single_result = GRAPH_MODULE.compute_confidence_interval([0.42])

    assert single_result["confidence_interval_available"] is False
    assert single_result["sample_size"] == 1
    assert math.isclose(float(single_result["mean"]), 0.42, rel_tol=1e-9)
    assert math.isclose(float(single_result["lower_bound"]), 0.42, rel_tol=1e-9)
    assert math.isclose(float(single_result["upper_bound"]), 0.42, rel_tol=1e-9)


def test_get_z_score_and_sample_extraction_paths() -> None:
    assert math.isclose(GRAPH_MODULE._get_z_score(0.90), 1.645, rel_tol=1e-9)
    assert math.isclose(GRAPH_MODULE._get_z_score(0.95), 1.96, rel_tol=1e-9)
    assert math.isclose(GRAPH_MODULE._get_z_score(0.99), 2.576, rel_tol=1e-9)
    assert math.isclose(GRAPH_MODULE._get_z_score(0.83), 1.96, rel_tol=1e-9)

    assert GRAPH_MODULE._extract_strategy_samples({"confidence_scores": [1, "x", 0.5]}) == [1.0, 0.5]
    assert GRAPH_MODULE._extract_strategy_samples([0.1, None, 2]) == [0.1, 2.0]
    assert GRAPH_MODULE._extract_strategy_samples("invalid") == []


def test_build_strategy_confidence_report_paths() -> None:
    state = {
        "strategy_confidence_level": 0.9,
        "strategy_metrics": {
            "rag": {"confidence_scores": [0.5, 0.7, 0.9]},
            "llm": [0.6],
            "empty": {"confidence_scores": []},
        },
    }

    GRAPH_MODULE._build_strategy_confidence_report(state)

    report = state["strategy_confidence_intervals"]
    assert report["rag"]["confidence_interval_available"] is True
    assert report["llm"]["confidence_interval_available"] is False
    assert report["empty"]["confidence_interval_available"] is False

    strategy_reporting = state["strategy_reporting"]
    assert strategy_reporting["confidence_intervals_included"] is True
    assert strategy_reporting["strategies_with_intervals"] == ["rag"]
    assert math.isclose(
        float(strategy_reporting["confidence_interval_level"]),
        0.9,
        rel_tol=1e-9,
    )


def test_build_strategy_confidence_report_noop_without_metrics() -> None:
    state = {"config": {"paper_validator_enabled": False}}
    GRAPH_MODULE._build_strategy_confidence_report(state)
    assert "strategy_confidence_intervals" not in state
    assert "strategy_reporting" not in state


def test_release_gate_criteria_validation_paths() -> None:
    bypass_state = {"release_gate_validation_required": False}
    assert GRAPH_MODULE._release_gate_criteria_valid(bypass_state) is True
    assert "release_gate_validation" not in bypass_state

    missing_state = {"release_gate_validation_required": True}
    assert GRAPH_MODULE._release_gate_criteria_valid(missing_state) is False
    assert missing_state["release_gate_validation"]["reason"] == "missing_release_gate_criteria"

    pass_state = {
        "release_gate_validation_required": True,
        "release_gate_criteria": [
            {"id": "ci", "passed": True},
            {"id": "quality", "met": True},
            {"id": "docs", "status": "passed"},
        ],
    }
    assert GRAPH_MODULE._release_gate_criteria_valid(pass_state) is True
    assert pass_state["release_gate_validation"]["passed"] is True
    assert pass_state["release_gate_validation"]["failed_criteria"] == []

    fail_state = {
        "release_gate_validation_required": True,
        "release_gate_criteria": [{"id": "ci", "passed": False}, "invalid"],
    }
    assert GRAPH_MODULE._release_gate_criteria_valid(fail_state) is False
    assert fail_state["release_gate_validation"]["reason"] == "criteria_not_met"
    assert fail_state["release_gate_validation"]["failed_criteria"] == ["ci", "criterion_1"]


def test_existing_graph_routes_and_release_gate_routing() -> None:
    assert GRAPH_MODULE._route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert GRAPH_MODULE._route_after_clarification({}) == "input_writer_node"

    assert GRAPH_MODULE._route_after_sweep_detection({"sweep_id": "sweep-1"}) == "sweep_execution_handler"
    assert GRAPH_MODULE._route_after_sweep_detection({}) == "architect_node"

    assert GRAPH_MODULE._paper_validator_enabled({"config": {"paper_validator_enabled": True}}) is True
    assert GRAPH_MODULE._paper_validator_enabled({"config": {"paper_validator_enabled": False}}) is False
    assert GRAPH_MODULE._paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True
    assert GRAPH_MODULE._paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=False)}) is False
    assert GRAPH_MODULE._paper_validator_enabled({}) is False

    assert (
        GRAPH_MODULE._route_after_architect(
            {"config": {"paper_validator_enabled": True}, "strategy_metrics": {"s": [0.1, 0.2]}}
        )
        == "paper_validator_node"
    )
    assert GRAPH_MODULE._route_after_architect({"config": {"paper_validator_enabled": False}}) == "intent_extraction_node"

    assert GRAPH_MODULE._route_after_paper_validator({"paper_validation_passed": False}) == "end"
    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": "## [F-003] Missing Mapping\nScope: docs only",
            }
        )
        == "end"
    )
    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {"paper_validation_passed": True, "feature_blocks_validation_required": True}
        )
        == "end"
    )
    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_validation_required": True,
                "feature_blocks_validation_passed": True,
                "claim_evidence_matrix_required": True,
            }
        )
        == "end"
    )

    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": "## [F-2]\nTests/Fixtures: tests/unit/test_ok.py",
                "claim_evidence_matrix_required": True,
                "claim_evidence_matrix_complete": True,
                "release_gate_validation_required": True,
                "release_gate_criteria": [{"id": "ci", "passed": False}],
            }
        )
        == "end"
    )
    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": "## [F-2]\nTests/Fixtures: tests/unit/test_ok.py",
                "claim_evidence_matrix_required": True,
                "claim_evidence_matrix_complete": True,
                "release_gate_validation_required": True,
                "release_gate_criteria": [
                    {"id": "ci", "passed": True},
                    {"id": "coverage", "status": "ok"},
                ],
            }
        )
        == "intent_extraction_node"
    )
    assert GRAPH_MODULE._route_after_paper_validator({"paper_validation_passed": True}) == "intent_extraction_node"

    clarification_state = {"clarification_questions": ["q1"]}
    sweep_state = {"sweep_id": "sweep-1", "sweep_parameter": "max_step"}
    assert GRAPH_MODULE.clarification_handler_node(clarification_state) is clarification_state
    assert GRAPH_MODULE.sweep_execution_handler_node(sweep_state) is sweep_state

    app = GRAPH_MODULE.create_graph().compile()
    graph_def = app.get_graph()
    nodes = set(graph_def.nodes.keys())
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert "architect_node" in nodes
    assert "paper_validator_node" in nodes
    assert "input_writer_node" in nodes
    assert ("__start__", "sweep_detection_node") in edges
    assert ("architect_node", "paper_validator_node") in edges
    assert ("architect_node", "intent_extraction_node") in edges
    assert ("paper_validator_node", "__end__") in edges
