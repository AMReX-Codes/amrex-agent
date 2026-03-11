"""Tests for impl-location/test synchronization criterion wiring."""

from __future__ import annotations

import pytest

from src.graph import (
    AMENDMENT_MODULE_LOC_ID,
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
    impl_locations_tests_sync_handler_node,
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
from src.services.plan import (
    _use_case_artifact_entries_from_report,
    _use_case_artifact_entries_from_state,
    _feature_test_mapping_entries_from_report,
    AMENDMENT_MODULE_LOC_ID as PLAN_AMENDMENT_MODULE_LOC_ID,
    AMENDMENT_MODULE_MAX_LOC,
    GLOBAL_FUNCTION_COMPLEXITY_DEFAULT_THRESHOLD,
    GLOBAL_FUNCTION_COMPLEXITY_ID,
    IMPL_TEST_SYNC_ID,
    SimulationPlan,
    SimulationPlanFactory,
    amendment_module_loc_failure_reason,
    amendment_module_loc_passed,
    build_amendment_module_loc_report,
    build_global_complexity_report,
    build_feature_test_mapping_report,
    global_function_complexity_failure_reason,
    global_function_complexity_passed,
    impl_locations_tests_synced_failure_reason,
    impl_locations_tests_synced_passed,
    normalize_use_case_artifact_mappings,
    normalize_feature_test_mappings,
)


def _sample_plan() -> SimulationPlan:
    return SimulationPlan(
        selected_solver="PeleLMeX",
        selected_case="Exec/FlameSheet",
        modifications=[("amr.max_level", 2)],
        reasoning="baseline",
        solver_confidence=0.9,
        baseline_confidence=0.8,
        cbr_confidence=0.7,
    )


def test_plan_model_factories_and_normalizers_cover_expected_shapes():
    plan = _sample_plan()
    assert plan.to_dict()["selected_solver"] == "PeleLMeX"
    assert '"selected_solver": "PeleLMeX"' in plan.to_json()
    assert plan.get_overall_confidence() == pytest.approx(0.79)
    assert "Overall:" in plan.get_summary()

    with pytest.raises(ValueError, match="baseline_result is required"):
        SimulationPlanFactory.create_from_rag("PeleLMeX", {}, {}, [], "run")

    rag_plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={"selected_case": {"metadata": {"repo_path": "Exec/Fallback"}}, "confidence": 0.5},
        cbr_plan={"modifications": [{"parameter": "max_step", "value": 20}], "similar_cases": ["A", "B"]},
        docs=[{"doc": "x"}],
        user_prompt="prompt",
        solver_confidence=0.75,
        used_llm=True,
    )
    assert rag_plan.selected_case == "Exec/Fallback"
    assert rag_plan.modifications == [("max_step", 20)]
    assert "patterns from" in rag_plan.reasoning
    assert rag_plan.used_llm is True

    simple_plan = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "PeleLMeX"},
        baseline={"name": "Flame", "case_dir": "Exec/Flame", "total_score": 0.66},
        modifications=[],
        visualization={"plots": []},
        analysis={"checks": []},
        user_prompt="run flame",
    )
    assert simple_plan.selected_case == "Exec/Flame"
    assert simple_plan.baseline_confidence == pytest.approx(0.66)

    with pytest.raises(ValueError, match="missing solver"):
        SimulationPlanFactory.create_from_simple({}, {}, [], {}, {}, "run")

    from_dict_plan = SimulationPlanFactory.from_dict(
        {
            "selected_solver": "PeleLMeX",
            "selected_case": "Exec/Flame",
            "modifications": [["max_step", 10]],
            "reasoning": "ok",
            "unknown": "ignored",
        }
    )
    assert from_dict_plan.modifications == [("max_step", 10)]

    migrated = SimulationPlanFactory.from_dict(
        {
            "solver": "PeleC",
            "baseline": {"path": "Exec/Jet", "code": "PeleC"},
            "modifications": [{"parameter": "dt", "value": 1e-6}],
            "reasoning": "legacy",
        }
    )
    assert migrated.selected_solver == "PeleC"
    assert migrated.selected_case == "Exec/Jet"
    assert migrated.modifications == [("dt", 1e-6)]

    with pytest.raises(ValueError, match="missing solver"):
        SimulationPlanFactory.from_dict({"baseline": {}})

    assert normalize_use_case_artifact_mappings(
        {"entries": [{"usecase": "UC-1", "artifact": "tests/unit/test_a.py"}, {"id": "UC-2", "references": ["a", "", 1]}]}
    ) == [
        {"use_case": "UC-1", "artifacts": ["tests/unit/test_a.py"]},
        {"use_case": "UC-2", "artifacts": ["a"]},
    ]
    assert normalize_use_case_artifact_mappings("bad") == []


def test_complexity_and_amendment_reports_cover_fallback_paths():
    source = """
def simple(x):
    return x

def complex_fn(a, b, c):
    if a and b and c:
        return 1
    if a:
        return 2
    if b:
        return 3
    if c:
        return 4
    return 0
"""
    report = build_global_complexity_report(source, threshold=3)
    assert report["criterion"] == GLOBAL_FUNCTION_COMPLEXITY_ID
    assert report["threshold"] == 3
    assert report["passes"] is False
    assert report["violations"][0]["name"] == "complex_fn"
    assert build_global_complexity_report("async def afn():\n    return 1\n")["functions"][0]["name"] == "afn"
    assert build_global_complexity_report("def a():\n    return 1\n")["threshold"] == GLOBAL_FUNCTION_COMPLEXITY_DEFAULT_THRESHOLD

    approved = {
        "global_complexity_report": {"passes": False},
        "gate_approvals": [{"decision": "approved", "details": {"criterion": GLOBAL_FUNCTION_COMPLEXITY_ID}}],
    }
    assert global_function_complexity_passed(approved) is True
    assert global_function_complexity_failure_reason(approved) == "global_function_complexity_satisfied"
    assert global_function_complexity_passed({"global_complexity_report": {"passes": True}}) is True
    assert global_function_complexity_passed({"global_complexity_report": {"violations": [1]}}) is False
    assert global_function_complexity_passed({"global_complexity_report": {"violations": "invalid"}}) is False
    assert global_function_complexity_passed({}) is False
    assert global_function_complexity_failure_reason({}) == "global_function_complexity_threshold_exceeded"
    assert (
        global_function_complexity_passed(
            {
                "gate_approvals": [
                    "invalid",
                    {"details": "invalid"},
                    {"details": {"criterion": "other"}},
                    {"decision": "approved", "details": {"criterion": GLOBAL_FUNCTION_COMPLEXITY_ID}},
                ]
            }
        )
        is True
    )

    modules = [
        {
            "name": "src/amendments/a.py",
            "loc": 150,
            "is_amendment_module": True,
            "helper_extraction_documented": False,
        },
        {
            "name": "src/amendments/b.py",
            "loc": 95,
            "is_amendment_module": True,
            "helper_extraction_documented": False,
        },
        {
            "name": "src/core/c.py",
            "loc": 300,
            "is_amendment_module": False,
            "helper_extraction_documented": False,
        },
    ]
    amendment_report = build_amendment_module_loc_report(modules)
    assert amendment_report["criterion"] == PLAN_AMENDMENT_MODULE_LOC_ID
    assert amendment_report["max_loc"] == AMENDMENT_MODULE_MAX_LOC
    assert amendment_report["passes"] is False
    assert amendment_report["violations"][0]["name"] == "src/amendments/a.py"

    passing = build_amendment_module_loc_report(
        [{"name": "src/amendments/d.py", "loc": 140, "is_amendment_module": True, "helper_extraction_documented": True}]
    )
    assert passing["passes"] is True

    invalid_loc = build_amendment_module_loc_report(
        [{"name": "bad", "loc": "oops", "is_amendment_module": True}]
    )
    assert invalid_loc["passes"] is False

    approved_amendment = {
        "amendment_module_loc_report": {"passes": False},
        "gate_approvals": [{"decision": "approved", "details": {"criterion": PLAN_AMENDMENT_MODULE_LOC_ID}}],
    }
    assert amendment_module_loc_passed(approved_amendment) is True
    assert amendment_module_loc_failure_reason(approved_amendment) == "amendment_module_loc_satisfied"
    assert amendment_module_loc_passed({"amendment_module_loc_report": {"passes": True}}) is True
    assert amendment_module_loc_passed({"amendment_module_loc_report": {"modules": [{"is_amendment_module": True}]}}) is False
    assert amendment_module_loc_passed({"amendment_module_loc_report": {"modules": "invalid"}}) is True
    assert amendment_module_loc_passed({}) is False
    assert amendment_module_loc_failure_reason({}) == "amendment_module_helper_extraction_missing"
    assert (
        amendment_module_loc_passed(
            {
                "gate_approvals": [
                    "invalid",
                    {"details": "invalid"},
                    {"details": {"criterion": "other"}},
                    {"decision": "approved", "details": {"criterion": PLAN_AMENDMENT_MODULE_LOC_ID}},
                ]
            }
    )
        is True
    )
    assert amendment_module_loc_passed({"amendment_module_loc_report": {"violations": []}}) is True


def test_impl_test_sync_report_gate_reason_and_route():
    normalized = normalize_feature_test_mappings(
        {
            "feature_blocks": [
                {"feature": "UNNUMBERED-052", "implementation": ["src/services/plan.py"], "tests": ["tests/unit/test_impl_test_sync_gate.py"]},
                {"id": "UNNUMBERED-XXX", "impl_locations": "src/graph.py", "test_files": "tests/unit/test_graph.py"},
            ]
        }
    )
    assert normalized == [
        {
            "feature_id": "UNNUMBERED-052",
            "implementation_locations": ["src/services/plan.py"],
            "tests": ["tests/unit/test_impl_test_sync_gate.py"],
        },
        {
            "feature_id": "UNNUMBERED-XXX",
            "implementation_locations": ["src/graph.py"],
            "tests": ["tests/unit/test_graph.py"],
        },
    ]

    report = build_feature_test_mapping_report(
        [
            {"feature_id": "UNNUMBERED-052", "implementation_locations": ["src/services/plan.py"], "tests": ["tests/unit/test_impl_test_sync_gate.py"]},
            {"feature_id": "UNNUMBERED-100", "implementation_locations": [], "tests": ["tests/unit/test_feature_100_gate.py"]},
        ]
    )
    assert report["criterion"] == IMPL_TEST_SYNC_ID
    assert report["passes"] is False
    assert report["violations"][0]["reason_code"] == "impl_locations_missing"

    state_from_report = {"impl_locations_tests_sync_report": report}
    assert impl_locations_tests_synced_passed(state_from_report) is False
    assert impl_locations_tests_synced_failure_reason(state_from_report) == "impl_locations_missing"

    tests_missing_state = {
        "feature_blocks": [
            {
                "feature_id": "UNNUMBERED-052",
                "implementation_locations": ["src/services/plan.py"],
                "tests": [],
            }
        ]
    }
    assert impl_locations_tests_synced_passed(tests_missing_state) is False
    assert impl_locations_tests_synced_failure_reason(tests_missing_state) == "tests_missing"

    approved_state = {
        "impl_locations_tests_sync_report": {"passes": False},
        "gate_approvals": [{"decision": "approved", "details": {"criterion": IMPL_TEST_SYNC_ID}}],
    }
    assert impl_locations_tests_synced_passed(approved_state) is True
    assert impl_locations_tests_synced_failure_reason(approved_state) == "impl_locations_tests_synced_satisfied"

    passing_state = {
        "implementation_test_sync": [
            {
                "feature_id": "UNNUMBERED-052",
                "implementation_locations": ["src/services/plan.py"],
                "tests": ["tests/unit/test_impl_test_sync_gate.py"],
            }
        ]
    }
    assert impl_locations_tests_synced_passed(passing_state) is True

    assert impl_locations_tests_synced_passed({}) is False
    assert impl_locations_tests_synced_failure_reason({}) == "impl_tests_sync_missing"

    assert _route_after_input_writer({"enforce_impl_locations_tests_sync": True}) == "impl_locations_tests_sync_handler"
    assert _route_after_input_writer(
        {
            "enforce_impl_locations_tests_sync": True,
            "implementation_test_sync": [
                {
                    "feature_id": "UNNUMBERED-052",
                    "implementation_locations": ["src/services/plan.py"],
                    "tests": ["tests/unit/test_impl_test_sync_gate.py"],
                }
            ],
            "paper_validator_enabled": True,
            "validation_manifest": {"ok": True},
        }
    ) == "paper_validator_node"

    updates = impl_locations_tests_sync_handler_node({"gate_approvals": "invalid", "errors_active": "invalid"})
    assert updates["mode"] == "terminal"
    assert updates["reviewer_failure_category"] == "impl_test_sync_gate"
    assert updates["gate_approvals"][-1]["details"]["criterion"] == IMPL_TEST_SYNC_ID
    assert updates["errors_active"] == ["impl_tests_sync_missing"]


def test_latency_taxonomy_uc_and_depth_gates_still_functional():
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_seconds": 12}}) == 12.0
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_ms": 1500}}) == 1.5
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_seconds": -1}}) is None
    assert _extract_plan_generation_latency_seconds({"details": "invalid"}) is None

    assert _collect_plan_generation_latencies_seconds({"plan_generation_latencies_seconds": [1, 2.5, "x"]}) == [1.0, 2.5]
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

    approved = {"gate_approvals": [{"decision": "approved", "details": {"criterion": PLAN_GENERATION_P95_ID}}]}
    assert plan_generation_p95_passed(approved) is True
    assert plan_generation_p95_failure_reason(approved) == "plan_generation_p95_satisfied"
    assert plan_generation_p95_passed({"plan_generation_latencies_seconds": [20, 50, 170]}) is True

    failing = {"plan_generation_latencies_seconds": [120, 181]}
    assert plan_generation_p95_passed(failing) is False
    assert plan_generation_p95_failure_reason(failing) == "plan_generation_p95_exceeded"
    assert _route_after_architect({**failing, "enforce_plan_generation_p95": True}) == "plan_generation_p95_handler"
    assert _route_after_architect({"enforce_plan_generation_p95": True, "plan_generation_latencies_seconds": [1]}) == "intent_extraction_node"

    approvals = [
        "bad",
        {"details": "bad"},
        {"details": {"reason_code": "feature_a_dependency_unverified"}},
        {"details": {"reason_code": "level4_depth_guidance_out_of_range"}},
    ]
    assert _error_reason_codes_from_gate_approvals(approvals) == [
        "feature_a_dependency_unverified",
        "level4_depth_guidance_out_of_range",
    ]

    taxonomy_state = {
        "errors_active": ["feature_a_dependency_unverified", "global_function_complexity_threshold_exceeded"],
        "gate_approvals": [{"details": {"reason_code": "level4_depth_guidance_out_of_range"}}],
    }
    assert _error_reason_codes_from_state(taxonomy_state) == [
        "feature_a_dependency_unverified",
        "global_function_complexity_threshold_exceeded",
        "level4_depth_guidance_out_of_range",
    ]
    assert stable_error_taxonomy_passed(taxonomy_state) is True
    assert stable_error_taxonomy_failure_reason(taxonomy_state) == "error_taxonomy_satisfied"
    assert stable_error_taxonomy_passed({"error_taxonomy_version": "v0"}) is False
    assert stable_error_taxonomy_failure_reason({"error_taxonomy_version": "v0"}) == "error_taxonomy_version_mismatch"
    assert stable_error_taxonomy_failure_reason({"error_taxonomy_contract": "invalid"}) == "error_taxonomy_contract_invalid"
    assert stable_error_taxonomy_failure_reason(
        {
            "error_taxonomy_contract": {
                "version": STABLE_ERROR_TAXONOMY_VERSION,
                "reason_codes": "invalid",
            }
        }
    ) == "error_taxonomy_contract_invalid"

    assert stable_error_taxonomy_passed({"errors_active": ["brand_new_reason_code"]}) is False
    assert stable_error_taxonomy_failure_reason({"errors_active": ["brand_new_reason_code"]}) == "error_taxonomy_reason_code_unknown"

    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 80}]}) is True
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 120}]}) is True
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": 79}]}) is False
    assert level4_depth_guidance_passed({"level4_sections": [{"line_count": "90"}]}) is False
    assert level4_depth_guidance_passed({"level4_sections": ["invalid"]}) is False
    assert level4_depth_guidance_passed({"level4_depth_context": {"camera_ready_rigor": True}, "level4_sections": [{"line_count": 600}]}) is True
    assert level4_depth_guidance_failure_reason({}) == "level4_depth_guidance_missing"
    assert level4_depth_guidance_failure_reason({"level4_sections": [{"line_count": 40}]}) == "level4_depth_guidance_out_of_range"

    assert _uc_rows_from_state({"uc_rows": [{"artifact_link": "a"}, "bad"]}) == [{"artifact_link": "a"}]
    assert _uc_rows_from_state({"uc_traceability_rows": [{"artifact_link": "b"}]}) == [{"artifact_link": "b"}]
    assert _uc_rows_from_state({"use_case_rows": [{"artifact_link": "c"}]}) == [{"artifact_link": "c"}]
    assert _uc_rows_from_state({"uc_rows": "invalid"}) == []
    assert _uc_row_has_traceable_artifact({"artifact_link": "tests/unit/test_foo.py"}) is True
    assert _uc_row_has_traceable_artifact({"artifact_link": "  "}) is False
    assert _uc_row_has_traceable_artifact({"artifact_link": "x", "artifact_status": "stale"}) is False
    assert _uc_row_has_traceable_artifact({"artifact_link": "x", "artifact_current": False}) is False

    assert uc_row_traceable_artifact_passed(
        {
            "gate_approvals": [{"decision": "approved", "details": {"criterion": UC_ROW_TRACEABLE_ARTIFACT_ID}}],
            "uc_rows": [],
        }
    ) is True
    assert uc_row_traceable_artifact_failure_reason(
        {"uc_rows": [{"uc_id": "UC-2", "artifact_link": "tests/unit/test_b.py", "artifact_status": "expired"}]}
    ) == "uc_traceable_artifact_stale"


def test_routes_handlers_and_graph_wiring_cover_all_gate_nodes():
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({}) == "input_writer_node"

    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": "s1"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": None}) == "architect_node"
    assert _route_after_sweep_detection({"sweep_id": None}) == "feature_a_dependency_handler"

    assert _paper_validator_mode2_enabled({"paper_validator_enabled": True}) is True
    assert _paper_validator_mode2_enabled({"config": {"paper_validator_enabled": True}}) is True

    class Cfg:
        paper_validator_enabled = True

    assert _paper_validator_mode2_enabled({"config": Cfg()}) is True
    assert _paper_validator_mode2_enabled({}) is False

    assert _route_after_input_writer({"enforce_level4_depth_guidance": True, "level4_sections": [{"line_count": 40}]}) == "level4_depth_guidance_handler"
    assert _route_after_input_writer({"enforce_amendment_module_loc": True, "amendment_module_loc_report": {"passes": False}}) == "amendment_module_loc_handler"
    assert _route_after_input_writer({"enforce_global_function_complexity": True, "global_complexity_report": {"passes": False}}) == "global_function_complexity_handler"
    assert _route_after_input_writer({"enforce_stable_error_taxonomy": True, "errors_active": ["brand_new_reason_code"]}) == "stable_error_taxonomy_handler"
    assert _route_after_input_writer({"enforce_uc_row_traceable_artifact": True, "uc_rows": [{"uc_id": "UC-1", "artifact_link": ""}]}) == "uc_row_traceable_artifact_handler"

    dep_updates = feature_a_dependency_handler_node({"gate_approvals": "invalid", "errors_active": "invalid"})
    assert dep_updates["reviewer_failure_category"] == "dependency_gate"

    amendment_updates = amendment_module_loc_handler_node({"gate_approvals": "invalid", "errors_active": "invalid"})
    assert amendment_updates["reviewer_failure_category"] == "amendment_structure_gate"
    assert amendment_updates["gate_approvals"][-1]["details"]["criterion"] == AMENDMENT_MODULE_LOC_ID

    complexity_updates = global_function_complexity_handler_node({"gate_approvals": "invalid", "errors_active": "invalid", "global_complexity_report": {"passes": False}})
    assert complexity_updates["reviewer_failure_category"] == "complexity_gate"
    assert complexity_updates["gate_approvals"][-1]["details"]["criterion"] == GLOBAL_FUNCTION_COMPLEXITY_ID

    level4_updates = level4_depth_guidance_handler_node({"gate_approvals": "invalid", "errors_active": ["level4_depth_guidance_out_of_range"], "level4_sections": [{"line_count": 5}]})
    assert level4_updates["reviewer_failure_category"] == "depth_guidance_gate"
    assert level4_updates["gate_approvals"][-1]["details"]["criterion"] == LEVEL4_DEPTH_GUIDANCE_ID

    p95_updates = plan_generation_p95_handler_node({"gate_approvals": "invalid", "errors_active": ["plan_generation_p95_exceeded"], "plan_generation_latencies_seconds": [120, 181]})
    assert p95_updates["reviewer_failure_category"] == "planning_latency_gate"
    assert p95_updates["gate_approvals"][-1]["details"]["criterion"] == PLAN_GENERATION_P95_ID

    taxonomy_updates = stable_error_taxonomy_handler_node({"gate_approvals": "invalid", "errors_active": "invalid", "error_taxonomy_version": STABLE_ERROR_TAXONOMY_VERSION})
    assert taxonomy_updates["reviewer_failure_category"] == "error_taxonomy_gate"
    assert taxonomy_updates["gate_approvals"][-1]["details"]["criterion"] == STABLE_ERROR_TAXONOMY_ID

    uc_updates = uc_row_traceable_artifact_handler_node({"gate_approvals": "invalid", "errors_active": ["uc_traceable_artifact_missing"], "uc_rows": [{"uc_id": "UC-1", "artifact_link": ""}]})
    assert uc_updates["reviewer_failure_category"] == "uc_traceability_gate"
    assert uc_updates["gate_approvals"][-1]["details"]["criterion"] == UC_ROW_TRACEABLE_ARTIFACT_ID

    state = {"clarification_questions": ["q"], "sweep_id": "s1", "sweep_parameter": "x"}
    assert clarification_handler_node(state) is state
    assert sweep_execution_handler_node(state) is state

    graph = create_graph().compile().get_graph()
    nodes = set(graph.nodes)
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert "impl_locations_tests_sync_handler" in nodes
    assert ("input_writer_node", "impl_locations_tests_sync_handler") in edges
    assert ("impl_locations_tests_sync_handler", "__end__") in edges
    assert ("input_writer_node", "uc_row_traceable_artifact_handler") in edges
    assert ("input_writer_node", "stable_error_taxonomy_handler") in edges


def test_graph_regression_suite_still_passes():
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


def test_plan_and_graph_fallback_branches_for_coverage_guardrails():
    rag_tuple_mods = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={"selected_case": {"case": "Exec/CaseA"}, "confidence": 0.33},
        cbr_plan={"modifications": [("amr.max_level", 2)], "reasoning": "explicit"},
        docs=[],
        user_prompt="prompt",
    )
    assert rag_tuple_mods.reasoning == "explicit"

    with_rationale = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "PeleC"},
        baseline={"path": "Exec/A", "match_rationale": "rationale"},
        modifications=[("x", 1)],
        visualization={},
        analysis={},
        user_prompt="run",
    )
    assert "rationale" in with_rationale.reasoning

    assert SimulationPlanFactory.from_dict(
        {
            "selected_solver": "PeleC",
            "selected_case": "Exec/A",
            "modifications": [],
            "reasoning": "ok",
        }
    ).modifications == []

    assert _use_case_artifact_entries_from_report({"use_case_artifacts": {"id": "UC-3"}}) == [
        {"use_case": "UC-3", "artifacts": []}
    ]
    assert _use_case_artifact_entries_from_state({"use_case_artifacts": "invalid"}) == []

    assert normalize_feature_test_mappings({"feature_id": "UNNUMBERED-052"}) == [
        {"feature_id": "UNNUMBERED-052", "implementation_locations": [], "tests": []}
    ]
    assert normalize_feature_test_mappings([{"feature_id": " ", "tests": ["x"]}, "bad"]) == []
    assert _feature_test_mapping_entries_from_report({"feature_mappings": {"feature_id": "UNNUMBERED-052"}}) == [
        {"feature_id": "UNNUMBERED-052", "implementation_locations": [], "tests": []}
    ]

    tests_missing_report = build_feature_test_mapping_report(
        [{"feature_id": "UNNUMBERED-052", "implementation_locations": ["src/a.py"], "tests": []}]
    )
    assert tests_missing_report["violations"][0]["reason_code"] == "tests_missing"
    assert impl_locations_tests_synced_passed(
        {
            "gate_approvals": [
                "invalid",
                {"details": "invalid"},
                {"details": {"criterion": "OTHER"}},
                {"decision": "approved", "details": {"criterion": IMPL_TEST_SYNC_ID}},
            ]
        }
    ) is True
    assert impl_locations_tests_synced_passed({"impl_locations_tests_sync_report": {"violations": []}}) is True
    assert (
        impl_locations_tests_synced_failure_reason(
            {
                "impl_locations_tests_sync_report": {
                    "violations": ["invalid", {"reason_code": "unknown"}],
                },
                "feature_mappings": [{"feature_id": "UNNUMBERED-052", "implementation_locations": [], "tests": []}],
            }
        )
        == "impl_locations_missing"
    )

    assert level4_depth_guidance_passed({"gate_approvals": [{"decision": "approved", "details": {"criterion": LEVEL4_DEPTH_GUIDANCE_ID}}]}) is True
    assert level4_depth_guidance_failure_reason(
        {"gate_approvals": [{"decision": "approved", "details": {"criterion": LEVEL4_DEPTH_GUIDANCE_ID}}]}
    ) == "level4_depth_guidance_satisfied"
    assert _route_after_input_writer({}) == "end"


def test_regression_uc_row_traceability_helpers_and_pass_fail_logic():
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


def test_regression_plan_generation_and_taxonomy_and_depth_routes():
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
    assert stable_error_taxonomy_failure_reason({"error_taxonomy_contract": "invalid"}) == "error_taxonomy_contract_invalid"
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
