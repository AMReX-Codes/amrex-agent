"""Unit tests for paper-validator mode 1 behavior."""

from __future__ import annotations

from types import SimpleNamespace

from src.graph import (
    _paper_validator_enabled,
    _route_after_architect,
    _route_after_clarification,
    _route_after_paper_validator,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    sweep_execution_handler_node,
)
from src.nodes.paper_validator_node import paper_validator_node


def test_mode1_fails_when_plan_missing() -> None:
    updates = paper_validator_node({})

    assert updates["paper_validation_passed"] is False
    assert updates["paper_validation_reason"] == "missing_plan"
    assert updates["paper_validator_mode1_complete"] is False
    assert "validation_manifest" not in updates


def test_mode1_fails_when_paper_design_missing() -> None:
    updates = paper_validator_node({"plan": {}})

    assert updates["paper_validation_passed"] is False
    assert updates["paper_validation_reason"] == "missing_paper_design"
    assert updates["paper_validator_mode1_complete"] is False


def test_mode1_fails_when_sections_missing_and_not_deferred() -> None:
    updates = paper_validator_node({"plan": {"paper_design": {"deferred": False}}})

    assert updates["paper_validation_passed"] is False
    assert updates["paper_validation_reason"] == "missing_sections"
    assert updates["paper_validation_status"] == "failed"


def test_mode1_deferred_design_marks_mode_complete() -> None:
    updates = paper_validator_node({"plan": {"paper_design": {"deferred": True}}})

    assert updates["paper_validation_passed"] is True
    assert updates["paper_validation_status"] == "deferred"
    assert updates["paper_validation_reason"] == "design_deferred"
    assert updates["paper_validator_mode1_complete"] is True
    assert updates["validation_manifest"]["paper_input_type"] == "pdf"


def test_mode1_passes_and_builds_manifest_for_single_condition() -> None:
    state = {
        "paper_source": "1234.5678",
        "paper_input_type": "arxiv",
        "plan": {
            "paper_design": {
                "sections": ["overview"],
                "base_resolved_config": {"amr.n_cell": "128 128 128"},
                "sweep_parameter": "amr.n_cell",
            }
        },
    }

    updates = paper_validator_node(state)

    assert updates["paper_validation_passed"] is True
    assert updates["paper_validator_mode1_complete"] is True
    assert updates["resolved_config"] == {"amr.n_cell": "128 128 128"}

    manifest = updates["validation_manifest"]
    assert manifest["paper_source"] == "1234.5678"
    assert manifest["paper_input_type"] == "arxiv"
    assert manifest["is_sweep"] is False
    assert manifest["conditions"] == [{"amr.n_cell": "128 128 128"}]


def test_mode1_detects_sweep_when_multiple_conditions_present() -> None:
    state = {
        "resolved_config": {"max_step": 10},
        "plan": {
            "paper_design": {
                "sections": ["results"],
                "conditions": [
                    {"max_step": 10},
                    {"max_step": 20},
                ],
                "sweep_parameter": "max_step",
            }
        },
    }

    updates = paper_validator_node(state)

    manifest = updates["validation_manifest"]
    assert manifest["is_sweep"] is True
    assert manifest["conditions"] == [{"max_step": 10}, {"max_step": 20}]
    assert manifest["sweep_parameter"] == "max_step"
    assert updates["resolved_config"] == {"max_step": 10}


def test_graph_routes_cover_all_paths() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"

    assert _route_after_sweep_detection({"sweep_id": "sweep-1"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"

    assert _route_after_architect({"config": {"paper_validator_enabled": True}}) == "paper_validator_node"
    assert _route_after_architect({"config": {"paper_validator_enabled": False}}) == "intent_extraction_node"

    assert _route_after_paper_validator({"paper_validation_passed": True}) == "intent_extraction_node"
    assert _route_after_paper_validator({"paper_validation_passed": False}) == "end"


def test_paper_validator_enabled_supports_dict_and_object() -> None:
    assert _paper_validator_enabled({}) is False
    assert _paper_validator_enabled({"config": {}}) is False
    assert _paper_validator_enabled({"config": {"paper_validator_enabled": True}}) is True
    assert _paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True


def test_existing_handlers_and_graph_wiring_work() -> None:
    clarification_state = {"clarification_questions": ["q1"]}
    sweep_state = {"sweep_id": "sweep-1", "sweep_parameter": "max_step"}

    assert clarification_handler_node(clarification_state) is clarification_state
    assert sweep_execution_handler_node(sweep_state) is sweep_state

    app = create_graph().compile()
    graph_def = app.get_graph()
    nodes = set(graph_def.nodes.keys())
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert "paper_validator_node" in nodes
    assert ("architect_node", "paper_validator_node") in edges
    assert ("architect_node", "intent_extraction_node") in edges
    assert ("paper_validator_node", "intent_extraction_node") in edges
    assert ("paper_validator_node", "__end__") in edges
