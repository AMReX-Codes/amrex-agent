"""Feature traceability gate tests."""

from __future__ import annotations

from src.graph import (
    PHASE1_FEATURE_TRACE_MARKER,
    _has_phase1_feature_trace,
    _paper_validator_enabled,
    _route_after_clarification,
    _route_after_complexity_evidence,
    _route_after_paper_validator,
    _route_after_phase1_traceability,
    _route_after_sweep_detection,
    clarification_handler_node,
    complexity_evidence_handler_node,
    complexity_evidence_node,
    create_graph,
    paper_validator_node,
    phase1_traceability_handler_node,
    session_dependency_handler_node,
    sweep_execution_handler_node,
)
from src.session_manager import SESSION_DEPENDENCY_COMPLETION_MARKER


def test_phase1_traceability_gate_and_graph_routes(monkeypatch):
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
    assert _route_after_sweep_detection({"sweep_id": "sweep"}) == "session_dependency_handler"
    assert _route_after_sweep_detection(
        {"sweep_id": "sweep", "session_markers": {SESSION_DEPENDENCY_COMPLETION_MARKER: True}}
    ) == "sweep_execution_handler"

    assert _has_phase1_feature_trace({}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: "invalid"}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"BAD": ["F1.1"]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": []}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": [1]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": ["X1"]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": "F1.1"}}) is True
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC2": ["F2B", "F6.2"]}}) is True

    assert _route_after_phase1_traceability({}) == "end"
    assert (
        _route_after_phase1_traceability({"enforce_phase1_feature_trace": True})
        == "phase1_traceability_handler"
    )
    assert (
        _route_after_phase1_traceability(
            {
                "enforce_phase1_feature_trace": True,
                PHASE1_FEATURE_TRACE_MARKER: {"UC1": ["F1.1"], "UC2": "F2B"},
            }
        )
        == "end"
    )

    assert _route_after_complexity_evidence({}) == "end"
    assert (
        _route_after_complexity_evidence(
            {
                "enforce_phase1_feature_trace": True,
                PHASE1_FEATURE_TRACE_MARKER: {"UC1": ["F1.1"]},
            }
        )
        == "end"
    )
    assert (
        _route_after_complexity_evidence({"enforce_phase1_feature_trace": True})
        == "phase1_traceability_handler"
    )
    assert (
        _route_after_complexity_evidence({"enforce_radon_complexity_evidence": True})
        == "complexity_evidence_handler"
    )
    assert (
        _route_after_complexity_evidence(
            {
                "enforce_radon_complexity_evidence": True,
                "radon_complexity_evidence": {"radon_available": True},
            }
        )
        == "end"
    )

    assert session_dependency_handler_node({})["required_marker"] == SESSION_DEPENDENCY_COMPLETION_MARKER

    enforced = complexity_evidence_node({"enforce_radon_complexity_evidence": True})
    assert enforced["radon_complexity_evidence"]["radon_available"] is False

    unchanged = complexity_evidence_node({"enforce_radon_complexity_evidence": False})
    assert "radon_complexity_evidence" not in unchanged

    existing = complexity_evidence_node(
        {
            "enforce_radon_complexity_evidence": True,
            "radon_complexity_evidence": {"radon_available": True},
        }
    )
    assert existing["radon_complexity_evidence"]["radon_available"] is True

    handler = complexity_evidence_handler_node({"enforce_radon_complexity_evidence": True})
    assert handler["required_marker"] == "radon_complexity_evidence"
    assert "Radon complexity evidence" in handler["dependency_error"]

    handler_with_existing = complexity_evidence_handler_node(
        {"radon_complexity_evidence": {"radon_available": True}}
    )
    assert handler_with_existing["radon_complexity_evidence"]["radon_available"] is True

    trace_handler = phase1_traceability_handler_node({})
    assert trace_handler["required_marker"] == PHASE1_FEATURE_TRACE_MARKER
    assert "traceability is required" in trace_handler["dependency_error"]

    assert clarification_handler_node({"clarification_questions": ["q1"]}) == {"clarification_questions": ["q1"]}
    assert sweep_execution_handler_node({"sweep_id": "id", "sweep_parameter": "p"})["sweep_id"] == "id"
    state = {"x": 1}
    assert paper_validator_node(state) is state

    app = create_graph().compile()
    graph_def = app.get_graph()
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert ("input_writer_node", "complexity_evidence_node") in edges
    assert ("complexity_evidence_node", "complexity_evidence_handler") in edges
    assert ("complexity_evidence_node", "phase1_traceability_handler") in edges
    assert ("complexity_evidence_node", "__end__") in edges
    assert ("complexity_evidence_handler", "__end__") in edges
    assert ("phase1_traceability_handler", "__end__") in edges
