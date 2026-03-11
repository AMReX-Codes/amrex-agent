"""Session 27: UNNUMBERED-056 required behavior checklist tests."""

from __future__ import annotations

from src.graph import (
    PHASE1_FEATURE_TRACE_MARKER,
    REQUIRED_BEHAVIOR_MARKER,
    _has_phase1_feature_trace,
    _has_required_behavior_item,
    _paper_validator_enabled,
    _route_after_clarification,
    _route_after_complexity_evidence,
    _route_after_paper_validator,
    _route_after_phase1_traceability,
    _route_after_required_behavior_item,
    _route_after_sweep_detection,
    clarification_handler_node,
    complexity_evidence_handler_node,
    complexity_evidence_node,
    create_graph,
    paper_validator_node,
    phase1_traceability_handler_node,
    required_behavior_handler_node,
    session_dependency_handler_node,
    sweep_execution_handler_node,
)
from src.session_manager import B1_SESSION_COMPLETION_MARKER


def test_required_behavior_item_gate_and_graph_routes(monkeypatch):
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
        {"sweep_id": "sweep", "session_markers": {B1_SESSION_COMPLETION_MARKER: True}}
    ) == "sweep_execution_handler"

    assert _has_phase1_feature_trace({}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: "invalid"}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"BAD": ["F1.1"]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": []}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": [1]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": ["X1"]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": "F1.1"}}) is True
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC2": ["F2B", "F6.2"]}}) is True

    assert _has_required_behavior_item({}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ""}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: "   "}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: 1}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: []}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ["ok", ""]}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: "must be true"}) is True
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ["must", "be true"]}) is True

    assert _route_after_required_behavior_item({}) == "end"
    assert (
        _route_after_required_behavior_item({"enforce_required_behavior_item": True})
        == "required_behavior_handler"
    )
    assert (
        _route_after_required_behavior_item(
            {
                "enforce_required_behavior_item": True,
                REQUIRED_BEHAVIOR_MARKER: "must be true",
            }
        )
        == "end"
    )

    assert _route_after_phase1_traceability({}) == "end"
    assert (
        _route_after_phase1_traceability({"enforce_phase1_feature_trace": True})
        == "phase1_traceability_handler"
    )
    assert (
        _route_after_phase1_traceability(
            {
                "enforce_phase1_feature_trace": True,
                PHASE1_FEATURE_TRACE_MARKER: {"UC1": "F1.1"},
            }
        )
        == "end"
    )
    assert (
        _route_after_phase1_traceability({"enforce_required_behavior_item": True})
        == "required_behavior_handler"
    )

    assert _route_after_complexity_evidence({}) == "end"
    assert (
        _route_after_complexity_evidence({"enforce_required_behavior_item": True})
        == "required_behavior_handler"
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
    assert (
        _route_after_complexity_evidence(
            {
                "enforce_radon_complexity_evidence": True,
                "radon_complexity_evidence": {"radon_available": True},
                "enforce_required_behavior_item": True,
                REQUIRED_BEHAVIOR_MARKER: "must be true",
            }
        )
        == "end"
    )

    assert session_dependency_handler_node({})["required_marker"] == B1_SESSION_COMPLETION_MARKER

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

    complexity_handler = complexity_evidence_handler_node({})
    assert complexity_handler["required_marker"] == "radon_complexity_evidence"
    assert "Radon complexity evidence" in complexity_handler["dependency_error"]

    complexity_handler_with_existing = complexity_evidence_handler_node(
        {"radon_complexity_evidence": {"radon_available": True}}
    )
    assert complexity_handler_with_existing["radon_complexity_evidence"]["radon_available"] is True

    phase1_handler = phase1_traceability_handler_node({})
    assert phase1_handler["required_marker"] == PHASE1_FEATURE_TRACE_MARKER
    assert "traceability is required" in phase1_handler["dependency_error"]

    handler = required_behavior_handler_node({})
    assert handler["required_marker"] == REQUIRED_BEHAVIOR_MARKER
    assert "required behavior item is required" in handler["dependency_error"]

    handler_with_existing = required_behavior_handler_node(
        {
            "required_marker": "existing_marker",
            "dependency_error": "existing error",
        }
    )
    assert handler_with_existing["required_marker"] == "existing_marker"
    assert handler_with_existing["dependency_error"] == "existing error"

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
    assert ("complexity_evidence_node", "required_behavior_handler") in edges
    assert ("complexity_evidence_handler", "__end__") in edges
    assert ("phase1_traceability_handler", "__end__") in edges
    assert ("required_behavior_handler", "__end__") in edges
