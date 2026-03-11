"""Graph wiring for B1b/B1c intent and clarification flow."""

from __future__ import annotations

import math
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.models import GraphState
from src.nodes.architect_node import architect_node
from src.nodes.clarification_node import clarification_node
from src.nodes.input_writer_node import input_writer_node
from src.nodes.intent_extraction_node import intent_extraction_node
from src.nodes.paper_validator_node import paper_validator_node
from src.nodes.sweep_detection_node import sweep_detection_node
from src.services.plan import (
    AMENDMENT_MODULE_LOC_ID,
    GLOBAL_FUNCTION_COMPLEXITY_ID,
    IMPL_TEST_SYNC_ID,
    amendment_module_loc_failure_reason,
    amendment_module_loc_passed,
    global_function_complexity_failure_reason,
    global_function_complexity_passed,
    impl_locations_tests_synced_failure_reason,
    impl_locations_tests_synced_passed,
)
from src.session_manager import (
    FEATURE_A_DEPENDENCY_ID,
    feature_a_dependency_failure_reason,
    feature_a_dependency_passed,
    resolve_dependency_state,
)
from src.utils.metrics import (
    UNNUMBERED_185_ID,
    benchmark_postmortem_risk_feedback_failure_reason,
    benchmark_postmortem_risk_feedback_passed,
)

LEVEL4_DEPTH_GUIDANCE_ID = "UNNUMBERED-055"
LEVEL4_BASELINE_MIN_LINES = 80
LEVEL4_BASELINE_MAX_LINES = 120
LEVEL4_EXPANDED_MIN_LINES = 500
LEVEL4_EXPANDED_MAX_LINES = 1000
LEVEL4_EXPANSION_FLAGS = (
    "near_implementation",
    "high_complexity",
    "camera_ready_rigor",
)
PLAN_GENERATION_P95_ID = "UNNUMBERED-157"
PLAN_GENERATION_P95_MAX_SECONDS = 180.0
STABLE_ERROR_TAXONOMY_ID = "UNNUMBERED-238"
STABLE_ERROR_TAXONOMY_VERSION = "v1"
UC_ROW_TRACEABLE_ARTIFACT_ID = "UNNUMBERED-038"
STABLE_ERROR_REASON_CODES = frozenset(
    {
        "feature_a_dependency_unverified",
        "amendment_module_helper_extraction_missing",
        "global_function_complexity_threshold_exceeded",
        "level4_depth_guidance_missing",
        "level4_depth_guidance_out_of_range",
        "plan_generation_latency_missing",
        "plan_generation_p95_exceeded",
        "error_taxonomy_version_mismatch",
        "error_taxonomy_reason_code_unknown",
        "error_taxonomy_contract_invalid",
        "uc_traceability_rows_missing",
        "uc_traceable_artifact_missing",
        "uc_traceable_artifact_stale",
        "impl_tests_sync_missing",
        "impl_locations_missing",
        "tests_missing",
    }
)


def _extract_plan_generation_latency_seconds(entry: dict[str, Any]) -> float | None:
    details = entry.get("details")
    if not isinstance(details, dict):
        return None

    raw_latency = details.get("plan_generation_latency_seconds")
    if isinstance(raw_latency, (int, float)) and raw_latency >= 0:
        return float(raw_latency)

    raw_latency_ms = details.get("plan_generation_latency_ms")
    if isinstance(raw_latency_ms, (int, float)) and raw_latency_ms >= 0:
        return float(raw_latency_ms) / 1000.0

    return None


def _collect_plan_generation_latencies_seconds(state: dict) -> list[float]:
    direct_latencies = state.get("plan_generation_latencies_seconds")
    if isinstance(direct_latencies, list):
        values = [float(value) for value in direct_latencies if isinstance(value, (int, float))]
        if values:
            return values

    workflow_history = state.get("workflow_history")
    if not isinstance(workflow_history, list):
        return []

    latencies: list[float] = []
    for entry in workflow_history:
        if not isinstance(entry, dict):
            continue
        if entry.get("node") != "architect":
            continue
        latency = _extract_plan_generation_latency_seconds(entry)
        if latency is not None:
            latencies.append(latency)
    return latencies


def _p95_seconds(samples: list[float]) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    rank = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[rank]


def plan_generation_p95_passed(state: dict) -> bool:
    gate_approvals = state.get("gate_approvals", [])
    if isinstance(gate_approvals, list):
        for approval in gate_approvals:
            if not isinstance(approval, dict):
                continue
            if approval.get("decision") != "approved":
                continue
            details = approval.get("details", {})
            if isinstance(details, dict) and details.get("criterion") == PLAN_GENERATION_P95_ID:
                return True

    p95_seconds = _p95_seconds(_collect_plan_generation_latencies_seconds(state))
    return p95_seconds is not None and p95_seconds <= PLAN_GENERATION_P95_MAX_SECONDS


def plan_generation_p95_failure_reason(state: dict) -> str:
    if plan_generation_p95_passed(state):
        return "plan_generation_p95_satisfied"

    latencies = _collect_plan_generation_latencies_seconds(state)
    if not latencies:
        return "plan_generation_latency_missing"

    return "plan_generation_p95_exceeded"


def _error_reason_codes_from_gate_approvals(gate_approvals: list[Any]) -> list[str]:
    reason_codes: list[str] = []
    for approval in gate_approvals:
        if not isinstance(approval, dict):
            continue
        details = approval.get("details")
        if not isinstance(details, dict):
            continue
        reason_code = details.get("reason_code")
        if isinstance(reason_code, str) and reason_code:
            reason_codes.append(reason_code)
    return reason_codes


def _error_reason_codes_from_state(state: dict) -> list[str]:
    reason_codes: set[str] = set()

    errors_active = state.get("errors_active", [])
    if isinstance(errors_active, list):
        reason_codes.update(code for code in errors_active if isinstance(code, str) and code)

    gate_approvals = state.get("gate_approvals", [])
    if isinstance(gate_approvals, list):
        reason_codes.update(_error_reason_codes_from_gate_approvals(gate_approvals))

    return sorted(reason_codes)


def _error_taxonomy_contract_valid(state: dict) -> bool:
    contract = state.get("error_taxonomy_contract")
    if contract is None:
        return True
    if not isinstance(contract, dict):
        return False

    if contract.get("version") != STABLE_ERROR_TAXONOMY_VERSION:
        return False

    contract_codes = contract.get("reason_codes")
    if not isinstance(contract_codes, list):
        return False

    normalized_codes = sorted(code for code in contract_codes if isinstance(code, str) and code)
    return normalized_codes == sorted(STABLE_ERROR_REASON_CODES)


def stable_error_taxonomy_passed(state: dict) -> bool:
    gate_approvals = state.get("gate_approvals", [])
    if isinstance(gate_approvals, list):
        for approval in gate_approvals:
            if not isinstance(approval, dict):
                continue
            if approval.get("decision") != "approved":
                continue
            details = approval.get("details", {})
            if isinstance(details, dict) and details.get("criterion") == STABLE_ERROR_TAXONOMY_ID:
                return True

    taxonomy_version = state.get("error_taxonomy_version", STABLE_ERROR_TAXONOMY_VERSION)
    if taxonomy_version != STABLE_ERROR_TAXONOMY_VERSION:
        return False

    reason_codes = _error_reason_codes_from_state(state)
    if not all(code in STABLE_ERROR_REASON_CODES for code in reason_codes):
        return False

    return _error_taxonomy_contract_valid(state)


def stable_error_taxonomy_failure_reason(state: dict) -> str:
    if stable_error_taxonomy_passed(state):
        return "error_taxonomy_satisfied"

    taxonomy_version = state.get("error_taxonomy_version", STABLE_ERROR_TAXONOMY_VERSION)
    if taxonomy_version != STABLE_ERROR_TAXONOMY_VERSION:
        return "error_taxonomy_version_mismatch"

    reason_codes = _error_reason_codes_from_state(state)
    if any(code not in STABLE_ERROR_REASON_CODES for code in reason_codes):
        return "error_taxonomy_reason_code_unknown"

    if not _error_taxonomy_contract_valid(state):
        return "error_taxonomy_contract_invalid"

    return "error_taxonomy_contract_invalid"


def _level4_expansion_enabled(state: dict, section: dict[str, Any]) -> bool:
    if any(section.get(flag) is True for flag in LEVEL4_EXPANSION_FLAGS):
        return True

    context = state.get("level4_depth_context")
    if isinstance(context, dict):
        return any(context.get(flag) is True for flag in LEVEL4_EXPANSION_FLAGS)
    return False


def _level4_line_count_valid(state: dict, section: dict[str, Any]) -> bool:
    line_count = section.get("line_count")
    if not isinstance(line_count, int):
        return False

    if _level4_expansion_enabled(state, section):
        return LEVEL4_EXPANDED_MIN_LINES <= line_count <= LEVEL4_EXPANDED_MAX_LINES
    return LEVEL4_BASELINE_MIN_LINES <= line_count <= LEVEL4_BASELINE_MAX_LINES


def level4_depth_guidance_passed(state: dict) -> bool:
    gate_approvals = state.get("gate_approvals", [])
    if isinstance(gate_approvals, list):
        for approval in gate_approvals:
            if not isinstance(approval, dict):
                continue
            if approval.get("decision") != "approved":
                continue
            details = approval.get("details", {})
            if isinstance(details, dict) and details.get("criterion") == LEVEL4_DEPTH_GUIDANCE_ID:
                return True

    sections = state.get("level4_sections")
    if not isinstance(sections, list) or not sections:
        return False

    for section in sections:
        if not isinstance(section, dict):
            return False
        if not _level4_line_count_valid(state, section):
            return False
    return True


def level4_depth_guidance_failure_reason(state: dict) -> str:
    if level4_depth_guidance_passed(state):
        return "level4_depth_guidance_satisfied"

    sections = state.get("level4_sections")
    if not isinstance(sections, list) or not sections:
        return "level4_depth_guidance_missing"

    return "level4_depth_guidance_out_of_range"


def _route_after_clarification(state: dict) -> str:
    if state.get("clarification_needed", False):
        return "clarification_handler"
    return "input_writer_node"


def _route_after_sweep_detection(state: dict) -> str:
    resolved_state = resolve_dependency_state(state)
    if not feature_a_dependency_passed(resolved_state):
        return "feature_a_dependency_handler"
    if resolved_state.get("sweep_id") is not None:
        return "sweep_execution_handler"
    return "architect_node"


def _route_after_architect(state: dict) -> str:
    if state.get("enforce_plan_generation_p95", False):
        if not plan_generation_p95_passed(state):
            return "plan_generation_p95_handler"
    return "intent_extraction_node"


def _paper_validator_mode2_enabled(state: dict) -> bool:
    if state.get("paper_validator_enabled") is True:
        return True

    config = state.get("config")
    if isinstance(config, dict):
        return config.get("paper_validator_enabled", False) is True
    return getattr(config, "paper_validator_enabled", False) is True


def _route_after_input_writer(state: dict) -> str:
    if state.get("enforce_level4_depth_guidance", False):
        if not level4_depth_guidance_passed(state):
            return "level4_depth_guidance_handler"
    if state.get("enforce_amendment_module_loc", False):
        if not amendment_module_loc_passed(state):
            return "amendment_module_loc_handler"
    if state.get("enforce_global_function_complexity", False):
        if not global_function_complexity_passed(state):
            return "global_function_complexity_handler"
    if state.get("enforce_stable_error_taxonomy", False):
        if not stable_error_taxonomy_passed(state):
            return "stable_error_taxonomy_handler"
    if state.get("enforce_uc_row_traceable_artifact", False):
        if not uc_row_traceable_artifact_passed(state):
            return "uc_row_traceable_artifact_handler"
    if state.get("enforce_impl_locations_tests_sync", False):
        if not impl_locations_tests_synced_passed(state):
            return "impl_locations_tests_sync_handler"
    if state.get("enforce_benchmark_postmortem_risk_feedback", False):
        if not benchmark_postmortem_risk_feedback_passed(state):
            return "benchmark_postmortem_risk_feedback_handler"
    if _paper_validator_mode2_enabled(state) and isinstance(
        state.get("validation_manifest"), dict
    ):
        return "paper_validator_node"
    return "end"


def _uc_rows_from_state(state: dict) -> list[dict[str, Any]]:
    candidate_keys = ("uc_rows", "uc_traceability_rows", "use_case_rows")
    for key in candidate_keys:
        rows = state.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _uc_row_has_traceable_artifact(row: dict[str, Any]) -> bool:
    artifact_reference = row.get("artifact_link")
    if not isinstance(artifact_reference, str) or not artifact_reference.strip():
        return False

    stale_markers = {
        "stale",
        "outdated",
        "expired",
    }
    status = row.get("artifact_status")
    if isinstance(status, str) and status.strip().lower() in stale_markers:
        return False

    if row.get("artifact_current") is False:
        return False

    return True


def uc_row_traceable_artifact_passed(state: dict) -> bool:
    gate_approvals = state.get("gate_approvals", [])
    if isinstance(gate_approvals, list):
        for approval in gate_approvals:
            if not isinstance(approval, dict):
                continue
            if approval.get("decision") != "approved":
                continue
            details = approval.get("details", {})
            if isinstance(details, dict) and details.get("criterion") == UC_ROW_TRACEABLE_ARTIFACT_ID:
                return True

    rows = _uc_rows_from_state(state)
    if not rows:
        return False

    for row in rows:
        if not _uc_row_has_traceable_artifact(row):
            return False
    return True


def uc_row_traceable_artifact_failure_reason(state: dict) -> str:
    if uc_row_traceable_artifact_passed(state):
        return "uc_traceable_artifact_satisfied"

    rows = _uc_rows_from_state(state)
    if not rows:
        return "uc_traceability_rows_missing"

    for row in rows:
        artifact_link = row.get("artifact_link")
        if not isinstance(artifact_link, str) or not artifact_link.strip():
            return "uc_traceable_artifact_missing"

        status = row.get("artifact_status")
        if isinstance(status, str) and status.strip().lower() in {"stale", "outdated", "expired"}:
            return "uc_traceable_artifact_stale"
        if row.get("artifact_current") is False:
            return "uc_traceable_artifact_stale"

    return "uc_traceable_artifact_missing"


def clarification_handler_node(state: dict) -> dict:
    """
    Placeholder for B1c clarification response.
    Full implementation in later session.
    Currently routes to END after logging questions.
    """
    questions = state.get("clarification_questions", [])
    print(f"Clarification needed: {questions}")
    return state


def sweep_execution_handler_node(state: dict) -> dict:
    """
    Placeholder for B2c sweep fan-out.
    Full implementation in later session.
    Logs detected sweep spec and routes to END.
    """
    sweep_id = state.get("sweep_id")
    sweep_param = state.get("sweep_parameter")
    print(f"Sweep detected: {sweep_id} over {sweep_param}")
    return state


def feature_a_dependency_handler_node(state: dict) -> dict:
    """Record a fail-closed dependency gate decision and route to END."""
    resolved_state = resolve_dependency_state(state)
    reason_code = feature_a_dependency_failure_reason(resolved_state)

    gate_approvals = resolved_state.get("gate_approvals", [])
    if not isinstance(gate_approvals, list):
        gate_approvals = []

    gate_approvals.append(
        {
            "gate_id": f"dependency-{FEATURE_A_DEPENDENCY_ID}",
            "gate_type": "dependency",
            "decision": "rejected",
            "interface_path": "auto",
            "details": {
                "criterion": FEATURE_A_DEPENDENCY_ID,
                "reason_code": reason_code,
            },
        }
    )

    errors_active = resolved_state.get("errors_active", [])
    if not isinstance(errors_active, list):
        errors_active = []
    if reason_code not in errors_active:
        errors_active.append(reason_code)

    return {
        "gate_approvals": gate_approvals,
        "errors_active": errors_active,
        "reviewer_failure_category": "dependency_gate",
        "mode": "terminal",
    }


def global_function_complexity_handler_node(state: dict) -> dict:
    """Record a fail-closed global function complexity gate decision and route to END."""
    reason_code = global_function_complexity_failure_reason(state)

    gate_approvals = state.get("gate_approvals", [])
    if not isinstance(gate_approvals, list):
        gate_approvals = []

    gate_approvals.append(
        {
            "gate_id": f"criterion-{GLOBAL_FUNCTION_COMPLEXITY_ID}",
            "gate_type": "criterion",
            "decision": "rejected",
            "interface_path": "auto",
            "details": {
                "criterion": GLOBAL_FUNCTION_COMPLEXITY_ID,
                "reason_code": reason_code,
            },
        }
    )

    errors_active = state.get("errors_active", [])
    if not isinstance(errors_active, list):
        errors_active = []
    if reason_code not in errors_active:
        errors_active.append(reason_code)

    return {
        "gate_approvals": gate_approvals,
        "errors_active": errors_active,
        "reviewer_failure_category": "complexity_gate",
        "mode": "terminal",
    }


def amendment_module_loc_handler_node(state: dict) -> dict:
    """Record a fail-closed amendment module LOC/helper extraction gate decision."""
    reason_code = amendment_module_loc_failure_reason(state)

    gate_approvals = state.get("gate_approvals", [])
    if not isinstance(gate_approvals, list):
        gate_approvals = []

    gate_approvals.append(
        {
            "gate_id": f"criterion-{AMENDMENT_MODULE_LOC_ID}",
            "gate_type": "criterion",
            "decision": "rejected",
            "interface_path": "auto",
            "details": {
                "criterion": AMENDMENT_MODULE_LOC_ID,
                "reason_code": reason_code,
            },
        }
    )

    errors_active = state.get("errors_active", [])
    if not isinstance(errors_active, list):
        errors_active = []
    if reason_code not in errors_active:
        errors_active.append(reason_code)

    return {
        "gate_approvals": gate_approvals,
        "errors_active": errors_active,
        "reviewer_failure_category": "amendment_structure_gate",
        "mode": "terminal",
    }


def level4_depth_guidance_handler_node(state: dict) -> dict:
    """Record a fail-closed level-4 depth guidance gate decision and route to END."""
    reason_code = level4_depth_guidance_failure_reason(state)

    gate_approvals = state.get("gate_approvals", [])
    if not isinstance(gate_approvals, list):
        gate_approvals = []

    gate_approvals.append(
        {
            "gate_id": f"criterion-{LEVEL4_DEPTH_GUIDANCE_ID}",
            "gate_type": "criterion",
            "decision": "rejected",
            "interface_path": "auto",
            "details": {
                "criterion": LEVEL4_DEPTH_GUIDANCE_ID,
                "reason_code": reason_code,
            },
        }
    )

    errors_active = state.get("errors_active", [])
    if not isinstance(errors_active, list):
        errors_active = []
    if reason_code not in errors_active:
        errors_active.append(reason_code)

    return {
        "gate_approvals": gate_approvals,
        "errors_active": errors_active,
        "reviewer_failure_category": "depth_guidance_gate",
        "mode": "terminal",
    }


def plan_generation_p95_handler_node(state: dict) -> dict:
    """Record a fail-closed planning latency gate decision and route to END."""
    reason_code = plan_generation_p95_failure_reason(state)
    p95_seconds = _p95_seconds(_collect_plan_generation_latencies_seconds(state))

    gate_approvals = state.get("gate_approvals", [])
    if not isinstance(gate_approvals, list):
        gate_approvals = []

    gate_approvals.append(
        {
            "gate_id": f"criterion-{PLAN_GENERATION_P95_ID}",
            "gate_type": "criterion",
            "decision": "rejected",
            "interface_path": "auto",
            "details": {
                "criterion": PLAN_GENERATION_P95_ID,
                "reason_code": reason_code,
                "p95_seconds": p95_seconds,
                "threshold_seconds": PLAN_GENERATION_P95_MAX_SECONDS,
            },
        }
    )

    errors_active = state.get("errors_active", [])
    if not isinstance(errors_active, list):
        errors_active = []
    if reason_code not in errors_active:
        errors_active.append(reason_code)

    return {
        "gate_approvals": gate_approvals,
        "errors_active": errors_active,
        "reviewer_failure_category": "planning_latency_gate",
        "mode": "terminal",
    }


def stable_error_taxonomy_handler_node(state: dict) -> dict:
    """Record a fail-closed taxonomy stability gate decision and route to END."""
    reason_code = stable_error_taxonomy_failure_reason(state)
    reason_codes = _error_reason_codes_from_state(state)

    gate_approvals = state.get("gate_approvals", [])
    if not isinstance(gate_approvals, list):
        gate_approvals = []

    gate_approvals.append(
        {
            "gate_id": f"criterion-{STABLE_ERROR_TAXONOMY_ID}",
            "gate_type": "criterion",
            "decision": "rejected",
            "interface_path": "auto",
            "details": {
                "criterion": STABLE_ERROR_TAXONOMY_ID,
                "reason_code": reason_code,
                "taxonomy_version": state.get(
                    "error_taxonomy_version", STABLE_ERROR_TAXONOMY_VERSION
                ),
                "reason_codes": reason_codes,
            },
        }
    )

    errors_active = state.get("errors_active", [])
    if not isinstance(errors_active, list):
        errors_active = []
    if reason_code not in errors_active:
        errors_active.append(reason_code)

    return {
        "gate_approvals": gate_approvals,
        "errors_active": errors_active,
        "reviewer_failure_category": "error_taxonomy_gate",
        "mode": "terminal",
    }


def uc_row_traceable_artifact_handler_node(state: dict) -> dict:
    """Record a fail-closed UC traceability gate decision and route to END."""
    reason_code = uc_row_traceable_artifact_failure_reason(state)
    rows = _uc_rows_from_state(state)

    gate_approvals = state.get("gate_approvals", [])
    if not isinstance(gate_approvals, list):
        gate_approvals = []

    gate_approvals.append(
        {
            "gate_id": f"criterion-{UC_ROW_TRACEABLE_ARTIFACT_ID}",
            "gate_type": "criterion",
            "decision": "rejected",
            "interface_path": "auto",
            "details": {
                "criterion": UC_ROW_TRACEABLE_ARTIFACT_ID,
                "reason_code": reason_code,
                "row_count": len(rows),
            },
        }
    )

    errors_active = state.get("errors_active", [])
    if not isinstance(errors_active, list):
        errors_active = []
    if reason_code not in errors_active:
        errors_active.append(reason_code)

    return {
        "gate_approvals": gate_approvals,
        "errors_active": errors_active,
        "reviewer_failure_category": "uc_traceability_gate",
        "mode": "terminal",
    }


def impl_locations_tests_sync_handler_node(state: dict) -> dict:
    """Record a fail-closed impl-location/test sync gate decision and route to END."""
    reason_code = impl_locations_tests_synced_failure_reason(state)

    gate_approvals = state.get("gate_approvals", [])
    if not isinstance(gate_approvals, list):
        gate_approvals = []

    gate_approvals.append(
        {
            "gate_id": f"criterion-{IMPL_TEST_SYNC_ID}",
            "gate_type": "criterion",
            "decision": "rejected",
            "interface_path": "auto",
            "details": {
                "criterion": IMPL_TEST_SYNC_ID,
                "reason_code": reason_code,
            },
        }
    )

    errors_active = state.get("errors_active", [])
    if not isinstance(errors_active, list):
        errors_active = []
    if reason_code not in errors_active:
        errors_active.append(reason_code)

    return {
        "gate_approvals": gate_approvals,
        "errors_active": errors_active,
        "reviewer_failure_category": "impl_test_sync_gate",
        "mode": "terminal",
    }


def benchmark_postmortem_risk_feedback_handler_node(state: dict) -> dict:
    """Record a fail-closed benchmark/postmortem risk feedback gate decision."""
    reason_code = benchmark_postmortem_risk_feedback_failure_reason(state)

    gate_approvals = state.get("gate_approvals", [])
    if not isinstance(gate_approvals, list):
        gate_approvals = []

    gate_approvals.append(
        {
            "gate_id": f"criterion-{UNNUMBERED_185_ID}",
            "gate_type": "criterion",
            "decision": "rejected",
            "interface_path": "auto",
            "details": {
                "criterion": UNNUMBERED_185_ID,
                "reason_code": reason_code,
            },
        }
    )

    errors_active = state.get("errors_active", [])
    if not isinstance(errors_active, list):
        errors_active = []
    if reason_code not in errors_active:
        errors_active.append(reason_code)

    return {
        "gate_approvals": gate_approvals,
        "errors_active": errors_active,
        "reviewer_failure_category": "benchmark_postmortem_risk_feedback_gate",
        "mode": "terminal",
    }


def create_graph() -> StateGraph:
    """Build graph with B1b/B1c graph wiring."""
    graph = StateGraph(GraphState)

    graph.add_node("sweep_detection_node", sweep_detection_node)
    graph.add_node("feature_a_dependency_handler", feature_a_dependency_handler_node)
    graph.add_node("level4_depth_guidance_handler", level4_depth_guidance_handler_node)
    graph.add_node("amendment_module_loc_handler", amendment_module_loc_handler_node)
    graph.add_node(
        "global_function_complexity_handler", global_function_complexity_handler_node
    )
    graph.add_node("architect_node", architect_node)
    graph.add_node("plan_generation_p95_handler", plan_generation_p95_handler_node)
    graph.add_node("intent_extraction_node", intent_extraction_node)
    graph.add_node("clarification_node", clarification_node)
    graph.add_node("clarification_handler", clarification_handler_node)
    graph.add_node("sweep_execution_handler", sweep_execution_handler_node)
    graph.add_node("input_writer_node", input_writer_node)
    graph.add_node("stable_error_taxonomy_handler", stable_error_taxonomy_handler_node)
    graph.add_node(
        "uc_row_traceable_artifact_handler", uc_row_traceable_artifact_handler_node
    )
    graph.add_node(
        "impl_locations_tests_sync_handler", impl_locations_tests_sync_handler_node
    )
    graph.add_node(
        "benchmark_postmortem_risk_feedback_handler",
        benchmark_postmortem_risk_feedback_handler_node,
    )
    graph.add_node("paper_validator_node", paper_validator_node)

    graph.add_edge(START, "sweep_detection_node")
    graph.add_conditional_edges(
        "sweep_detection_node",
        _route_after_sweep_detection,
        {
            "architect_node": "architect_node",
            "sweep_execution_handler": "sweep_execution_handler",
            "feature_a_dependency_handler": "feature_a_dependency_handler",
        },
    )
    graph.add_edge("feature_a_dependency_handler", END)
    graph.add_conditional_edges(
        "architect_node",
        _route_after_architect,
        {
            "intent_extraction_node": "intent_extraction_node",
            "plan_generation_p95_handler": "plan_generation_p95_handler",
        },
    )
    graph.add_edge("plan_generation_p95_handler", END)
    graph.add_edge("intent_extraction_node", "clarification_node")
    graph.add_conditional_edges(
        "clarification_node",
        _route_after_clarification,
        {
            "input_writer_node": "input_writer_node",
            "clarification_handler": "clarification_handler",
        },
    )
    graph.add_edge("clarification_handler", END)
    graph.add_edge("sweep_execution_handler", END)
    graph.add_conditional_edges(
        "input_writer_node",
        _route_after_input_writer,
        {
            "level4_depth_guidance_handler": "level4_depth_guidance_handler",
            "amendment_module_loc_handler": "amendment_module_loc_handler",
            "global_function_complexity_handler": "global_function_complexity_handler",
            "stable_error_taxonomy_handler": "stable_error_taxonomy_handler",
            "uc_row_traceable_artifact_handler": "uc_row_traceable_artifact_handler",
            "impl_locations_tests_sync_handler": "impl_locations_tests_sync_handler",
            "benchmark_postmortem_risk_feedback_handler": "benchmark_postmortem_risk_feedback_handler",
            "paper_validator_node": "paper_validator_node",
            "end": END,
        },
    )
    graph.add_edge("level4_depth_guidance_handler", END)
    graph.add_edge("amendment_module_loc_handler", END)
    graph.add_edge("global_function_complexity_handler", END)
    graph.add_edge("stable_error_taxonomy_handler", END)
    graph.add_edge("uc_row_traceable_artifact_handler", END)
    graph.add_edge("impl_locations_tests_sync_handler", END)
    graph.add_edge("benchmark_postmortem_risk_feedback_handler", END)
    graph.add_edge("paper_validator_node", END)

    return graph
