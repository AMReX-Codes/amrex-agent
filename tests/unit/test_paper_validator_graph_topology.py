"""Paper validator graph topology tests."""

from __future__ import annotations

from src.graph import (
    _route_after_clarification,
    _route_after_sweep_detection,
    create_graph,
    paper_validator_node,
    session_dependency_handler_node,
)


def test_paper_validator_node_in_graph() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()
    assert "paper_validator_node" in graph_def.nodes


def test_paper_validator_wiring() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()
    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("clarification_node", "paper_validator_node") in edges
    assert ("paper_validator_node", "input_writer_node") in edges


def test_clarification_routes_to_writer_when_validator_disabled() -> None:
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"
    assert _route_after_clarification(
        {"clarification_needed": False, "paper_validator_enabled": False}
    ) == "input_writer_node"
    assert _route_after_clarification({}) == "input_writer_node"


def test_clarification_routes_to_paper_validator_when_enabled() -> None:
    assert _route_after_clarification(
        {"clarification_needed": False, "paper_validator_enabled": True}
    ) == "paper_validator_node"


def test_clarification_needed_routes_to_handler() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"


def test_no_sweep_routes_to_architect() -> None:
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"
    assert _route_after_sweep_detection({}) == "architect_node"


def test_sweep_routes_to_dependency_handler_when_incomplete(monkeypatch) -> None:
    monkeypatch.setattr("src.graph.is_session_dependency_complete", lambda state: False)
    assert _route_after_sweep_detection({"sweep_id": "sweep_001"}) == "session_dependency_handler"


def test_sweep_routes_to_execution_handler_when_complete(monkeypatch) -> None:
    monkeypatch.setattr("src.graph.is_session_dependency_complete", lambda state: True)
    assert _route_after_sweep_detection({"sweep_id": "sweep_001"}) == "sweep_execution_handler"


def test_session_dependency_handler_node_sets_defaults() -> None:
    result = session_dependency_handler_node({})
    assert "dependency_error" in result
    assert "required_marker" in result


def test_session_dependency_handler_node_preserves_existing_values() -> None:
    seed = {"dependency_error": "existing", "required_marker": "marker"}
    result = session_dependency_handler_node(seed)
    assert result["dependency_error"] == "existing"
    assert result["required_marker"] == "marker"


def test_paper_validator_node_passthrough() -> None:
    state = {"paper_validator_enabled": True}
    assert paper_validator_node(state) == state
