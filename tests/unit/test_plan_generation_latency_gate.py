"""Tests for p95 planning-latency criterion wiring."""

from __future__ import annotations

from src.graph import (
    LEVEL4_DEPTH_GUIDANCE_ID,
    PLAN_GENERATION_P95_ID,
    _collect_plan_generation_latencies_seconds,
    _extract_plan_generation_latency_seconds,
    _p95_seconds,
    _paper_validator_mode2_enabled,
    _route_after_architect,
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
    plan_generation_p95_failure_reason,
    plan_generation_p95_handler_node,
    plan_generation_p95_passed,
    sweep_execution_handler_node,
)
from src.services.plan import GLOBAL_FUNCTION_COMPLEXITY_ID


def test_plan_generation_latency_extraction_and_p95_math():
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_seconds": 12}}) == 12.0
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_ms": 1500}}) == 1.5
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_seconds": -1}}) is None
    assert _extract_plan_generation_latency_seconds({"details": "invalid"}) is None

    assert _p95_seconds([]) is None
    assert _p95_seconds([1.0]) == 1.0
    assert _p95_seconds([1.0, 2.0, 3.0, 4.0]) == 4.0


def test_plan_generation_latency_collection_prefers_direct_values_and_history():
    assert _collect_plan_generation_latencies_seconds({"plan_generation_latencies_seconds": [1, 2.5, "x"]}) == [
        1.0,
        2.5,
    ]
    assert _collect_plan_generation_latencies_seconds({"plan_generation_latencies_seconds": []}) == []
    assert _collect_plan_generation_latencies_seconds({"workflow_history": "invalid"}) == []
    assert _collect_plan_generation_latencies_seconds(
        {
            "workflow_history": [
                "invalid",
                {"node": "reviewer", "details": {"plan_generation_latency_seconds": 1}},
                {"node": "architect", "details": {"plan_generation_latency_ms": 120000}},
                {"node": "architect", "details": {"plan_generation_latency_seconds": 90}},
            ]
        }
    ) == [120.0, 90.0]


def test_plan_generation_p95_gate_routes_and_reason_codes():
    approved = {
        "gate_approvals": [
            {"decision": "approved", "details": {"criterion": PLAN_GENERATION_P95_ID}},
        ]
    }
    assert plan_generation_p95_passed(approved) is True
    assert plan_generation_p95_failure_reason(approved) == "plan_generation_p95_satisfied"

    passing = {"plan_generation_latencies_seconds": [20, 50, 170]}
    assert plan_generation_p95_passed(passing) is True
    assert plan_generation_p95_failure_reason(passing) == "plan_generation_p95_satisfied"

    failing = {"plan_generation_latencies_seconds": [120, 181]}
    assert plan_generation_p95_passed(failing) is False
    assert plan_generation_p95_failure_reason(failing) == "plan_generation_p95_exceeded"
    assert _route_after_architect({**failing, "enforce_plan_generation_p95": True}) == (
        "plan_generation_p95_handler"
    )
    assert _route_after_architect({"enforce_plan_generation_p95": True, **passing}) == (
        "intent_extraction_node"
    )
    assert _route_after_architect({}) == "intent_extraction_node"

    assert plan_generation_p95_failure_reason({}) == "plan_generation_latency_missing"


def test_plan_generation_p95_handler_records_rejection_details():
    updates = plan_generation_p95_handler_node(
        {
            "gate_approvals": "invalid",
            "errors_active": ["plan_generation_p95_exceeded"],
            "plan_generation_latencies_seconds": [120, 181],
        }
    )
    assert updates["mode"] == "terminal"
    assert updates["reviewer_failure_category"] == "planning_latency_gate"
    assert updates["gate_approvals"][-1]["details"]["criterion"] == PLAN_GENERATION_P95_ID
    assert updates["gate_approvals"][-1]["details"]["p95_seconds"] == 181.0
    assert updates["errors_active"].count("plan_generation_p95_exceeded") == 1

    missing = plan_generation_p95_handler_node({"gate_approvals": [], "errors_active": "invalid"})
    assert missing["errors_active"] == ["plan_generation_latency_missing"]
    assert missing["gate_approvals"][-1]["details"]["p95_seconds"] is None


def test_existing_level4_and_complexity_gates_remain_wired():
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 80}]}) is True
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 120}]}) is True
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 79}]}) is False
    assert (
        level4_depth_guidance_passed(
            {
                "level4_depth_context": {"camera_ready_rigor": True},
                "level4_sections": [{"line_count": 600}],
            }
        )
        is True
    )
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": "90"}]}) is False
    assert level4_depth_guidance_failure_reason({}) == "level4_depth_guidance_missing"
    assert (
        level4_depth_guidance_failure_reason({"level4_sections": [{"line_count": 40}]})
        == "level4_depth_guidance_out_of_range"
    )

    assert _route_after_input_writer(
        {"enforce_level4_depth_guidance": True, "level4_sections": [{"line_count": 40}]}
    ) == "level4_depth_guidance_handler"
    assert _route_after_input_writer(
        {
            "enforce_level4_depth_guidance": True,
            "level4_sections": [{"line_count": 95}],
            "enforce_global_function_complexity": True,
            "global_complexity_report": {"passes": False},
        }
    ) == "global_function_complexity_handler"
    assert _route_after_input_writer(
        {
            "enforce_level4_depth_guidance": True,
            "level4_sections": [{"line_count": 95}],
            "enforce_global_function_complexity": True,
            "global_complexity_report": {"passes": True},
            "paper_validator_enabled": True,
            "validation_manifest": {"ok": True},
        }
    ) == "paper_validator_node"
    assert _route_after_input_writer({}) == "end"

    level4_updates = level4_depth_guidance_handler_node(
        {"gate_approvals": "invalid", "errors_active": "invalid", "level4_sections": [{"line_count": 5}]}
    )
    assert level4_updates["reviewer_failure_category"] == "depth_guidance_gate"
    assert level4_updates["gate_approvals"][-1]["details"]["criterion"] == LEVEL4_DEPTH_GUIDANCE_ID
    assert level4_updates["errors_active"] == ["level4_depth_guidance_out_of_range"]

    complexity_updates = global_function_complexity_handler_node(
        {"gate_approvals": "invalid", "errors_active": "invalid", "global_complexity_report": {"passes": False}}
    )
    assert complexity_updates["reviewer_failure_category"] == "complexity_gate"
    assert complexity_updates["gate_approvals"][-1]["details"]["criterion"] == (
        GLOBAL_FUNCTION_COMPLEXITY_ID
    )
    assert complexity_updates["errors_active"] == ["global_function_complexity_threshold_exceeded"]


def test_existing_routes_and_placeholders_cover_remaining_branches():
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({}) == "input_writer_node"

    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": "s1"}) == (
        "sweep_execution_handler"
    )
    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": None}) == (
        "architect_node"
    )
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"

    assert _paper_validator_mode2_enabled({"paper_validator_enabled": True}) is True
    assert _paper_validator_mode2_enabled({"config": {"paper_validator_enabled": True}}) is True

    class Cfg:
        paper_validator_enabled = True

    assert _paper_validator_mode2_enabled({"config": Cfg()}) is True
    assert _paper_validator_mode2_enabled({}) is False

    state = {"clarification_questions": ["q"], "sweep_id": "s1", "sweep_parameter": "x"}
    assert clarification_handler_node(state) is state
    assert sweep_execution_handler_node(state) is state

    dep_updates = feature_a_dependency_handler_node({"gate_approvals": "invalid", "errors_active": "invalid"})
    assert dep_updates["reviewer_failure_category"] == "dependency_gate"
    assert dep_updates["errors_active"] == ["feature_a_dependency_unverified"]


def test_create_graph_wires_p95_and_existing_handlers():
    graph = create_graph().compile().get_graph()
    nodes = set(graph.nodes)
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert "plan_generation_p95_handler" in nodes
    assert ("architect_node", "plan_generation_p95_handler") in edges
    assert ("plan_generation_p95_handler", "__end__") in edges

    assert "level4_depth_guidance_handler" in nodes
    assert ("input_writer_node", "level4_depth_guidance_handler") in edges
    assert ("level4_depth_guidance_handler", "__end__") in edges
