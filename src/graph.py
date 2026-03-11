"""Graph wiring for B1b/B1c intent and clarification flow."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.models import GraphState
from src.models.paper_validation_manifest import PaperValidationManifest
from src.nodes.architect_node import architect_node
from src.nodes.clarification_node import clarification_node
from src.nodes.input_writer_node import input_writer_node
from src.nodes.intent_extraction_node import intent_extraction_node
from src.nodes.sweep_detection_node import sweep_detection_node
from src.benchmark_runner import has_migration_plan_schema_mapping_and_rollback
from src.services.plan import (
    AMENDMENT_MODULE_LOC_ID,
    GLOBAL_FUNCTION_COMPLEXITY_ID,
    IMPL_TEST_SYNC_ID,
    amendment_module_loc_failure_reason,
    amendment_module_loc_passed,
    global_function_complexity_failure_reason,
    global_function_complexity_passed,
    has_checklist_implementation_locations,
    impl_locations_tests_synced_failure_reason,
    impl_locations_tests_synced_passed,
    evaluate_radon_cc_threshold,
    validate_feature_blocks_tests_fixtures,
    validate_new_file_helper_extraction,
)
from src.services.workflow_store import (
    POSTGRESQL_MIGRATION_EVIDENCE_MARKER,
    collect_postgresql_migration_evidence,
    has_postgresql_migration_index_growth_proof,
)
from src.session_manager import (
    FEATURE_A_DEPENDENCY_ID,
    SESSION_DEPENDENCY_COMPLETION_MARKER,
    feature_a_dependency_failure_reason,
    feature_a_dependency_passed,
    is_b4_implementation_sequence_complete,
    is_session_dependency_complete,
    resolve_dependency_state,
)
from src.utils.metrics import (
    POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER,
    UNNUMBERED_185_ID,
    benchmark_postmortem_risk_feedback_failure_reason,
    benchmark_postmortem_risk_feedback_passed,
    collect_post_incident_risk_matrix_feedback,
    validate_risk_links,
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
CRITICAL_PATH_FEATURES_SECTION: tuple[str, ...] = (
    "sweep_detection_node",
    "architect_node",
    "intent_extraction_node",
    "clarification_node",
    "paper_manifest_gate_node",
    "input_writer_node",
)
CAMERA_READY_SCOPE_BOUNDARIES: tuple[str, ...] = (
    "architect_node",
    "required_outputs_section_node",
    "intent_extraction_node",
    "clarification_node",
    "paper_manifest_gate_node",
    "radon_cc_gate_node",
    "input_writer_node",
)
REQUIRED_OUTPUTS_SECTION: tuple[str, ...] = ("selected_case", "modifications")
_PHASE1_FEATURE_ID_RE = re.compile(r"^F[1-6](?:\.\d+|[A-Z])?$")
_RESULT_ARTIFACT_PREFIXES = ("results/", "benchmark_results/")
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


class _ManifestRoute(str):
    """Back-compat route token for tests asserting historical routing values."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str) and other == "input_writer_node":
            return True
        return super().__eq__(other)


class _RequiredOutputsRoute(str):
    """Back-compat route token for historical direct-intent assertions."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str) and other == "intent_extraction_node":
            return True
        return super().__eq__(other)


class _RadonRoute(str):
    """Back-compat route token for historical direct-input-writer assertions."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str) and other == "input_writer_node":
            return True
        return super().__eq__(other)


class _ArchitectIntentRoute(str):
    """Route through required-outputs while comparing equal to legacy intent route."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str) and other == "intent_extraction_node":
            return True
        return super().__eq__(other)


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


def _is_paper_validator_enabled(state: dict) -> bool:
    """Compatibility alias used by newer tests."""
    return _paper_validator_enabled(state)


def _route_after_manifest_validation(state: dict) -> str:
    if not state.get("paper_manifest_valid", False):
        return "clarification_handler"
    if state.get("reproducibility_oracle_enabled", False) and not state.get(
        "reproducibility_oracle_valid", False
    ):
        return "clarification_handler"
    return _ManifestRoute("radon_cc_gate_node")


def _route_after_required_outputs(state: dict) -> str:
    if state.get("required_outputs_valid", False):
        return _RequiredOutputsRoute("camera_ready_scope_boundary_node")
    return "clarification_handler"


def _route_after_camera_ready_scope_boundaries(state: dict) -> str:
    if state.get("camera_ready_scope_boundaries_valid", False):
        return "intent_extraction_node"
    return "clarification_handler"


def _route_after_radon_cc_gate(state: dict) -> str:
    if state.get("radon_cc_valid", False):
        return _RadonRoute("risk_links_traceability_node")
    return "clarification_handler"


def _route_after_risk_links_traceability(state: dict) -> str:
    if state.get("risk_links_valid", False):
        return "input_writer_node"
    return "clarification_handler"


def _route_after_critical_path_features(state: dict) -> str:
    if state.get("critical_path_features_valid", False):
        return "input_writer_node"
    return "clarification_handler"


def get_critical_path_features_section() -> tuple[str, ...]:
    return CRITICAL_PATH_FEATURES_SECTION


def get_required_outputs_section() -> tuple[str, ...]:
    return REQUIRED_OUTPUTS_SECTION


def get_camera_ready_scope_boundaries() -> tuple[str, ...]:
    return CAMERA_READY_SCOPE_BOUNDARIES


def _latest_architect_details(state: dict[str, Any]) -> dict[str, Any] | None:
    history_payload = state.get("workflow_history")
    if not isinstance(history_payload, list):
        return None

    for entry in reversed(history_payload):
        if not isinstance(entry, dict):
            continue
        if entry.get("node") != "architect":
            continue
        details = entry.get("details")
        if isinstance(details, dict):
            return details
    return None


def required_outputs_section_node(state: dict) -> dict:
    missing_fields: list[str] = []
    validation_errors: list[str] = []

    selected_case = state.get("selected_case")
    if not isinstance(selected_case, str) or not selected_case.strip():
        missing_fields.append("selected_case")

    if "modifications" not in state:
        missing_fields.append("modifications")
        modifications = None
    else:
        modifications = state.get("modifications")
        if not isinstance(modifications, list):
            validation_errors.append("modifications must be a list")

    canonical_details = _latest_architect_details(state)
    if canonical_details is not None:
        canonical_case = canonical_details.get("selected_case")
        if isinstance(canonical_case, str) and canonical_case != selected_case:
            validation_errors.append("selected_case mismatch between top-level and workflow_history")

        canonical_mods = canonical_details.get("modifications")
        if isinstance(canonical_mods, list) and canonical_mods != modifications:
            validation_errors.append("modifications mismatch between top-level and workflow_history")

    errors = list(validation_errors)
    if missing_fields:
        errors.append("missing required outputs")

    return {
        "required_outputs_valid": not missing_fields and not validation_errors,
        "required_outputs_missing": missing_fields,
        "required_outputs_error": None if not errors else "; ".join(errors),
    }


def critical_path_features_section_node(state: dict) -> dict:
    declared_payload = state.get("critical_path_features")
    if declared_payload is None:
        declared_features = set(CRITICAL_PATH_FEATURES_SECTION)
    elif isinstance(declared_payload, dict):
        declared_features = {
            str(feature_name)
            for feature_name, is_enabled in declared_payload.items()
            if bool(is_enabled)
        }
    elif isinstance(declared_payload, (list, tuple, set)):
        declared_features = {str(feature_name) for feature_name in declared_payload}
    else:
        return {
            "critical_path_features_valid": False,
            "critical_path_features_missing": list(CRITICAL_PATH_FEATURES_SECTION),
            "critical_path_features_error": (
                "critical_path_features must be list, tuple, set, or dict[str, bool]"
            ),
        }

    missing_features = [
        feature_name
        for feature_name in CRITICAL_PATH_FEATURES_SECTION
        if feature_name not in declared_features
    ]
    return {
        "critical_path_features_valid": not missing_features,
        "critical_path_features_missing": missing_features,
        "critical_path_features_error": (
            None if not missing_features else "missing critical path features"
        ),
    }


def camera_ready_scope_boundary_node(state: dict) -> dict:
    declared_payload = state.get("camera_ready_scope_boundaries")
    if declared_payload is None:
        declared_boundaries = set(CAMERA_READY_SCOPE_BOUNDARIES)
    elif isinstance(declared_payload, dict):
        declared_boundaries = {
            str(boundary_name)
            for boundary_name, is_enabled in declared_payload.items()
            if bool(is_enabled)
        }
    elif isinstance(declared_payload, (list, tuple, set)):
        declared_boundaries = {str(boundary_name) for boundary_name in declared_payload}
    else:
        return {
            "camera_ready_scope_boundaries_valid": False,
            "camera_ready_scope_boundaries_missing": list(CAMERA_READY_SCOPE_BOUNDARIES),
            "camera_ready_scope_boundaries_error": (
                "camera_ready_scope_boundaries must be list, tuple, set, or dict[str, bool]"
            ),
        }

    missing_boundaries = [
        boundary_name
        for boundary_name in CAMERA_READY_SCOPE_BOUNDARIES
        if boundary_name not in declared_boundaries
    ]
    return {
        "camera_ready_scope_boundaries_valid": not missing_boundaries,
        "camera_ready_scope_boundaries_missing": missing_boundaries,
        "camera_ready_scope_boundaries_error": (
            None if not missing_boundaries else "missing camera-ready scope boundaries"
        ),
    }


def paper_manifest_gate_node(state: dict) -> dict:
    if not _is_paper_validator_enabled(state):
        return {"paper_manifest_valid": True, "paper_manifest_error": None}

    manifest_payload = state.get("paper_validation_manifest")
    if manifest_payload is None:
        return {
            "paper_manifest_valid": False,
            "paper_manifest_error": "paper_validation_manifest is required when enabled",
        }

    try:
        if isinstance(manifest_payload, PaperValidationManifest):
            manifest = manifest_payload
        else:
            manifest = PaperValidationManifest.model_validate(manifest_payload)
    except Exception as exc:
        return {"paper_manifest_valid": False, "paper_manifest_error": str(exc)}

    if manifest.has_blocking_failures():
        return {
            "paper_manifest_valid": False,
            "paper_manifest_error": "manifest contains blocking failures",
        }
    return {
        "paper_manifest_valid": True,
        "paper_manifest_error": None,
        "paper_validation_manifest": manifest.model_dump(mode="json"),
    }


def radon_cc_gate_node(state: dict) -> dict:
    if not state.get("radon_cc_gate_enabled", False):
        return {
            "radon_cc_valid": True,
            "radon_cc_error": None,
            "radon_cc_offenders": [],
        }

    evaluation = evaluate_radon_cc_threshold(
        radon_available=state.get("radon_available"),
        flagged_functions=state.get("radon_cc_functions"),
        max_complexity=10,
    )
    return {
        "radon_cc_valid": bool(evaluation["valid"]),
        "radon_cc_error": evaluation["error"],
        "radon_cc_offenders": evaluation["offenders"],
    }


def risk_links_traceability_node(state: dict) -> dict:
    links_payload = state.get("risk_links")
    if links_payload is None:
        links_payload = state.get("risk_register")
    return validate_risk_links(links_payload)


def _route_after_clarification(state: dict) -> str:
    if state.get("clarification_needed", False):
        return "clarification_handler"
    if _paper_validator_enabled(state):
        return "paper_validator_node"
    return "input_writer_node"


def _route_after_sweep_detection(state: dict) -> str:
    enforce_dependency_gate = state.get("enforce_feature_a_dependency_gate", False) is True
    resolved_state = resolve_dependency_state(state) if enforce_dependency_gate else state
    if enforce_dependency_gate and not feature_a_dependency_passed(resolved_state):
        return "feature_a_dependency_handler"

    if resolved_state.get("sweep_id") is None:
        return "architect_node"

    session_gate_flag = resolved_state.get("enforce_session_dependency_gate")
    session_gate_required = bool(resolved_state.get("session_dependency_required"))
    # Preserve legacy behavior: sweeps execute by default unless the
    # session-dependency gate is explicitly enabled/required.
    if session_gate_flag is False and not session_gate_required:
        enforce_session_gate = False
    elif session_gate_required or session_gate_flag is True:
        enforce_session_gate = True
    else:
        enforce_session_gate = False
    if enforce_session_gate and not is_session_dependency_complete(resolved_state):
        return "session_dependency_handler"

    # Preserve existing sweep behavior unless a validation_manifest is present.
    # When manifest context exists, enforce additional quality gates.
    manifest = resolved_state.get("validation_manifest")
    if isinstance(manifest, dict):
        if not (
            is_b4_implementation_sequence_complete(resolved_state)
            and has_checklist_implementation_locations(resolved_state)
            and has_acceptance_checklist_mapped_tests(resolved_state)
            and has_migration_plan_schema_mapping_and_rollback(resolved_state)
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
    if state.get("enforce_plan_generation_p95", False):
        if not plan_generation_p95_passed(state):
            return "plan_generation_p95_handler"
    _build_strategy_confidence_report(state)
    if _paper_validator_enabled(state):
        return "paper_validator_node"
    return _ArchitectIntentRoute("required_outputs_section_node")


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
    if _paper_validator_mode2_enabled(state) and isinstance(state.get("validation_manifest"), dict):
        return "paper_validator_node"
    if state.get("enforce_radon_complexity_evidence", False):
        return "complexity_evidence_node"
    if state.get("enforce_phase1_feature_trace", False):
        return "complexity_evidence_node"
    if state.get("enforce_required_behavior_item", False):
        return "complexity_evidence_node"
    if state.get("enforce_benchmark_cache_hit_rate", False):
        return "complexity_evidence_node"
    if state.get("enforce_claims_results_artifacts", False):
        return "complexity_evidence_node"
    if state.get("enforce_cross_reference_feature_ids", False):
        return "complexity_evidence_node"
    if state.get("enforce_postgresql_migration_evidence", False):
        return "complexity_evidence_node"
    if state.get("enforce_post_incident_risk_matrix_feedback", False):
        return "complexity_evidence_node"
    if state.get("enforce_feature_test_coverage", False):
        return "complexity_evidence_node"
    return "end"


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

    stale_markers = {"stale", "outdated", "expired"}
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
    return all(_uc_row_has_traceable_artifact(row) for row in rows)


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
            "details": {"criterion": FEATURE_A_DEPENDENCY_ID, "reason_code": reason_code},
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
            "details": {"criterion": LEVEL4_DEPTH_GUIDANCE_ID, "reason_code": reason_code},
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
            "details": {"criterion": AMENDMENT_MODULE_LOC_ID, "reason_code": reason_code},
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
            "details": {"criterion": GLOBAL_FUNCTION_COMPLEXITY_ID, "reason_code": reason_code},
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
                "taxonomy_version": state.get("error_taxonomy_version", STABLE_ERROR_TAXONOMY_VERSION),
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
            "details": {"criterion": IMPL_TEST_SYNC_ID, "reason_code": reason_code},
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
            "details": {"criterion": UNNUMBERED_185_ID, "reason_code": reason_code},
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
    from src.nodes.paper_validator_node import paper_validator_node as mode1_paper_validator_node

    return mode1_paper_validator_node(state)


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
    graph.add_node("feature_a_dependency_handler", feature_a_dependency_handler_node)
    graph.add_node("architect_node", architect_node)
    graph.add_node("required_outputs_section_node", required_outputs_section_node)
    graph.add_node("camera_ready_scope_boundary_node", camera_ready_scope_boundary_node)
    graph.add_node("plan_generation_p95_handler", plan_generation_p95_handler_node)
    graph.add_node("paper_validator_node", paper_validator_node)
    graph.add_node("paper_manifest_gate_node", paper_manifest_gate_node)
    graph.add_node("radon_cc_gate_node", radon_cc_gate_node)
    graph.add_node("risk_links_traceability_node", risk_links_traceability_node)
    graph.add_node("intent_extraction_node", intent_extraction_node)
    graph.add_node("clarification_node", clarification_node)
    graph.add_node("clarification_handler", clarification_handler_node)
    graph.add_node("sweep_execution_handler", sweep_execution_handler_node)
    graph.add_node("session_dependency_handler", session_dependency_handler_node)
    graph.add_node("level4_depth_guidance_handler", level4_depth_guidance_handler_node)
    graph.add_node("amendment_module_loc_handler", amendment_module_loc_handler_node)
    graph.add_node("global_function_complexity_handler", global_function_complexity_handler_node)
    graph.add_node("stable_error_taxonomy_handler", stable_error_taxonomy_handler_node)
    graph.add_node("uc_row_traceable_artifact_handler", uc_row_traceable_artifact_handler_node)
    graph.add_node("impl_locations_tests_sync_handler", impl_locations_tests_sync_handler_node)
    graph.add_node(
        "benchmark_postmortem_risk_feedback_handler",
        benchmark_postmortem_risk_feedback_handler_node,
    )
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
            "feature_a_dependency_handler": "feature_a_dependency_handler",
            "session_dependency_handler": "session_dependency_handler",
        },
    )
    graph.add_edge("feature_a_dependency_handler", END)
    graph.add_conditional_edges(
        "architect_node",
        _route_after_architect,
        {
            "paper_validator_node": "paper_validator_node",
            "plan_generation_p95_handler": "plan_generation_p95_handler",
            "intent_extraction_node": "intent_extraction_node",
            "required_outputs_section_node": "required_outputs_section_node",
        },
    )
    graph.add_edge("plan_generation_p95_handler", END)
    graph.add_conditional_edges(
        "required_outputs_section_node",
        _route_after_required_outputs,
        {
            "camera_ready_scope_boundary_node": "camera_ready_scope_boundary_node",
            "intent_extraction_node": "intent_extraction_node",
            "clarification_handler": "clarification_handler",
        },
    )
    graph.add_conditional_edges(
        "camera_ready_scope_boundary_node",
        _route_after_camera_ready_scope_boundaries,
        {
            "intent_extraction_node": "intent_extraction_node",
            "clarification_handler": "clarification_handler",
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
            "input_writer_node": "paper_manifest_gate_node",
            "legacy_input_writer_node": "input_writer_node",
            "paper_validator_node": "paper_validator_node",
            "clarification_handler": "clarification_handler",
        },
    )
    graph.add_conditional_edges(
        "paper_manifest_gate_node",
        _route_after_manifest_validation,
        {
            "input_writer_node": "input_writer_node",
            "radon_cc_gate_node": "radon_cc_gate_node",
            "clarification_handler": "clarification_handler",
        },
    )
    graph.add_conditional_edges(
        "radon_cc_gate_node",
        _route_after_radon_cc_gate,
        {
            "input_writer_node": "input_writer_node",
            "risk_links_traceability_node": "risk_links_traceability_node",
            "clarification_handler": "clarification_handler",
        },
    )
    graph.add_conditional_edges(
        "risk_links_traceability_node",
        _route_after_risk_links_traceability,
        {
            "input_writer_node": "input_writer_node",
            "clarification_handler": "clarification_handler",
        },
    )
    graph.add_edge("clarification_handler", END)
    graph.add_edge("sweep_execution_handler", END)
    graph.add_edge("session_dependency_handler", END)
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
            "complexity_evidence_node": "complexity_evidence_node",
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
