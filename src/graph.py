"""Graph wiring for B1b/B1c intent and clarification flow."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from src.models import GraphState
from src.models.paper_validation_manifest import PaperValidationManifest
from src.nodes.architect_node import architect_node
from src.nodes.clarification_node import clarification_node
from src.nodes.input_writer_node import input_writer_node
from src.nodes.intent_extraction_node import intent_extraction_node
from src.nodes.sweep_detection_node import sweep_detection_node
from src.services.plan import evaluate_radon_cc_threshold
from src.utils.metrics import validate_risk_links

CRITICAL_PATH_FEATURES_SECTION: tuple[str, ...] = (
    "sweep_detection_node",
    "architect_node",
    "intent_extraction_node",
    "clarification_node",
    "paper_manifest_gate_node",
    "input_writer_node",
)

REQUIRED_OUTPUTS_SECTION: tuple[str, ...] = ("selected_case", "modifications")

CAMERA_READY_SCOPE_BOUNDARIES: tuple[str, ...] = (
    "architect_node",
    "required_outputs_section_node",
    "intent_extraction_node",
    "clarification_node",
    "paper_manifest_gate_node",
    "radon_cc_gate_node",
    "input_writer_node",
)


def _route_after_clarification(state: dict) -> str:
    if state.get("clarification_needed", False):
        return "clarification_handler"
    return "input_writer_node"


def _route_after_sweep_detection(state: dict) -> str:
    if state.get("sweep_id") is not None:
        return "sweep_execution_handler"
    return "architect_node"


def _route_after_required_outputs(state: dict) -> str:
    if state.get("required_outputs_valid", False):
        return "camera_ready_scope_boundary_node"
    return "clarification_handler"


def _route_after_camera_ready_scope_boundaries(state: dict) -> str:
    if state.get("camera_ready_scope_boundaries_valid", False):
        return "intent_extraction_node"
    return "clarification_handler"


def _is_paper_validator_enabled(state: dict) -> bool:
    if "paper_validator_enabled" in state:
        return bool(state["paper_validator_enabled"])
    config = state.get("config")
    if config is not None and hasattr(config, "paper_validator_enabled"):
        return bool(getattr(config, "paper_validator_enabled"))
    return False


def _route_after_manifest_validation(state: dict) -> str:
    if not state.get("paper_manifest_valid", False):
        return "clarification_handler"
    if state.get("reproducibility_oracle_enabled", False) and not state.get(
        "reproducibility_oracle_valid", False
    ):
        return "clarification_handler"
    return "radon_cc_gate_node"


def _route_after_radon_cc_gate(state: dict) -> str:
    if state.get("radon_cc_valid", False):
        return "risk_links_traceability_node"
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
    """
    Session 24 executable artifact for UNNUMBERED-046.
    Returns the must-have publication critical-path feature list.
    """
    return CRITICAL_PATH_FEATURES_SECTION


def get_required_outputs_section() -> tuple[str, ...]:
    """
    Session 39 executable artifact for UNNUMBERED-274.
    Returns the concrete required-output keys enforced in runtime state.
    """
    return REQUIRED_OUTPUTS_SECTION


def get_camera_ready_scope_boundaries() -> tuple[str, ...]:
    """
    Session 79 executable artifact for UNNUMBERED-049.
    Returns the required in-scope camera-ready graph boundaries.
    """
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
    """
    Enforce concrete required outputs:
      - top-level selected_case: non-empty string
      - top-level modifications: list
      - when architect workflow_history details exist, top-level values must match
    """
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
    """
    Validate whether all critical-path features are declared in state.
    Accepts:
      - missing key: defaults to all required features present
      - sequence/set of feature names
      - mapping of feature name -> enabled bool
    """
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
    """
    Validate in-scope camera-ready boundaries.
    Accepts:
      - missing key: defaults to required boundaries
      - sequence/set of boundary names
      - mapping of boundary name -> enabled bool
    """
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


def paper_manifest_gate_node(state: dict) -> dict:
    """
    Session 9 manifest gate for paper-validator outputs.
    Defaults to bypass when feature flag is disabled.
    """
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
    """
    Session 49 complexity gate for UNNUMBERED-002-01.
    Bypasses by default unless explicitly enabled in state.
    """
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
    """
    Session 109 traceability checker for risk → mitigation + validation artifact.
    """
    links_payload = state.get("risk_links")
    if links_payload is None:
        links_payload = state.get("risk_register")
    return validate_risk_links(links_payload)


def create_graph() -> StateGraph:
    """Build graph with B1b/B1c graph wiring."""
    graph = StateGraph(GraphState)

    graph.add_node("sweep_detection_node", sweep_detection_node)
    graph.add_node("architect_node", architect_node)
    graph.add_node("required_outputs_section_node", required_outputs_section_node)
    graph.add_node("camera_ready_scope_boundary_node", camera_ready_scope_boundary_node)
    graph.add_node("intent_extraction_node", intent_extraction_node)
    graph.add_node("clarification_node", clarification_node)
    graph.add_node("clarification_handler", clarification_handler_node)
    graph.add_node("sweep_execution_handler", sweep_execution_handler_node)
    graph.add_node("paper_manifest_gate_node", paper_manifest_gate_node)
    graph.add_node("radon_cc_gate_node", radon_cc_gate_node)
    graph.add_node("risk_links_traceability_node", risk_links_traceability_node)
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
    graph.add_edge("architect_node", "required_outputs_section_node")
    graph.add_conditional_edges(
        "required_outputs_section_node",
        _route_after_required_outputs,
        {
            "camera_ready_scope_boundary_node": "camera_ready_scope_boundary_node",
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
    graph.add_edge("intent_extraction_node", "clarification_node")
    graph.add_conditional_edges(
        "clarification_node",
        _route_after_clarification,
        {
            "input_writer_node": "paper_manifest_gate_node",
            "clarification_handler": "clarification_handler",
        },
    )
    graph.add_conditional_edges(
        "paper_manifest_gate_node",
        _route_after_manifest_validation,
        {
            "radon_cc_gate_node": "radon_cc_gate_node",
            "clarification_handler": "clarification_handler",
        },
    )
    graph.add_conditional_edges(
        "radon_cc_gate_node",
        _route_after_radon_cc_gate,
        {
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
    graph.add_edge("input_writer_node", END)

    return graph
