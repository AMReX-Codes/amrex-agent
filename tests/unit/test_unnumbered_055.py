"""Session 26 tests for level-4 depth guidance criterion wiring."""

from __future__ import annotations

from src.graph import (
    LEVEL4_DEPTH_GUIDANCE_ID,
    _paper_validator_mode2_enabled,
    _route_after_clarification,
    _route_after_input_writer,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    feature_a_dependency_handler_node,
    global_function_complexity_handler_node,
    level4_depth_guidance_failure_reason,
    level4_depth_guidance_handler_node,
    level4_depth_guidance_passed,
    sweep_execution_handler_node,
)
from src.services.plan import GLOBAL_FUNCTION_COMPLEXITY_ID


def test_level4_depth_guidance_baseline_and_expansion_ranges():
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 80}]}) is True
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 120}]}) is True
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 79}]}) is False
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 121}]}) is False

    expanded = {
        "level4_depth_context": {"high_complexity": True},
        "level4_sections": [{"line_count": 500}, {"line_count": 1000}],
    }
    assert level4_depth_guidance_passed(expanded) is True
    assert level4_depth_guidance_passed({**expanded, "level4_sections": [{"line_count": 499}]}) is False
    assert (
        level4_depth_guidance_passed(
            {
                "level4_sections": [{"line_count": 600, "near_implementation": True}],
            }
        )
        is True
    )
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": "90"}]}) is False
    assert level4_depth_guidance_passed({"level4_sections": ["invalid"]}) is False


def test_level4_depth_guidance_approval_override_and_reason_codes():
    approved = {
        "gate_approvals": [
            {
                "decision": "approved",
                "details": {"criterion": LEVEL4_DEPTH_GUIDANCE_ID},
            }
        ],
    }
    assert level4_depth_guidance_passed(approved) is True
    assert level4_depth_guidance_failure_reason(approved) == "level4_depth_guidance_satisfied"

    assert level4_depth_guidance_failure_reason({}) == "level4_depth_guidance_missing"
    assert (
        level4_depth_guidance_failure_reason({"level4_sections": [{"line_count": 25}]})
        == "level4_depth_guidance_out_of_range"
    )
    assert (
        level4_depth_guidance_passed(
            {
                "gate_approvals": [
                    "invalid",
                    {"decision": "rejected", "details": {"criterion": LEVEL4_DEPTH_GUIDANCE_ID}},
                    {"decision": "approved", "details": "invalid"},
                ],
                "level4_sections": [{"line_count": 100}],
            }
        )
        is True
    )


def test_graph_routes_include_level4_depth_gate():
    blocked = _route_after_input_writer(
        {"enforce_level4_depth_guidance": True, "level4_sections": [{"line_count": 40}]}
    )
    assert blocked == "level4_depth_guidance_handler"

    complexity_blocked = _route_after_input_writer(
        {
            "enforce_level4_depth_guidance": True,
            "level4_sections": [{"line_count": 95}],
            "enforce_global_function_complexity": True,
            "global_complexity_report": {"passes": False},
        }
    )
    assert complexity_blocked == "global_function_complexity_handler"

    assert (
        _route_after_input_writer(
            {
                "enforce_level4_depth_guidance": True,
                "level4_depth_context": {"near_implementation": True},
                "level4_sections": [{"line_count": 600}],
                "paper_validator_enabled": True,
                "validation_manifest": {"ok": True},
            }
        )
        == "paper_validator_node"
    )
    assert _route_after_input_writer({}) == "end"
    assert (
        _route_after_input_writer(
            {
                "enforce_global_function_complexity": True,
                "global_complexity_report": {"passes": True},
            }
        )
        == "end"
    )


def test_level4_and_existing_gate_handlers_record_rejections():
    level4_updates = level4_depth_guidance_handler_node(
        {
            "gate_approvals": "invalid",
            "errors_active": ["level4_depth_guidance_out_of_range"],
            "level4_sections": [{"line_count": 12}],
        }
    )
    assert level4_updates["mode"] == "terminal"
    assert level4_updates["reviewer_failure_category"] == "depth_guidance_gate"
    assert level4_updates["gate_approvals"][-1]["details"]["criterion"] == LEVEL4_DEPTH_GUIDANCE_ID
    assert level4_updates["errors_active"].count("level4_depth_guidance_out_of_range") == 1

    dep_updates = feature_a_dependency_handler_node(
        {"gate_approvals": "invalid", "errors_active": "invalid"}
    )
    assert dep_updates["reviewer_failure_category"] == "dependency_gate"
    assert dep_updates["errors_active"] == ["feature_a_dependency_unverified"]

    complexity_updates = global_function_complexity_handler_node(
        {
            "gate_approvals": "invalid",
            "errors_active": "invalid",
            "global_complexity_report": {"passes": False},
        }
    )
    assert complexity_updates["reviewer_failure_category"] == "complexity_gate"
    assert complexity_updates["gate_approvals"][-1]["details"]["criterion"] == (
        GLOBAL_FUNCTION_COMPLEXITY_ID
    )
    assert complexity_updates["errors_active"] == ["global_function_complexity_threshold_exceeded"]

    level4_again = level4_depth_guidance_handler_node(
        {
            "gate_approvals": [],
            "errors_active": [],
            "level4_sections": [{"line_count": 5}],
        }
    )
    assert level4_again["errors_active"] == ["level4_depth_guidance_out_of_range"]


def test_graph_routes_and_placeholder_nodes_cover_existing_branches():
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({}) == "input_writer_node"

    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": "s1"}) == (
        "sweep_execution_handler"
    )
    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": None}) == (
        "architect_node"
    )
    assert _route_after_sweep_detection({"sweep_id": None}) == "feature_a_dependency_handler"

    assert _paper_validator_mode2_enabled({"paper_validator_enabled": True}) is True
    assert _paper_validator_mode2_enabled({"config": {"paper_validator_enabled": True}}) is True

    class Cfg:
        paper_validator_enabled = True

    assert _paper_validator_mode2_enabled({"config": Cfg()}) is True
    assert _paper_validator_mode2_enabled({}) is False

    state = {"clarification_questions": ["q"], "sweep_id": "s1", "sweep_parameter": "x"}
    assert clarification_handler_node(state) is state
    assert sweep_execution_handler_node(state) is state


def test_create_graph_wires_level4_handler():
    graph = create_graph().compile().get_graph()
    nodes = set(graph.nodes)
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert "level4_depth_guidance_handler" in nodes
    assert ("input_writer_node", "level4_depth_guidance_handler") in edges
    assert ("level4_depth_guidance_handler", "__end__") in edges
