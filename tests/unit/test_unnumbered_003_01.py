"""Session 51 tests for amendment module LOC and helper extraction criterion wiring."""

from __future__ import annotations

import pytest

from src.graph import (
    AMENDMENT_MODULE_LOC_ID,
    LEVEL4_DEPTH_GUIDANCE_ID,
    PLAN_GENERATION_P95_ID,
    STABLE_ERROR_TAXONOMY_ID,
    STABLE_ERROR_TAXONOMY_VERSION,
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
)
from src.services.plan import (
    AMENDMENT_MODULE_LOC_ID as PLAN_AMENDMENT_MODULE_LOC_ID,
    AMENDMENT_MODULE_MAX_LOC,
    GLOBAL_FUNCTION_COMPLEXITY_DEFAULT_THRESHOLD,
    GLOBAL_FUNCTION_COMPLEXITY_ID,
    SimulationPlan,
    SimulationPlanFactory,
    amendment_module_loc_failure_reason,
    amendment_module_loc_passed,
    build_amendment_module_loc_report,
    build_global_complexity_report,
    global_function_complexity_failure_reason,
    global_function_complexity_passed,
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


def test_simulation_plan_methods_cover_summary_and_serialization():
    plan = _sample_plan()

    as_dict = plan.to_dict()
    assert as_dict["selected_solver"] == "PeleLMeX"

    as_json = plan.to_json()
    assert '"selected_solver": "PeleLMeX"' in as_json

    assert plan.get_overall_confidence() == pytest.approx(0.79)
    summary = plan.get_summary()
    assert "Simulation Plan Summary" in summary
    assert "Overall:" in summary


def test_create_from_rag_requires_baseline_result():
    with pytest.raises(ValueError, match="baseline_result is required"):
        SimulationPlanFactory.create_from_rag(
            solver_name="PeleLMeX",
            baseline_result={},
            cbr_plan={},
            docs=[],
            user_prompt="run",
        )


def test_create_from_rag_converts_dict_modifications_and_generates_reasoning():
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result={
            "selected_case": {"case": "Exec/CaseA", "metadata": {"repo_path": "fallback"}},
            "confidence": 0.65,
            "candidates": [{"case": "Exec/CaseA"}],
        },
        cbr_plan={
            "modifications": [{"parameter": "max_step", "value": 20}],
            "similar_cases": ["CaseA", "CaseB"],
        },
        docs=[{"doc": "x"}],
        user_prompt="prompt",
        solver_confidence=0.75,
        used_llm=True,
    )

    assert plan.selected_case == "Exec/CaseA"
    assert plan.modifications == [("max_step", 20)]
    assert "CaseA" in plan.reasoning
    assert plan.used_llm is True
    assert plan.indexing_strategy == "hierarchical"


def test_create_from_simple_handles_match_rationale_and_confidence():
    plan = SimulationPlanFactory.create_from_simple(
        requirements={"solver": "PeleLMeX"},
        baseline={
            "name": "Flame",
            "path": "Exec/Flame",
            "match_score": 0.66,
            "match_rationale": "Closest setup.",
        },
        modifications=[],
        visualization={"plots": []},
        analysis={"checks": []},
        user_prompt="run flame",
    )

    assert plan.selected_solver == "PeleLMeX"
    assert plan.selected_case == "Exec/Flame"
    assert plan.baseline_confidence == pytest.approx(0.66)
    assert "Closest setup" in plan.reasoning


def test_create_from_simple_raises_when_solver_missing():
    with pytest.raises(ValueError, match="missing solver"):
        SimulationPlanFactory.create_from_simple(
            requirements={},
            baseline={},
            modifications=[],
            visualization={},
            analysis={},
            user_prompt="run",
        )


def test_from_dict_filters_unknown_fields_and_converts_list_modifications():
    plan = SimulationPlanFactory.from_dict(
        {
            "selected_solver": "PeleLMeX",
            "selected_case": "Exec/Flame",
            "modifications": [["max_step", 10]],
            "reasoning": "ok",
            "unknown": "ignored",
        }
    )
    assert plan.modifications == [("max_step", 10)]


def test_from_dict_migrates_legacy_dict_and_missing_solver_error():
    plan = SimulationPlanFactory.from_dict(
        {
            "solver": "PeleC",
            "baseline": {"path": "Exec/Jet", "code": "PeleC"},
            "modifications": [{"parameter": "dt", "value": 1e-6}],
            "reasoning": "legacy",
        }
    )

    assert plan.selected_solver == "PeleC"
    assert plan.selected_case == "Exec/Jet"
    assert plan.modifications == [("dt", 1e-6)]

    with pytest.raises(ValueError, match="missing solver"):
        SimulationPlanFactory.from_dict({"baseline": {}})


def test_build_global_complexity_report_and_gate_fallbacks():
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
    assert len(report["functions"]) == 2
    assert report["passes"] is False
    assert report["violations"][0]["name"] == "complex_fn"

    assert build_global_complexity_report("def a():\n    return 1\n")["threshold"] == (
        GLOBAL_FUNCTION_COMPLEXITY_DEFAULT_THRESHOLD
    )

    approved = {
        "global_complexity_report": {"passes": False},
        "gate_approvals": [
            {
                "decision": "approved",
                "details": {"criterion": GLOBAL_FUNCTION_COMPLEXITY_ID},
            }
        ],
    }
    assert global_function_complexity_passed(approved) is True
    assert global_function_complexity_failure_reason(approved) == "global_function_complexity_satisfied"

    assert global_function_complexity_passed({"global_complexity_report": {"passes": True}}) is True
    assert global_function_complexity_passed({"global_complexity_report": {"violations": [1]}}) is False
    assert global_function_complexity_passed({}) is False
    assert (
        global_function_complexity_failure_reason({})
        == "global_function_complexity_threshold_exceeded"
    )


def test_build_amendment_module_loc_report_and_gate_fallbacks():
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

    report = build_amendment_module_loc_report(modules)
    assert report["criterion"] == PLAN_AMENDMENT_MODULE_LOC_ID
    assert report["max_loc"] == AMENDMENT_MODULE_MAX_LOC
    assert report["passes"] is False
    assert len(report["violations"]) == 1
    assert report["violations"][0]["name"] == "src/amendments/a.py"

    passing = build_amendment_module_loc_report(
        [
            {
                "name": "src/amendments/d.py",
                "loc": 140,
                "is_amendment_module": True,
                "helper_extraction_documented": True,
            }
        ]
    )
    assert passing["passes"] is True

    invalid_loc = build_amendment_module_loc_report(
        [{"name": "bad", "loc": "oops", "is_amendment_module": True}]
    )
    assert invalid_loc["passes"] is False

    approved = {
        "amendment_module_loc_report": {"passes": False},
        "gate_approvals": [
            {
                "decision": "approved",
                "details": {"criterion": PLAN_AMENDMENT_MODULE_LOC_ID},
            }
        ],
    }
    assert amendment_module_loc_passed(approved) is True
    assert amendment_module_loc_failure_reason(approved) == "amendment_module_loc_satisfied"

    assert amendment_module_loc_passed({"amendment_module_loc_report": {"passes": True}}) is True
    assert (
        amendment_module_loc_passed(
            {
                "amendment_module_loc_report": {
                    "modules": [
                        {
                            "name": "ok",
                            "loc": 80,
                            "is_amendment_module": True,
                            "helper_extraction_documented": False,
                        }
                    ]
                }
            }
        )
        is False
    )
    assert amendment_module_loc_passed({}) is False
    assert (
        amendment_module_loc_failure_reason({})
        == "amendment_module_helper_extraction_missing"
    )


def test_plan_generation_latency_extraction_collection_p95_and_gate_logic():
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_seconds": 12}}) == 12.0
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_ms": 1500}}) == 1.5
    assert _extract_plan_generation_latency_seconds({"details": {"plan_generation_latency_seconds": -1}}) is None
    assert _extract_plan_generation_latency_seconds({"details": "invalid"}) is None

    assert _p95_seconds([]) is None
    assert _p95_seconds([1.0]) == 1.0
    assert _p95_seconds([1.0, 2.0, 3.0, 4.0]) == 4.0

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

    approved = {
        "gate_approvals": [
            {"decision": "approved", "details": {"criterion": PLAN_GENERATION_P95_ID}},
        ]
    }
    assert plan_generation_p95_passed(approved) is True
    assert plan_generation_p95_failure_reason(approved) == "plan_generation_p95_satisfied"

    passing = {"plan_generation_latencies_seconds": [20, 50, 170]}
    assert plan_generation_p95_passed(passing) is True

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


def test_stable_taxonomy_reason_code_collection_route_and_handler():
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

    state = {
        "errors_active": ["feature_a_dependency_unverified", "global_function_complexity_threshold_exceeded"],
        "gate_approvals": [
            {
                "details": {
                    "reason_code": "level4_depth_guidance_out_of_range",
                }
            }
        ],
    }
    assert _error_reason_codes_from_state(state) == [
        "feature_a_dependency_unverified",
        "global_function_complexity_threshold_exceeded",
        "level4_depth_guidance_out_of_range",
    ]
    assert stable_error_taxonomy_passed(state) is True
    assert stable_error_taxonomy_failure_reason(state) == "error_taxonomy_satisfied"

    approved = {
        "error_taxonomy_version": "mismatch",
        "gate_approvals": [{"decision": "approved", "details": {"criterion": STABLE_ERROR_TAXONOMY_ID}}],
    }
    assert stable_error_taxonomy_passed(approved) is True

    version_mismatch = {"error_taxonomy_version": "v0"}
    assert stable_error_taxonomy_passed(version_mismatch) is False
    assert stable_error_taxonomy_failure_reason(version_mismatch) == "error_taxonomy_version_mismatch"

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

    blocked = _route_after_input_writer(
        {
            "enforce_stable_error_taxonomy": True,
            "errors_active": ["brand_new_reason_code"],
            "error_taxonomy_version": STABLE_ERROR_TAXONOMY_VERSION,
        }
    )
    assert blocked == "stable_error_taxonomy_handler"

    assert _route_after_input_writer(
        {
            "enforce_stable_error_taxonomy": True,
            "errors_active": ["feature_a_dependency_unverified"],
            "error_taxonomy_version": STABLE_ERROR_TAXONOMY_VERSION,
        }
    ) == "end"

    updates = stable_error_taxonomy_handler_node(
        {
            "gate_approvals": "invalid",
            "errors_active": "invalid",
            "error_taxonomy_version": STABLE_ERROR_TAXONOMY_VERSION,
        }
    )
    assert updates["mode"] == "terminal"
    assert updates["reviewer_failure_category"] == "error_taxonomy_gate"
    assert updates["gate_approvals"][-1]["details"]["criterion"] == STABLE_ERROR_TAXONOMY_ID


def test_existing_level4_complexity_and_new_amendment_routes_remain_wired():
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
    assert (
        _route_after_input_writer(
            {"enforce_level4_depth_guidance": True, "level4_sections": [{"line_count": 40}]}
        )
        == "level4_depth_guidance_handler"
    )

    assert (
        _route_after_input_writer(
            {
                "enforce_amendment_module_loc": True,
                "amendment_module_loc_report": {
                    "passes": False,
                    "violations": [{"name": "src/amendments/x.py"}],
                },
            }
        )
        == "amendment_module_loc_handler"
    )

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
            "error_taxonomy_version": STABLE_ERROR_TAXONOMY_VERSION,
            "errors_active": ["feature_a_dependency_unverified"],
            "paper_validator_enabled": True,
            "validation_manifest": {"ok": True},
        }
    ) == "paper_validator_node"
    assert _route_after_input_writer({}) == "end"


def test_handlers_record_rejections_and_dedupe_errors():
    dep_updates = feature_a_dependency_handler_node(
        {"gate_approvals": "invalid", "errors_active": "invalid"}
    )
    assert dep_updates["reviewer_failure_category"] == "dependency_gate"
    assert dep_updates["errors_active"] == ["feature_a_dependency_unverified"]

    level4_updates = level4_depth_guidance_handler_node(
        {"gate_approvals": "invalid", "errors_active": "invalid", "level4_sections": [{"line_count": 5}]}
    )
    assert level4_updates["reviewer_failure_category"] == "depth_guidance_gate"
    assert level4_updates["gate_approvals"][-1]["details"]["criterion"] == LEVEL4_DEPTH_GUIDANCE_ID
    assert level4_updates["errors_active"] == ["level4_depth_guidance_out_of_range"]

    amendment_updates = amendment_module_loc_handler_node(
        {
            "gate_approvals": "invalid",
            "errors_active": ["amendment_module_helper_extraction_missing"],
            "amendment_module_loc_report": {"passes": False},
        }
    )
    assert amendment_updates["mode"] == "terminal"
    assert amendment_updates["reviewer_failure_category"] == "amendment_structure_gate"
    assert amendment_updates["gate_approvals"][-1]["details"]["criterion"] == AMENDMENT_MODULE_LOC_ID
    assert amendment_updates["errors_active"].count("amendment_module_helper_extraction_missing") == 1

    complexity_updates = global_function_complexity_handler_node(
        {"gate_approvals": "invalid", "errors_active": "invalid", "global_complexity_report": {"passes": False}}
    )
    assert complexity_updates["reviewer_failure_category"] == "complexity_gate"
    assert complexity_updates["gate_approvals"][-1]["details"]["criterion"] == (
        GLOBAL_FUNCTION_COMPLEXITY_ID
    )
    assert complexity_updates["errors_active"] == ["global_function_complexity_threshold_exceeded"]

    p95_updates = plan_generation_p95_handler_node(
        {
            "gate_approvals": "invalid",
            "errors_active": ["plan_generation_p95_exceeded"],
            "plan_generation_latencies_seconds": [120, 181],
        }
    )
    assert p95_updates["reviewer_failure_category"] == "planning_latency_gate"
    assert p95_updates["gate_approvals"][-1]["details"]["criterion"] == PLAN_GENERATION_P95_ID


def test_routes_placeholders_and_graph_wiring():
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

    graph = create_graph().compile().get_graph()
    nodes = set(graph.nodes)
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert "plan_generation_p95_handler" in nodes
    assert ("architect_node", "plan_generation_p95_handler") in edges
    assert ("plan_generation_p95_handler", "__end__") in edges

    assert "level4_depth_guidance_handler" in nodes
    assert ("input_writer_node", "level4_depth_guidance_handler") in edges
    assert ("level4_depth_guidance_handler", "__end__") in edges

    assert "amendment_module_loc_handler" in nodes
    assert ("input_writer_node", "amendment_module_loc_handler") in edges
    assert ("amendment_module_loc_handler", "__end__") in edges

    assert "stable_error_taxonomy_handler" in nodes
    assert ("input_writer_node", "stable_error_taxonomy_handler") in edges
    assert ("stable_error_taxonomy_handler", "__end__") in edges
