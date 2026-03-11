"""Graph wiring for B1b/B1c intent and clarification flow."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.models import GraphState
from src.nodes.architect_node import architect_node
from src.nodes.clarification_node import clarification_node
from src.nodes.input_writer_node import input_writer_node
from src.nodes.intent_extraction_node import intent_extraction_node
from src.nodes.sweep_detection_node import sweep_detection_node
from src.benchmark_runner import has_migration_plan_schema_mapping_and_rollback
from src.services.plan import (
    has_checklist_implementation_locations,
    validate_feature_blocks_tests_fixtures,
    validate_new_file_helper_extraction,
)
from src.services.workflow_store import (
    POSTGRESQL_MIGRATION_EVIDENCE_MARKER,
    collect_postgresql_migration_evidence,
    has_postgresql_migration_index_growth_proof,
)
from src.session_manager import (
    SESSION_DEPENDENCY_COMPLETION_MARKER,
    is_b4_implementation_sequence_complete,
    is_session_dependency_complete,
)
from src.utils.metrics import (
    POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER,
    collect_post_incident_risk_matrix_feedback,
    validate_risk_owner_status_updates,
)


_ACCEPTANCE_MAPPING_KEYS = (
    "mapped_tests",
    "tests",
    "test_cases",
    "test_ids",
)

PHASE1_FEATURE_TRACE_MARKER = "use_case_feature_trace"
REQUIRED_BEHAVIOR_MARKER = "required_behavior"
CLAIMS_RESULTS_ARTIFACTS_MARKER = "claims_results_artifacts"
CROSS_REFERENCE_FEATURE_IDS_MARKER = "cross_reference_feature_ids"
BENCHMARK_CACHE_HIT_RATE_MARKER = "benchmark_cache_hit_rate"
FEATURE_TEST_COVERAGE_MARKER = "feature_test_coverage"
_PHASE1_FEATURE_ID_RE = re.compile(r"^F[1-6](?:\.\d+|[A-Z])?$")
_RESULT_ARTIFACT_PREFIXES = ("results/", "benchmark_results/")


def collect_radon_complexity_evidence(
    target: str = "src/services/plan.py",
) -> dict[str, Any]:
    """Collect radon complexity gate evidence for a target module."""
    criterion = "radon_cc_max_C"
    radon_bin = shutil.which("radon")
    if not radon_bin:
        return {
            "criterion": criterion,
            "radon_available": False,
            "passed": False,
            "detail": "radon missing in PATH",
        }

    cmd = [radon_bin, "cc", target, "-n", "C"]
    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except OSError as exc:
        return {
            "criterion": criterion,
            "radon_available": False,
            "passed": False,
            "detail": f"radon invocation failed: {exc}",
        }

    output = (completed.stdout or "").strip()
    return {
        "criterion": criterion,
        "radon_available": True,
        "passed": completed.returncode == 0,
        "exit_code": completed.returncode,
        "output": output,
        "error": (completed.stderr or "").strip(),
        "command": cmd,
    }


def _normalize_test_mappings(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []

    if not isinstance(value, list):
        return []

    mappings: list[str] = []
    for entry in value:
        if isinstance(entry, str):
            normalized = entry.strip()
            if normalized:
                mappings.append(normalized)
    return mappings


def has_acceptance_checklist_mapped_tests(context: dict[str, Any]) -> bool:
    """
    Validate acceptance checklist entries include at least one mapped test.
    """
    manifest = context.get("validation_manifest")
    if not isinstance(manifest, dict):
        return False

    checklist = manifest.get("acceptance_checklist")
    if not isinstance(checklist, list) or not checklist:
        return False

    for entry in checklist:
        if not isinstance(entry, dict):
            return False
        has_mapping = any(
            _normalize_test_mappings(entry.get(key))
            for key in _ACCEPTANCE_MAPPING_KEYS
        )
        if not has_mapping:
            return False

    return True
_FEATURE_BLOCK_HEADER_RE = re.compile(r"^##\s+\[([^\]]+)\]\s*(.+?)\s*$")
_TESTS_FIXTURES_LINE_RE = re.compile(r"^tests/fixtures\s*:\s*(.+)$", re.IGNORECASE)


def _route_after_clarification(state: dict) -> str:
    if state.get("clarification_needed", False):
        return "clarification_handler"
    if _paper_validator_enabled(state):
        return "paper_validator_node"
    return "input_writer_node"


def _route_after_sweep_detection(state: dict) -> str:
    if state.get("sweep_id") is None:
        return "architect_node"

    if not is_session_dependency_complete(state):
        return "session_dependency_handler"

    # Preserve existing sweep behavior unless a validation_manifest is present.
    # When manifest context exists, enforce additional quality gates.
    manifest = state.get("validation_manifest")
    if isinstance(manifest, dict):
        if not (
            is_b4_implementation_sequence_complete(state)
            and has_checklist_implementation_locations(state)
            and has_acceptance_checklist_mapped_tests(state)
            and has_migration_plan_schema_mapping_and_rollback(state)
        ):
            return "architect_node"

    return "sweep_execution_handler"


def _paper_validator_enabled(state: dict[str, Any]) -> bool:
    if state.get("paper_validator_enabled", False) or state.get("paper_source"):
        return True
    config = state.get("config")
    if isinstance(config, dict):
        return bool(config.get("paper_validator_enabled", False))
    return bool(getattr(config, "paper_validator_enabled", False))


def _route_after_complexity_evidence(state: dict) -> str:
    if not state.get("enforce_radon_complexity_evidence", False):
        return _route_after_phase1_traceability(state)

    evidence = state.get("radon_complexity_evidence")
    if isinstance(evidence, dict) and evidence.get("radon_available", False):
        return _route_after_phase1_traceability(state)
    return "complexity_evidence_handler"


def _has_phase1_feature_trace(state: dict) -> bool:
    traceability = state.get(PHASE1_FEATURE_TRACE_MARKER)
    if not isinstance(traceability, dict) or not traceability:
        return False

    for use_case_id, feature_ids in traceability.items():
        if not isinstance(use_case_id, str) or not use_case_id.startswith("UC"):
            return False

        if isinstance(feature_ids, str):
            normalized_feature_ids = [feature_ids]
        elif isinstance(feature_ids, list):
            normalized_feature_ids = feature_ids
        else:
            return False

        if not normalized_feature_ids:
            return False

        for feature_id in normalized_feature_ids:
            if not isinstance(feature_id, str) or not _PHASE1_FEATURE_ID_RE.match(feature_id):
                return False

    return True


def _route_after_phase1_traceability(state: dict) -> str:
    if not state.get("enforce_phase1_feature_trace", False):
        return _route_after_required_behavior_item(state)
    if _has_phase1_feature_trace(state):
        return _route_after_required_behavior_item(state)
    return "phase1_traceability_handler"


def _has_required_behavior_item(state: dict) -> bool:
    required_behavior = state.get(REQUIRED_BEHAVIOR_MARKER)
    if isinstance(required_behavior, str):
        return bool(required_behavior.strip())
    if isinstance(required_behavior, list):
        return bool(required_behavior) and all(
            isinstance(item, str) and bool(item.strip()) for item in required_behavior
        )
    return False


def _coerce_non_negative_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric < 0:
        return None
    return numeric


def _coerce_unit_interval_float(value: Any) -> float | None:
    numeric = _coerce_non_negative_float(value)
    if numeric is None or numeric > 1:
        return None
    return numeric


def _extract_cache_stats_payload(state: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("benchmark_cache_stats", "embedding_cache_stats", "cache_stats"):
        payload = state.get(key)
        if isinstance(payload, dict):
            return payload

    workflow_history = state.get("workflow_history")
    if not isinstance(workflow_history, list):
        return None

    for entry in reversed(workflow_history):
        if not isinstance(entry, dict):
            continue
        details = entry.get("details")
        if not isinstance(details, dict):
            continue
        for key in ("benchmark_cache_stats", "embedding_cache_stats", "cache_stats"):
            payload = details.get(key)
            if isinstance(payload, dict):
                return payload
    return None


def _compute_benchmark_cache_hit_rate(state: dict[str, Any]) -> float | None:
    direct_rate = _coerce_unit_interval_float(state.get(BENCHMARK_CACHE_HIT_RATE_MARKER))
    if direct_rate is not None:
        return direct_rate

    for key in ("cache_hit_rate", "embedding_cache_hit_rate"):
        direct_rate = _coerce_unit_interval_float(state.get(key))
        if direct_rate is not None:
            return direct_rate

    cache_stats = _extract_cache_stats_payload(state)
    if not isinstance(cache_stats, dict):
        return None

    hits = _coerce_non_negative_float(cache_stats.get("hits"))
    if hits is None:
        hits = _coerce_non_negative_float(cache_stats.get("cache_hits"))
    if hits is None:
        return None

    total = _coerce_non_negative_float(cache_stats.get("total"))
    if total is None:
        total = _coerce_non_negative_float(cache_stats.get("requests"))
    if total is None:
        total = _coerce_non_negative_float(cache_stats.get("lookups"))
    if total is None:
        misses = _coerce_non_negative_float(cache_stats.get("misses"))
        if misses is None:
            misses = _coerce_non_negative_float(cache_stats.get("cache_misses"))
        if misses is not None:
            total = hits + misses

    if total is None or total <= 0 or hits > total:
        return None
    return hits / total


def _has_benchmark_cache_hit_rate(state: dict[str, Any]) -> bool:
    return _compute_benchmark_cache_hit_rate(state) is not None


def _route_after_required_behavior_item(state: dict) -> str:
    if not state.get("enforce_required_behavior_item", False):
        return _route_after_benchmark_cache_hit_rate(state)
    if _has_required_behavior_item(state):
        return _route_after_benchmark_cache_hit_rate(state)
    return "required_behavior_handler"


def _route_after_benchmark_cache_hit_rate(state: dict) -> str:
    if not state.get("enforce_benchmark_cache_hit_rate", False):
        return _route_after_claims_results_artifacts(state)
    if _has_benchmark_cache_hit_rate(state):
        return _route_after_claims_results_artifacts(state)
    return "benchmark_cache_hit_rate_handler"


def _is_results_artifact_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.startswith(_RESULT_ARTIFACT_PREFIXES)


def _has_claims_results_artifacts(state: dict) -> bool:
    claim_map = state.get(CLAIMS_RESULTS_ARTIFACTS_MARKER)
    if not isinstance(claim_map, dict) or not claim_map:
        return False

    for claim_id, artifact_refs in claim_map.items():
        if not isinstance(claim_id, str) or not claim_id.strip():
            return False

        if isinstance(artifact_refs, str):
            normalized_artifact_refs = [artifact_refs]
        elif isinstance(artifact_refs, list):
            normalized_artifact_refs = artifact_refs
        else:
            return False

        if not normalized_artifact_refs:
            return False

        for artifact_ref in normalized_artifact_refs:
            if not isinstance(artifact_ref, str) or not _is_results_artifact_path(artifact_ref):
                return False

    return True


def _route_after_claims_results_artifacts(state: dict) -> str:
    if not state.get("enforce_claims_results_artifacts", False):
        return _route_after_cross_reference_feature_ids(state)
    if _has_claims_results_artifacts(state):
        return _route_after_cross_reference_feature_ids(state)
    return "claims_results_artifacts_handler"


def _has_cross_reference_feature_ids(state: dict) -> bool:
    cross_refs = state.get(CROSS_REFERENCE_FEATURE_IDS_MARKER)
    if not isinstance(cross_refs, dict) or not cross_refs:
        return False

    for ref_id, feature_ids in cross_refs.items():
        if not isinstance(ref_id, str) or not ref_id.strip():
            return False

        if isinstance(feature_ids, str):
            normalized_feature_ids = [feature_ids]
        elif isinstance(feature_ids, list):
            normalized_feature_ids = feature_ids
        else:
            return False

        if not normalized_feature_ids:
            return False

        for feature_id in normalized_feature_ids:
            if not isinstance(feature_id, str) or not _PHASE1_FEATURE_ID_RE.match(feature_id):
                return False

    return True


def _route_after_cross_reference_feature_ids(state: dict) -> str:
    if not state.get("enforce_cross_reference_feature_ids", False):
        return _route_after_postgresql_migration_evidence(state)
    if _has_cross_reference_feature_ids(state):
        return _route_after_postgresql_migration_evidence(state)
    return "cross_reference_feature_ids_handler"


def _route_after_postgresql_migration_evidence(state: dict) -> str:
    if not state.get("enforce_postgresql_migration_evidence", False):
        return _route_after_post_incident_risk_matrix_feedback(state)

    evidence = collect_postgresql_migration_evidence(state)
    if has_postgresql_migration_index_growth_proof(evidence):
        return _route_after_post_incident_risk_matrix_feedback(state)
    return "postgresql_migration_handler"


def _route_after_post_incident_risk_matrix_feedback(state: dict) -> str:
    if not state.get("enforce_post_incident_risk_matrix_feedback", False):
        return _route_after_feature_test_coverage(state)

    feedback = collect_post_incident_risk_matrix_feedback(state)
    if feedback.get("feedback_complete", False):
        return _route_after_feature_test_coverage(state)
    return "post_incident_risk_matrix_feedback_handler"


def _normalize_test_paths(test_paths: Any, required_prefix: str) -> bool:
    if isinstance(test_paths, str):
        normalized = [test_paths]
    elif isinstance(test_paths, list):
        normalized = test_paths
    else:
        return False

    if not normalized:
        return False

    for path in normalized:
        if not isinstance(path, str) or not path.startswith(required_prefix):
            return False
    return True


def _has_unit_and_integration_feature_coverage(state: dict) -> bool:
    coverage = state.get(FEATURE_TEST_COVERAGE_MARKER)
    if not isinstance(coverage, dict) or not coverage:
        return False

    for feature_id, tests in coverage.items():
        if not isinstance(feature_id, str) or not feature_id.strip():
            return False
        if not isinstance(tests, dict):
            return False

        if not _normalize_test_paths(tests.get("unit"), "tests/unit/"):
            return False
        if not _normalize_test_paths(tests.get("integration"), "tests/integration/"):
            return False

    return True


def _route_after_feature_test_coverage(state: dict) -> str:
    if not state.get("enforce_feature_test_coverage", False):
        return "end"
    if _has_unit_and_integration_feature_coverage(state):
        return "end"
    return "feature_test_coverage_handler"


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
    # Compatibility mode: when called as a pre-validator router in tests.
    if "paper_validation_passed" not in state and "validation_manifest" not in state:
        return "paper_validator_node" if _paper_validator_enabled(state) else "input_writer_node"

    if not state.get("paper_validation_passed", False):
        return "end"
    # Respect explicit upstream gate failure even when markdown is present.
    if state.get("feature_blocks_validation_required", False):
        if state.get("feature_blocks_validation_passed") is False:
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


def session_dependency_handler_node(state: dict) -> dict:
    """Record unmet session dependency marker before terminating workflow."""
    updated = dict(state)
    updated.setdefault(
        "dependency_error",
        "Required dependency session must complete before sweep execution.",
    )
    updated.setdefault("required_marker", SESSION_DEPENDENCY_COMPLETION_MARKER)
    return updated


def paper_validator_node(state: dict) -> dict:
    """
    Graph-level placeholder node for paper-validator topology wiring.

    The concrete mode1 validation logic lives in `src.nodes.paper_validator_node`.
    """
    return state


def complexity_evidence_node(state: dict) -> dict:
    """Record radon complexity evidence when enforcement is enabled."""
    updated = dict(state)
    cache_hit_rate = _compute_benchmark_cache_hit_rate(updated)
    if cache_hit_rate is not None:
        updated[BENCHMARK_CACHE_HIT_RATE_MARKER] = cache_hit_rate

    if not updated.get("enforce_radon_complexity_evidence", False):
        return updated

    if not isinstance(updated.get("radon_complexity_evidence"), dict):
        updated["radon_complexity_evidence"] = collect_radon_complexity_evidence()
    return updated


def complexity_evidence_handler_node(state: dict) -> dict:
    """Capture unmet radon complexity evidence requirements and halt."""
    updated = dict(state)
    if not isinstance(updated.get("radon_complexity_evidence"), dict):
        updated["radon_complexity_evidence"] = collect_radon_complexity_evidence()
    updated.setdefault(
        "dependency_error",
        "Radon complexity evidence is required before workflow completion.",
    )
    updated.setdefault("required_marker", "radon_complexity_evidence")
    return updated


def phase1_traceability_handler_node(state: dict) -> dict:
    """Capture unmet use-case to Phase 1 feature-ID traceability requirements."""
    updated = dict(state)
    updated.setdefault(
        "dependency_error",
        "Use case to Phase 1 feature-ID traceability is required before workflow completion.",
    )
    updated.setdefault("required_marker", PHASE1_FEATURE_TRACE_MARKER)
    return updated


def required_behavior_handler_node(state: dict) -> dict:
    """Capture unmet required-behavior checklist requirements."""
    updated = dict(state)
    updated.setdefault(
        "dependency_error",
        "Consistency checklist required behavior item is required before workflow completion.",
    )
    updated.setdefault("required_marker", REQUIRED_BEHAVIOR_MARKER)
    return updated


def benchmark_cache_hit_rate_handler_node(state: dict) -> dict:
    """Capture unmet benchmark cache hit-rate observability requirements."""
    updated = dict(state)
    updated.setdefault(
        "dependency_error",
        "Benchmark output must include cache hit rate before workflow completion.",
    )
    updated.setdefault("required_marker", BENCHMARK_CACHE_HIT_RATE_MARKER)
    return updated


def claims_results_artifacts_handler_node(state: dict) -> dict:
    """Capture unmet claim-to-results artifact mapping requirements."""
    updated = dict(state)
    updated.setdefault(
        "dependency_error",
        "Claims must map to results artifacts under results/ or benchmark_results/ before workflow completion.",
    )
    updated.setdefault("required_marker", CLAIMS_RESULTS_ARTIFACTS_MARKER)
    return updated


def cross_reference_feature_ids_handler_node(state: dict) -> dict:
    """Capture unmet cross-reference to feature-ID mapping requirements."""
    updated = dict(state)
    updated.setdefault(
        "dependency_error",
        "Cross-references must include owning feature IDs before workflow completion.",
    )
    updated.setdefault("required_marker", CROSS_REFERENCE_FEATURE_IDS_MARKER)
    return updated


def postgresql_migration_handler_node(state: dict) -> dict:
    """Capture unmet PostgreSQL migration and index-growth proof requirements."""
    updated = dict(state)
    updated.setdefault(
        POSTGRESQL_MIGRATION_EVIDENCE_MARKER,
        collect_postgresql_migration_evidence(updated),
    )
    updated.setdefault(
        "dependency_error",
        "PostgreSQL migration runbook and index growth proof are required before workflow completion.",
    )
    updated.setdefault("required_marker", POSTGRESQL_MIGRATION_EVIDENCE_MARKER)
    return updated


def post_incident_risk_matrix_feedback_handler_node(state: dict) -> dict:
    """Capture unmet post-incident risk-matrix feedback requirements."""
    updated = dict(state)
    updated.setdefault(
        POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER,
        collect_post_incident_risk_matrix_feedback(updated),
    )
    updated.setdefault(
        "dependency_error",
        "Post-incident updates must feed back into the risk matrix before workflow completion.",
    )
    updated.setdefault("required_marker", POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER)
    return updated


def feature_test_coverage_handler_node(state: dict) -> dict:
    """Capture unmet unit+integration feature-coverage requirements."""
    updated = dict(state)
    updated.setdefault(
        "dependency_error",
        "Each feature must include both unit and integration test coverage before workflow completion.",
    )
    updated.setdefault("required_marker", FEATURE_TEST_COVERAGE_MARKER)
    return updated


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
    graph.add_node("session_dependency_handler", session_dependency_handler_node)
    graph.add_node("complexity_evidence_node", complexity_evidence_node)
    graph.add_node("complexity_evidence_handler", complexity_evidence_handler_node)
    graph.add_node("phase1_traceability_handler", phase1_traceability_handler_node)
    graph.add_node("required_behavior_handler", required_behavior_handler_node)
    graph.add_node("benchmark_cache_hit_rate_handler", benchmark_cache_hit_rate_handler_node)
    graph.add_node("claims_results_artifacts_handler", claims_results_artifacts_handler_node)
    graph.add_node(
        "cross_reference_feature_ids_handler",
        cross_reference_feature_ids_handler_node,
    )
    graph.add_node("postgresql_migration_handler", postgresql_migration_handler_node)
    graph.add_node(
        "post_incident_risk_matrix_feedback_handler",
        post_incident_risk_matrix_feedback_handler_node,
    )
    graph.add_node("feature_test_coverage_handler", feature_test_coverage_handler_node)
    graph.add_node("input_writer_node", input_writer_node)

    graph.add_edge(START, "sweep_detection_node")
    graph.add_conditional_edges(
        "sweep_detection_node",
        _route_after_sweep_detection,
        {
            "architect_node": "architect_node",
            "sweep_execution_handler": "sweep_execution_handler",
            "session_dependency_handler": "session_dependency_handler",
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
            "paper_validator_node": "paper_validator_node",
            "input_writer_node": "input_writer_node",
        },
    )
    graph.add_edge("intent_extraction_node", "clarification_node")
    graph.add_conditional_edges(
        "clarification_node",
        _route_after_clarification,
        {
            "input_writer_node": "input_writer_node",
            "paper_validator_node": "paper_validator_node",
            "clarification_handler": "clarification_handler",
        },
    )
    graph.add_edge("clarification_handler", END)
    graph.add_edge("sweep_execution_handler", END)
    graph.add_edge("session_dependency_handler", END)
    graph.add_edge("input_writer_node", "complexity_evidence_node")
    graph.add_conditional_edges(
        "complexity_evidence_node",
        _route_after_complexity_evidence,
        {
            "end": END,
            "complexity_evidence_handler": "complexity_evidence_handler",
            "phase1_traceability_handler": "phase1_traceability_handler",
            "required_behavior_handler": "required_behavior_handler",
            "benchmark_cache_hit_rate_handler": "benchmark_cache_hit_rate_handler",
            "claims_results_artifacts_handler": "claims_results_artifacts_handler",
            "cross_reference_feature_ids_handler": "cross_reference_feature_ids_handler",
            "postgresql_migration_handler": "postgresql_migration_handler",
            "post_incident_risk_matrix_feedback_handler": "post_incident_risk_matrix_feedback_handler",
            "feature_test_coverage_handler": "feature_test_coverage_handler",
        },
    )
    graph.add_edge("complexity_evidence_handler", END)
    graph.add_edge("phase1_traceability_handler", END)
    graph.add_edge("required_behavior_handler", END)
    graph.add_edge("benchmark_cache_hit_rate_handler", END)
    graph.add_edge("claims_results_artifacts_handler", END)
    graph.add_edge("cross_reference_feature_ids_handler", END)
    graph.add_edge("postgresql_migration_handler", END)
    graph.add_edge("post_incident_risk_matrix_feedback_handler", END)
    graph.add_edge("feature_test_coverage_handler", END)

    return graph
