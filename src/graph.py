"""Graph wiring for B1b/B1c intent and clarification flow."""

from __future__ import annotations

import math
import re
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
    validate_feature_blocks_tests_fixtures,
    validate_new_file_helper_extraction,
)
from src.utils.metrics import validate_risk_owner_status_updates

_FEATURE_BLOCK_HEADER_RE = re.compile(r"^##\s+\[([^\]]+)\]\s*(.+?)\s*$")
_TESTS_FIXTURES_LINE_RE = re.compile(r"^tests/fixtures\s*:\s*(.+)$", re.IGNORECASE)


def _route_after_clarification(state: dict) -> str:
    if state.get("clarification_needed", False):
        return "clarification_handler"
    return "input_writer_node"


def _route_after_sweep_detection(state: dict) -> str:
    if state.get("sweep_id") is not None:
        return "sweep_execution_handler"
    return "architect_node"


def _paper_validator_enabled(state: dict[str, Any]) -> bool:
    config = state.get("config")
    if isinstance(config, dict):
        return bool(config.get("paper_validator_enabled", False))
    return bool(getattr(config, "paper_validator_enabled", False))


def _get_z_score(confidence_level: float) -> float:
    """Return common two-tailed z-scores for confidence intervals."""
    if math.isclose(confidence_level, 0.90, rel_tol=0.0, abs_tol=1e-9):
        return 1.645
    if math.isclose(confidence_level, 0.95, rel_tol=0.0, abs_tol=1e-9):
        return 1.96
    if math.isclose(confidence_level, 0.99, rel_tol=0.0, abs_tol=1e-9):
        return 2.576
    return 1.96


def compute_confidence_interval(
    samples: list[float], confidence_level: float = 0.95
) -> dict[str, float | int | bool | None]:
    """Compute mean and normal-approximation confidence interval for samples."""
    if not samples:
        return {
            "confidence_interval_available": False,
            "sample_size": 0,
            "mean": None,
            "margin_of_error": None,
            "lower_bound": None,
            "upper_bound": None,
            "confidence_level": confidence_level,
        }

    sample_size = len(samples)
    mean = sum(samples) / sample_size
    if sample_size < 2:
        return {
            "confidence_interval_available": False,
            "sample_size": sample_size,
            "mean": mean,
            "margin_of_error": None,
            "lower_bound": mean,
            "upper_bound": mean,
            "confidence_level": confidence_level,
        }

    variance = sum((sample - mean) ** 2 for sample in samples) / (sample_size - 1)
    standard_error = math.sqrt(variance / sample_size)
    margin_of_error = _get_z_score(confidence_level) * standard_error
    return {
        "confidence_interval_available": True,
        "sample_size": sample_size,
        "mean": mean,
        "margin_of_error": margin_of_error,
        "lower_bound": mean - margin_of_error,
        "upper_bound": mean + margin_of_error,
        "confidence_level": confidence_level,
    }


def _extract_strategy_samples(metric_payload: Any) -> list[float]:
    if isinstance(metric_payload, dict):
        candidates = metric_payload.get("confidence_scores", [])
    elif isinstance(metric_payload, list):
        candidates = metric_payload
    else:
        candidates = []
    return [float(value) for value in candidates if isinstance(value, (int, float))]


def _build_strategy_confidence_report(state: dict[str, Any]) -> None:
    """Attach per-strategy confidence intervals to state when metrics are present."""
    strategy_metrics = state.get("strategy_metrics")
    if not isinstance(strategy_metrics, dict):
        return

    confidence_level = state.get("strategy_confidence_level", 0.95)
    report: dict[str, dict[str, float | int | bool | None]] = {}
    for strategy_name, metric_payload in strategy_metrics.items():
        samples = _extract_strategy_samples(metric_payload)
        report[str(strategy_name)] = compute_confidence_interval(
            samples,
            confidence_level=float(confidence_level),
        )

    state["strategy_confidence_intervals"] = report
    state["strategy_reporting"] = {
        "confidence_intervals_included": bool(report),
        "confidence_interval_level": float(confidence_level),
        "strategies_with_intervals": sorted(
            strategy
            for strategy, details in report.items()
            if bool(details.get("confidence_interval_available", False))
        ),
    }


def _route_after_architect(state: dict[str, Any]) -> str:
    _build_strategy_confidence_report(state)
    if _paper_validator_enabled(state):
        return "paper_validator_node"
    return "intent_extraction_node"


def _route_after_paper_validator(state: dict[str, Any]) -> str:
    if not state.get("paper_validation_passed", False):
        return "end"
    feature_blocks_markdown = state.get("feature_blocks_markdown")
    if isinstance(feature_blocks_markdown, str):
        validation = validate_feature_blocks_tests_fixtures(feature_blocks_markdown)
        if not validation["feature_blocks_validation_passed"]:
            return "end"
        helper_validation = validate_new_file_helper_extraction(feature_blocks_markdown)
        state["new_file_helper_extraction_validation"] = helper_validation
        state["new_file_helper_extraction_validation_passed"] = helper_validation[
            "new_file_helper_extraction_validation_passed"
        ]
        if not helper_validation["new_file_helper_extraction_validation_passed"]:
            return "end"
    elif state.get("feature_blocks_validation_required", False):
        if not state.get("feature_blocks_validation_passed", False):
            return "end"
    if state.get("new_file_helper_extraction_validation_required", False):
        helper_ok = state.get("new_file_helper_extraction_validation_passed", False)
        if not helper_ok:
            return "end"
    matrix_required = state.get("claim_evidence_matrix_required", False)
    matrix_complete = state.get("claim_evidence_matrix_complete", False)
    if matrix_required and not matrix_complete:
        return "end"
    if not _uc_summary_traceability_valid(state):
        return "end"
    if not _feature_fixture_mapping_valid(state):
        return "end"
    if not _risk_owner_status_updates_valid(state):
        return "end"
    if not _release_gate_criteria_valid(state):
        return "end"
    return "intent_extraction_node"


def _uc_summary_traceability_valid(state: dict[str, Any]) -> bool:
    """Validate that each summarized use case maps to at least one artifact."""
    if not state.get("uc_summary_traceability_required", False):
        return True

    precomputed_complete = state.get("uc_summary_traceability_complete")
    if isinstance(precomputed_complete, bool):
        state["uc_summary_traceability_validation"] = {
            "passed": precomputed_complete,
            "failed_use_cases": [],
            "reason": "ok" if precomputed_complete else "traceability_not_met",
        }
        return precomputed_complete

    raw_entries = state.get("uc_summary_entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        state["uc_summary_traceability_validation"] = {
            "passed": False,
            "failed_use_cases": [],
            "reason": "missing_uc_summary_entries",
        }
        return False

    failed_use_cases: list[str] = []
    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            failed_use_cases.append(f"uc_{index + 1:03d}")
            continue

        uc_id = str(
            entry.get("uc_id")
            or entry.get("use_case_id")
            or entry.get("id")
            or f"uc_{index + 1:03d}"
        )
        artifacts = []
        for key in ("artifacts", "artifact_refs", "traceability_artifacts", "tests", "fixtures", "benchmarks"):
            value = entry.get(key)
            if isinstance(value, list):
                artifacts.extend(str(item).strip() for item in value if str(item).strip())
            elif isinstance(value, str) and value.strip():
                artifacts.append(value.strip())
        if not artifacts:
            failed_use_cases.append(uc_id)

    validation = {
        "passed": not failed_use_cases,
        "failed_use_cases": failed_use_cases,
        "reason": "ok" if not failed_use_cases else "traceability_not_met",
    }
    state["uc_summary_traceability_validation"] = validation
    state["uc_summary_traceability_complete"] = validation["passed"]
    return validation["passed"]


def _feature_fixture_mapping_valid(state: dict[str, Any]) -> bool:
    """Validate feature-to-test/fixture mapping when explicitly required."""
    if not state.get("feature_test_fixture_mapping_required", False):
        return True

    precomputed_complete = state.get("feature_test_fixture_mapping_complete")
    if isinstance(precomputed_complete, bool):
        state["feature_test_fixture_mapping_validation"] = {
            "passed": precomputed_complete,
            "missing_features": [],
            "reason": "ok" if precomputed_complete else "feature_test_fixture_mapping_not_met",
        }
        return precomputed_complete

    missing_features: list[str] = []
    raw_entries = state.get("feature_test_fixture_mapping")
    if isinstance(raw_entries, list) and raw_entries:
        for index, entry in enumerate(raw_entries):
            if not isinstance(entry, dict):
                missing_features.append(f"feature_{index + 1:03d}")
                continue
            feature_label = str(
                entry.get("feature_label")
                or entry.get("feature_id")
                or entry.get("id")
                or f"feature_{index + 1:03d}"
            )
            tests = entry.get("tests")
            fixtures = entry.get("fixtures")
            has_tests = bool(tests) if isinstance(tests, list) else bool(str(tests or "").strip())
            has_fixtures = bool(fixtures) if isinstance(fixtures, list) else bool(str(fixtures or "").strip())
            if not (has_tests and has_fixtures):
                missing_features.append(feature_label)
    else:
        markdown = state.get("feature_blocks_markdown")
        if not isinstance(markdown, str):
            state["feature_test_fixture_mapping_validation"] = {
                "passed": False,
                "missing_features": [],
                "reason": "missing_feature_blocks_markdown",
            }
            return False

        current_feature: str | None = None
        tests_found: list[str] = []
        fixtures_found: list[str] = []
        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            header_match = _FEATURE_BLOCK_HEADER_RE.match(line)
            if header_match:
                if current_feature is not None and not (tests_found and fixtures_found):
                    missing_features.append(current_feature)
                current_feature = line
                tests_found = []
                fixtures_found = []
                continue
            if current_feature is None:
                continue
            mapping_match = _TESTS_FIXTURES_LINE_RE.match(line)
            if not mapping_match:
                continue
            for item in [part.strip() for part in re.split(r"[,;\n]", mapping_match.group(1)) if part.strip()]:
                lowered = item.lower()
                if "fixture" in lowered or lowered.endswith((".json", ".yaml", ".yml")):
                    fixtures_found.append(item)
                else:
                    tests_found.append(item)

        if current_feature is not None and not (tests_found and fixtures_found):
            missing_features.append(current_feature)

    validation = {
        "passed": not missing_features,
        "missing_features": missing_features,
        "reason": "ok" if not missing_features else "feature_test_fixture_mapping_not_met",
    }
    state["feature_test_fixture_mapping_validation"] = validation
    state["feature_test_fixture_mapping_complete"] = validation["passed"]
    return validation["passed"]


def _release_gate_criteria_valid(state: dict[str, Any]) -> bool:
    """Validate release-gate criteria when release validation is required."""
    if not state.get("release_gate_validation_required", False):
        return True

    criteria = state.get("release_gate_criteria")
    if not isinstance(criteria, list) or not criteria:
        state["release_gate_validation"] = {
            "passed": False,
            "failed_criteria": [],
            "reason": "missing_release_gate_criteria",
        }
        return False

    failed_criteria: list[str] = []
    for index, criterion in enumerate(criteria):
        if not isinstance(criterion, dict):
            failed_criteria.append(f"criterion_{index}")
            continue
        criterion_id = str(criterion.get("id", f"criterion_{index}"))
        passed = criterion.get("passed")
        status = str(criterion.get("status", "")).strip().lower()
        met = criterion.get("met")
        is_passed = bool(passed is True or met is True or status in {"ok", "pass", "passed", "met"})
        if not is_passed:
            failed_criteria.append(criterion_id)

    validation = {
        "passed": not failed_criteria,
        "failed_criteria": failed_criteria,
        "reason": "ok" if not failed_criteria else "criteria_not_met",
    }
    state["release_gate_validation"] = validation
    return validation["passed"]


def _risk_owner_status_updates_valid(state: dict[str, Any]) -> bool:
    """Validate risk owners/status updates across release gate milestones."""
    if not state.get("risk_owner_status_validation_required", False):
        return True

    validation = validate_risk_owner_status_updates(
        state.get("risk_entries"),
        state.get("release_gate_milestones"),
    )
    state["risk_owner_status_validation"] = validation
    state["risk_owner_status_validation_complete"] = bool(validation.get("passed", False))
    return state["risk_owner_status_validation_complete"]


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


def create_graph() -> StateGraph:
    """Build graph with B1b/B1c graph wiring."""
    graph = StateGraph(GraphState)

    graph.add_node("sweep_detection_node", sweep_detection_node)
    graph.add_node("architect_node", architect_node)
    graph.add_node("paper_validator_node", paper_validator_node)
    graph.add_node("intent_extraction_node", intent_extraction_node)
    graph.add_node("clarification_node", clarification_node)
    graph.add_node("clarification_handler", clarification_handler_node)
    graph.add_node("sweep_execution_handler", sweep_execution_handler_node)
    graph.add_node("input_writer_node", input_writer_node)

    graph.add_edge(START, "sweep_detection_node")
    graph.add_conditional_edges(
        "sweep_detection_node",
        _route_after_sweep_detection,
        {
            "architect_node": "architect_node",
            "sweep_execution_handler": "sweep_execution_handler",
        },
    )
    graph.add_conditional_edges(
        "architect_node",
        _route_after_architect,
        {
            "paper_validator_node": "paper_validator_node",
            "intent_extraction_node": "intent_extraction_node",
        },
    )
    graph.add_conditional_edges(
        "paper_validator_node",
        _route_after_paper_validator,
        {
            "intent_extraction_node": "intent_extraction_node",
            "end": END,
        },
    )
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
    graph.add_edge("input_writer_node", END)

    return graph
