"""Unit tests for confidence intervals in strategy reporting."""

from __future__ import annotations

import math
import sys
from types import SimpleNamespace

from src.graph import (
    _build_strategy_confidence_report,
    _extract_strategy_samples,
    _get_z_score,
    _paper_validator_enabled,
    _route_after_clarification,
    _route_after_paper_validator,
    _route_after_sweep_detection,
    clarification_handler_node,
    _route_after_architect,
    create_graph,
    compute_confidence_interval,
    sweep_execution_handler_node,
)

# Coverage compatibility for file-path based coverage targets.
sys.modules["src/graph.py"] = sys.modules["src.graph"]


def test_compute_confidence_interval_for_multiple_samples() -> None:
    result = compute_confidence_interval([0.7, 0.8, 0.9], confidence_level=0.95)

    assert result["confidence_interval_available"] is True
    assert result["sample_size"] == 3
    assert math.isclose(float(result["mean"]), 0.8, rel_tol=1e-9)
    assert float(result["lower_bound"]) < 0.8
    assert float(result["upper_bound"]) > 0.8
    assert math.isclose(float(result["confidence_level"]), 0.95, rel_tol=1e-9)


def test_compute_confidence_interval_handles_empty_samples() -> None:
    result = compute_confidence_interval([])

    assert result["confidence_interval_available"] is False
    assert result["sample_size"] == 0
    assert result["mean"] is None
    assert result["lower_bound"] is None
    assert result["upper_bound"] is None


def test_compute_confidence_interval_single_sample_no_interval() -> None:
    result = compute_confidence_interval([0.42])

    assert result["confidence_interval_available"] is False
    assert result["sample_size"] == 1
    assert math.isclose(float(result["mean"]), 0.42, rel_tol=1e-9)
    assert math.isclose(float(result["lower_bound"]), 0.42, rel_tol=1e-9)
    assert math.isclose(float(result["upper_bound"]), 0.42, rel_tol=1e-9)


def test_get_z_score_supports_common_levels_and_default() -> None:
    assert math.isclose(_get_z_score(0.90), 1.645, rel_tol=1e-9)
    assert math.isclose(_get_z_score(0.95), 1.96, rel_tol=1e-9)
    assert math.isclose(_get_z_score(0.99), 2.576, rel_tol=1e-9)
    assert math.isclose(_get_z_score(0.83), 1.96, rel_tol=1e-9)


def test_extract_strategy_samples_filters_non_numeric_entries() -> None:
    assert _extract_strategy_samples({"confidence_scores": [1, "x", 0.5]}) == [1.0, 0.5]
    assert _extract_strategy_samples([0.1, None, 2]) == [0.1, 2.0]
    assert _extract_strategy_samples("invalid") == []


def test_build_strategy_confidence_report_includes_where_available() -> None:
    state = {
        "strategy_confidence_level": 0.9,
        "strategy_metrics": {
            "rag": {"confidence_scores": [0.5, 0.7, 0.9]},
            "llm": [0.6],
            "empty": {"confidence_scores": []},
        },
    }

    _build_strategy_confidence_report(state)

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


def test_build_strategy_confidence_report_no_metrics_noop() -> None:
    state = {"config": {"paper_validator_enabled": False}}
    _build_strategy_confidence_report(state)
    assert "strategy_confidence_intervals" not in state
    assert "strategy_reporting" not in state


def test_route_after_architect_builds_report_and_routes() -> None:
    state = {
        "config": {"paper_validator_enabled": False},
        "strategy_metrics": {"baseline": [0.2, 0.4, 0.6, 0.8]},
    }

    route = _route_after_architect(state)

    assert route == "intent_extraction_node"
    assert "strategy_confidence_intervals" in state
    assert state["strategy_confidence_intervals"]["baseline"]["confidence_interval_available"] is True


def test_existing_graph_routes_and_wiring_still_hold() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({}) == "input_writer_node"

    assert _route_after_sweep_detection({"sweep_id": "sweep-1"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({}) == "architect_node"

    assert _paper_validator_enabled({"config": {"paper_validator_enabled": True}}) is True
    assert _paper_validator_enabled({"config": {"paper_validator_enabled": False}}) is False
    assert _paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True
    assert _paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=False)}) is False
    assert _paper_validator_enabled({}) is False

    assert (
        _route_after_architect(
            {"config": {"paper_validator_enabled": True}, "strategy_metrics": {"s": [0.1, 0.2]}}
        )
        == "paper_validator_node"
    )
    assert _route_after_architect({"config": {"paper_validator_enabled": False}}) == "intent_extraction_node"

    assert _route_after_paper_validator({"paper_validation_passed": False}) == "end"
    assert (
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": "## [F-003] Missing Mapping\nScope: docs only",
            }
        )
        == "end"
    )
    assert (
        _route_after_paper_validator(
            {"paper_validation_passed": True, "feature_blocks_validation_required": True}
        )
        == "end"
    )
    assert (
        _route_after_paper_validator(
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
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": "## [F-2]\nTests/Fixtures: tests/unit/test_ok.py",
                "claim_evidence_matrix_required": True,
                "claim_evidence_matrix_complete": True,
            }
        )
        == "intent_extraction_node"
    )
    assert _route_after_paper_validator({"paper_validation_passed": True}) == "intent_extraction_node"

    clarification_state = {"clarification_questions": ["q1"]}
    sweep_state = {"sweep_id": "sweep-1", "sweep_parameter": "max_step"}
    assert clarification_handler_node(clarification_state) is clarification_state
    assert sweep_execution_handler_node(sweep_state) is sweep_state

    app = create_graph().compile()
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
