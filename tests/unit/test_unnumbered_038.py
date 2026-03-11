"""Session 76 tests for UC row traceable artifact criterion wiring."""

from __future__ import annotations

import sys

import src.graph as _graph_module
from src.graph import (
    LEVEL4_DEPTH_GUIDANCE_ID,
    PLAN_GENERATION_P95_ID,
    STABLE_ERROR_TAXONOMY_ID,
    STABLE_ERROR_TAXONOMY_VERSION,
    UC_ROW_TRACEABLE_ARTIFACT_ID,
    _collect_plan_generation_latencies_seconds,
    _error_reason_codes_from_gate_approvals,
    _error_reason_codes_from_state,
    _extract_plan_generation_latency_seconds,
    _p95_seconds,
    _paper_validator_mode2_enabled,
    _route_after_architect,
    _route_after_clarification,
    _route_after_input_writer,
    _route_after_sweep_detection,
    _uc_row_has_traceable_artifact,
    _uc_rows_from_state,
    amendment_module_loc_handler_node,
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
    stable_error_taxonomy_failure_reason,
    stable_error_taxonomy_handler_node,
    stable_error_taxonomy_passed,
    sweep_execution_handler_node,
    uc_row_traceable_artifact_failure_reason,
    uc_row_traceable_artifact_handler_node,
    uc_row_traceable_artifact_passed,
)
from src.services.plan import AMENDMENT_MODULE_LOC_ID, GLOBAL_FUNCTION_COMPLEXITY_ID

sys.modules.setdefault("src/graph.py", _graph_module)


def test_uc_row_traceability_helpers_and_pass_fail_logic():
    assert _uc_rows_from_state({"uc_rows": [{"artifact_link": "a"}, "bad"]}) == [{"artifact_link": "a"}]
    assert _uc_rows_from_state({"uc_traceability_rows": [{"artifact_link": "b"}]}) == [
        {"artifact_link": "b"}
    ]
    assert _uc_rows_from_state({"use_case_rows": [{"artifact_link": "c"}]}) == [{"artifact_link": "c"}]
    assert _uc_rows_from_state({"uc_rows": "invalid"}) == []

    assert _uc_row_has_traceable_artifact({"artifact_link": "tests/unit/test_foo.py"}) is True
    assert _uc_row_has_traceable_artifact({"artifact_link": "  "}) is False
    assert _uc_row_has_traceable_artifact({"artifact_link": "x", "artifact_status": "stale"}) is False
    assert _uc_row_has_traceable_artifact({"artifact_link": "x", "artifact_current": False}) is False

    approved = {
        "gate_approvals": [{"decision": "approved", "details": {"criterion": UC_ROW_TRACEABLE_ARTIFACT_ID}}],
        "uc_rows": [],
    }
    assert uc_row_traceable_artifact_passed(approved) is True
    assert uc_row_traceable_artifact_failure_reason(approved) == "uc_traceable_artifact_satisfied"

    passing_state = {
        "uc_rows": [
            {"uc_id": "UC-1", "artifact_link": "tests/unit/test_a.py"},
            {"uc_id": "UC-2", "artifact_link": "benchmarks/b.py", "artifact_status": "current"},
        ]
    }
    assert uc_row_traceable_artifact_passed(passing_state) is True
    assert uc_row_traceable_artifact_failure_reason(passing_state) == "uc_traceable_artifact_satisfied"

    assert uc_row_traceable_artifact_passed({}) is False
    assert uc_row_traceable_artifact_failure_reason({}) == "uc_traceability_rows_missing"

    missing = {"uc_rows": [{"uc_id": "UC-1"}]}
    assert uc_row_traceable_artifact_passed(missing) is False
    assert uc_row_traceable_artifact_failure_reason(missing) == "uc_traceable_artifact_missing"

    stale = {"uc_rows": [{"uc_id": "UC-2", "artifact_link": "tests/unit/test_b.py", "artifact_status": "expired"}]}
    assert uc_row_traceable_artifact_passed(stale) is False
    assert uc_row_traceable_artifact_failure_reason(stale) == "uc_traceable_artifact_stale"
    not_current = {"uc_rows": [{"uc_id": "UC-2", "artifact_link": "tests/unit/test_b.py", "artifact_current": False}]}
    assert uc_row_traceable_artifact_passed(not_current) is False
    assert uc_row_traceable_artifact_failure_reason(not_current) == "uc_traceable_artifact_stale"

    assert (
        uc_row_traceable_artifact_passed(
            {
                "gate_approvals": [
                    "invalid",
                    {"decision": "rejected", "details": {"criterion": UC_ROW_TRACEABLE_ARTIFACT_ID}},
                    {"decision": "approved", "details": "invalid"},
                ],
                "uc_rows": [{"artifact_link": "tests/unit/test_c.py"}],
            }
        )
        is True
    )


def test_plan_generation_latency_extraction_collection_and_gate_logic():
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_seconds": 12}}) == 12.0
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_ms": 1500}}) == 1.5
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_seconds": -1}}) is None
    assert _extract_plan_generation_latency_seconds({"details": "invalid"}) is None

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

    assert _p95_seconds([]) is None
    assert _p95_seconds([1.0]) == 1.0
    assert _p95_seconds([1.0, 2.0, 3.0, 4.0]) == 4.0

    approved = {
        "gate_approvals": [{"decision": "approved", "details": {"criterion": PLAN_GENERATION_P95_ID}}],
    }
    assert plan_generation_p95_passed(approved) is True
    assert plan_generation_p95_failure_reason(approved) == "plan_generation_p95_satisfied"
    assert (
        plan_generation_p95_passed(
            {
                "gate_approvals": [
                    "invalid",
                    {"decision": "rejected", "details": {"criterion": PLAN_GENERATION_P95_ID}},
                    {"decision": "approved", "details": "invalid"},
                ],
                "plan_generation_latencies_seconds": [180],
            }
        )
        is True
    )

    passing = {"plan_generation_latencies_seconds": [20, 50, 170]}
    failing = {"plan_generation_latencies_seconds": [120, 181]}
    assert plan_generation_p95_passed(passing) is True
    assert plan_generation_p95_passed(failing) is False
    assert plan_generation_p95_failure_reason(failing) == "plan_generation_p95_exceeded"
    assert plan_generation_p95_failure_reason({}) == "plan_generation_latency_missing"


def test_taxonomy_reason_collection_and_pass_fail_logic():
    approvals = [
        "bad",
        {"details": "bad"},
        {"details": {"reason_code": "feature_a_dependency_unverified"}},
        {"details": {"reason_code": "level4_depth_guidance_out_of_range"}},
        {"details": {"reason_code": ""}},
    ]
    assert _error_reason_codes_from_gate_approvals(approvals) == [
        "feature_a_dependency_unverified",
        "level4_depth_guidance_out_of_range",
    ]

    state = {
        "errors_active": ["feature_a_dependency_unverified", "global_function_complexity_threshold_exceeded"],
        "gate_approvals": [{"details": {"reason_code": "level4_depth_guidance_out_of_range"}}],
    }
    assert _error_reason_codes_from_state(state) == [
        "feature_a_dependency_unverified",
        "global_function_complexity_threshold_exceeded",
        "level4_depth_guidance_out_of_range",
    ]
    assert stable_error_taxonomy_passed(state) is True
    assert stable_error_taxonomy_failure_reason(state) == "error_taxonomy_satisfied"
    assert (
        stable_error_taxonomy_passed(
            {
                "gate_approvals": [
                    "invalid",
                    {"decision": "rejected", "details": {"criterion": STABLE_ERROR_TAXONOMY_ID}},
                    {"decision": "approved", "details": "invalid"},
                ],
            }
        )
        is True
    )

    assert stable_error_taxonomy_passed({"error_taxonomy_version": "v0"}) is False
    assert stable_error_taxonomy_failure_reason({"error_taxonomy_version": "v0"}) == "error_taxonomy_version_mismatch"
    assert (
        stable_error_taxonomy_failure_reason({"error_taxonomy_contract": "invalid"})
        == "error_taxonomy_contract_invalid"
    )
    assert (
        stable_error_taxonomy_failure_reason(
            {
                "error_taxonomy_contract": {"version": STABLE_ERROR_TAXONOMY_VERSION, "reason_codes": "invalid"},
            }
        )
        == "error_taxonomy_contract_invalid"
    )

    unknown_code = {
        "error_taxonomy_version": STABLE_ERROR_TAXONOMY_VERSION,
        "errors_active": ["brand_new_reason_code"],
    }
    assert stable_error_taxonomy_passed(unknown_code) is False
    assert stable_error_taxonomy_failure_reason(unknown_code) == "error_taxonomy_reason_code_unknown"

    invalid_contract = {
        "error_taxonomy_version": STABLE_ERROR_TAXONOMY_VERSION,
        "error_taxonomy_contract": {"version": STABLE_ERROR_TAXONOMY_VERSION, "reason_codes": []},
    }
    assert stable_error_taxonomy_passed(invalid_contract) is False
    assert stable_error_taxonomy_failure_reason(invalid_contract) == "error_taxonomy_contract_invalid"


def test_level4_gate_and_paper_validator_mode_branches():
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 80}]}) is True
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 120}]}) is True
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 79}]}) is False
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": "90"}]}) is False
    assert level4_depth_guidance_passed({"level4_sections": ["invalid"]}) is False
    assert (
        level4_depth_guidance_passed(
            {
                "level4_depth_context": {"camera_ready_rigor": True},
                "level4_sections": [{"line_count": 600}],
            }
        )
        is True
    )
    assert level4_depth_guidance_failure_reason({}) == "level4_depth_guidance_missing"
    assert (
        level4_depth_guidance_failure_reason({"level4_sections": [{"line_count": 40}]})
        == "level4_depth_guidance_out_of_range"
    )
    assert (
        level4_depth_guidance_failure_reason(
            {
                "gate_approvals": [{"decision": "approved", "details": {"criterion": LEVEL4_DEPTH_GUIDANCE_ID}}],
            }
        )
        == "level4_depth_guidance_satisfied"
    )

    assert _paper_validator_mode2_enabled({"paper_validator_enabled": True}) is True
    assert _paper_validator_mode2_enabled({"config": {"paper_validator_enabled": True}}) is True

    class Cfg:
        paper_validator_enabled = True

    assert _paper_validator_mode2_enabled({"config": Cfg()}) is True
    assert _paper_validator_mode2_enabled({}) is False


def test_routes_cover_new_uc_gate_and_existing_ordering():
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({}) == "input_writer_node"

    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": "s1"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": None}) == "architect_node"
    assert _route_after_sweep_detection({"sweep_id": None}) == "feature_a_dependency_handler"

    assert _route_after_architect({"enforce_plan_generation_p95": True, "plan_generation_latencies_seconds": [181]}) == (
        "plan_generation_p95_handler"
    )
    assert _route_after_architect({"enforce_plan_generation_p95": True, "plan_generation_latencies_seconds": [1]}) == (
        "intent_extraction_node"
    )
    assert _route_after_architect({}) == "intent_extraction_node"

    assert _route_after_input_writer(
        {"enforce_level4_depth_guidance": True, "level4_sections": [{"line_count": 40}]}
    ) == "level4_depth_guidance_handler"

    assert _route_after_input_writer(
        {
            "enforce_level4_depth_guidance": True,
            "level4_sections": [{"line_count": 95}],
            "enforce_amendment_module_loc": True,
        }
    ) == "amendment_module_loc_handler"

    assert _route_after_input_writer(
        {
            "enforce_level4_depth_guidance": True,
            "level4_sections": [{"line_count": 95}],
            "enforce_amendment_module_loc": True,
            "amendment_module_loc_report": {"passes": True},
            "enforce_global_function_complexity": True,
            "global_complexity_report": {"passes": False},
        }
    ) == "global_function_complexity_handler"

    assert _route_after_input_writer(
        {
            "enforce_level4_depth_guidance": True,
            "level4_sections": [{"line_count": 95}],
            "enforce_amendment_module_loc": True,
            "amendment_module_loc_report": {"passes": True},
            "enforce_global_function_complexity": True,
            "global_complexity_report": {"passes": True},
            "enforce_stable_error_taxonomy": True,
            "errors_active": ["brand_new_reason_code"],
            "error_taxonomy_version": STABLE_ERROR_TAXONOMY_VERSION,
        }
    ) == "stable_error_taxonomy_handler"

    assert _route_after_input_writer(
        {
            "enforce_level4_depth_guidance": True,
            "level4_sections": [{"line_count": 95}],
            "enforce_amendment_module_loc": True,
            "amendment_module_loc_report": {"passes": True},
            "enforce_global_function_complexity": True,
            "global_complexity_report": {"passes": True},
            "enforce_stable_error_taxonomy": True,
            "errors_active": ["feature_a_dependency_unverified"],
            "error_taxonomy_version": STABLE_ERROR_TAXONOMY_VERSION,
            "enforce_uc_row_traceable_artifact": True,
            "uc_rows": [{"uc_id": "UC-1", "artifact_link": ""}],
        }
    ) == "uc_row_traceable_artifact_handler"

    assert _route_after_input_writer(
        {
            "enforce_uc_row_traceable_artifact": True,
            "uc_rows": [{"uc_id": "UC-1", "artifact_link": "tests/unit/test_x.py"}],
            "paper_validator_enabled": True,
            "validation_manifest": {"ok": True},
        }
    ) == "paper_validator_node"
    assert _route_after_input_writer(
        {
            "enforce_uc_row_traceable_artifact": True,
            "uc_rows": [{"uc_id": "UC-1", "artifact_link": "tests/unit/test_x.py"}],
        }
    ) == "end"

    assert _route_after_input_writer({}) == "end"


def test_handlers_record_rejections_and_avoid_duplicates():
    dep_updates = feature_a_dependency_handler_node({"gate_approvals": "invalid", "errors_active": "invalid"})
    assert dep_updates["reviewer_failure_category"] == "dependency_gate"
    assert dep_updates["errors_active"] == ["feature_a_dependency_unverified"]

    amendment_updates = amendment_module_loc_handler_node({"gate_approvals": "invalid", "errors_active": "invalid"})
    assert amendment_updates["reviewer_failure_category"] == "amendment_structure_gate"
    assert amendment_updates["gate_approvals"][-1]["details"]["criterion"] == AMENDMENT_MODULE_LOC_ID

    complexity_updates = global_function_complexity_handler_node(
        {"gate_approvals": "invalid", "errors_active": "invalid", "global_complexity_report": {"passes": False}}
    )
    assert complexity_updates["reviewer_failure_category"] == "complexity_gate"
    assert complexity_updates["gate_approvals"][-1]["details"]["criterion"] == GLOBAL_FUNCTION_COMPLEXITY_ID

    level4_updates = level4_depth_guidance_handler_node(
        {
            "gate_approvals": "invalid",
            "errors_active": ["level4_depth_guidance_out_of_range"],
            "level4_sections": [{"line_count": 5}],
        }
    )
    assert level4_updates["reviewer_failure_category"] == "depth_guidance_gate"
    assert level4_updates["gate_approvals"][-1]["details"]["criterion"] == LEVEL4_DEPTH_GUIDANCE_ID
    assert level4_updates["errors_active"].count("level4_depth_guidance_out_of_range") == 1

    p95_updates = plan_generation_p95_handler_node(
        {
            "gate_approvals": "invalid",
            "errors_active": ["plan_generation_p95_exceeded"],
            "plan_generation_latencies_seconds": [120, 181],
        }
    )
    assert p95_updates["reviewer_failure_category"] == "planning_latency_gate"
    assert p95_updates["gate_approvals"][-1]["details"]["criterion"] == PLAN_GENERATION_P95_ID
    assert p95_updates["errors_active"].count("plan_generation_p95_exceeded") == 1

    taxonomy_updates = stable_error_taxonomy_handler_node(
        {
            "gate_approvals": "invalid",
            "errors_active": "invalid",
            "error_taxonomy_version": STABLE_ERROR_TAXONOMY_VERSION,
        }
    )
    assert taxonomy_updates["reviewer_failure_category"] == "error_taxonomy_gate"
    assert taxonomy_updates["gate_approvals"][-1]["details"]["criterion"] == STABLE_ERROR_TAXONOMY_ID

    uc_updates = uc_row_traceable_artifact_handler_node(
        {
            "gate_approvals": "invalid",
            "errors_active": ["uc_traceable_artifact_missing"],
            "uc_rows": [{"uc_id": "UC-1", "artifact_link": ""}],
        }
    )
    assert uc_updates["mode"] == "terminal"
    assert uc_updates["reviewer_failure_category"] == "uc_traceability_gate"
    assert uc_updates["gate_approvals"][-1]["details"]["criterion"] == UC_ROW_TRACEABLE_ARTIFACT_ID
    assert uc_updates["gate_approvals"][-1]["details"]["row_count"] == 1
    assert uc_updates["errors_active"].count("uc_traceable_artifact_missing") == 1

    missing_rows = uc_row_traceable_artifact_handler_node({"gate_approvals": [], "errors_active": "invalid"})
    assert missing_rows["errors_active"] == ["uc_traceability_rows_missing"]

    dep_existing = feature_a_dependency_handler_node({"gate_approvals": [], "errors_active": ["feature_a_dependency_unverified"]})
    assert dep_existing["errors_active"] == ["feature_a_dependency_unverified"]
    complexity_existing = global_function_complexity_handler_node(
        {
            "gate_approvals": [],
            "errors_active": ["global_function_complexity_threshold_exceeded"],
            "global_complexity_report": {"passes": False},
        }
    )
    assert complexity_existing["errors_active"] == ["global_function_complexity_threshold_exceeded"]
    amendment_existing = amendment_module_loc_handler_node(
        {
            "gate_approvals": [],
            "errors_active": ["amendment_module_helper_extraction_missing"],
        }
    )
    assert amendment_existing["errors_active"] == ["amendment_module_helper_extraction_missing"]


def test_placeholder_nodes_and_graph_wiring_include_uc_gate():
    state = {"clarification_questions": ["q"], "sweep_id": "s1", "sweep_parameter": "x"}
    assert clarification_handler_node(state) is state
    assert sweep_execution_handler_node(state) is state

    graph = create_graph().compile().get_graph()
    nodes = set(graph.nodes)
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert "uc_row_traceable_artifact_handler" in nodes
    assert ("input_writer_node", "uc_row_traceable_artifact_handler") in edges
    assert ("uc_row_traceable_artifact_handler", "__end__") in edges
