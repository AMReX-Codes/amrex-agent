"""Unit tests for deferred paper-design validation behavior."""

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
    paper_validator_node,
    sweep_execution_handler_node,
)
from src.services.paper_validator import PaperValidator


def test_paper_validator_fails_without_plan() -> None:
    result = PaperValidator().validate({})
    assert result["paper_validation_passed"] is False
    assert result["paper_validation_reason"] == "missing_plan"
    assert result["paper_validation_status"] == "failed"


def test_paper_validator_fails_without_design() -> None:
    result = PaperValidator().validate({"plan": {}})
    assert result["paper_validation_passed"] is False
    assert result["paper_validation_reason"] == "missing_paper_design"


def test_paper_validator_passes_when_deferred() -> None:
    state = {"plan": {"paper_design": {"deferred": True}}}
    result = PaperValidator().validate(state)
    assert result["paper_validation_passed"] is True
    assert result["paper_validation_status"] == "deferred"
    assert result["paper_design_deferred"] is True


def test_paper_validator_fails_without_sections_when_not_deferred() -> None:
    state = {"plan": {"paper_design": {"deferred": False}}}
    result = PaperValidator().validate(state)
    assert result["paper_validation_passed"] is False
    assert result["paper_validation_reason"] == "missing_sections"


def test_paper_validator_passes_with_sections() -> None:
    state = {"plan": {"paper_design": {"sections": ["overview"]}}}
    result = PaperValidator().validate(state)
    assert result["paper_validation_passed"] is True
    assert result["paper_validation_status"] == "passed"
    assert result["paper_validation_reason"] == "ok"


def test_paper_validator_enabled_defaults_false() -> None:
    assert _paper_validator_enabled({}) is False
    assert _paper_validator_enabled({"config": {}}) is False


def test_paper_validator_enabled_true_for_dict_or_object() -> None:
    assert _paper_validator_enabled({"config": {"paper_validator_enabled": True}}) is True
    assert _paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True


def test_route_after_architect_when_feature_disabled() -> None:
    route = _route_after_architect({"config": {"paper_validator_enabled": False}})
    assert route == "intent_extraction_node"


def test_route_after_architect_when_feature_enabled() -> None:
    route = _route_after_architect({"config": {"paper_validator_enabled": True}})
    assert route == "paper_validator_node"


def test_route_after_paper_validator_handles_both_paths() -> None:
    assert _route_after_paper_validator({"paper_validation_passed": True}) == "intent_extraction_node"
    assert _route_after_paper_validator({"paper_validation_passed": False}) == "end"


def test_existing_clarification_and_sweep_routes_unchanged() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"
    assert _route_after_sweep_detection({"sweep_id": "sweep-1"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"


def test_existing_handler_nodes_return_state() -> None:
    clarification_state = {"clarification_questions": ["q1"], "clarification_needed": True}
    sweep_state = {"sweep_id": "sweep-1", "sweep_parameter": "max_step"}
    assert clarification_handler_node(clarification_state) is clarification_state
    assert sweep_execution_handler_node(sweep_state) is sweep_state


def test_paper_validator_node_returns_validation_payload() -> None:
    state = {"plan": {"paper_design": {"sections": ["methods"]}}}
    updates = paper_validator_node(state)
    assert updates["paper_validation_passed"] is True
    assert updates["paper_validation_status"] == "passed"


def test_graph_compiles_with_paper_validator_wiring() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()
    nodes = set(graph_def.nodes.keys())
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert "paper_validator_node" in nodes
    assert ("architect_node", "paper_validator_node") in edges
    assert ("architect_node", "intent_extraction_node") in edges
    assert ("paper_validator_node", "intent_extraction_node") in edges
    assert ("paper_validator_node", "__end__") in edges
