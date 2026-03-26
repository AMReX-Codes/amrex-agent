"""Paper Validator node for Amendment B4.5 Mode 1 behavior."""

from __future__ import annotations

from typing import Any

from src.models import GraphState


def paper_validator_node(state: GraphState) -> dict[str, Any]:
    """
    Run Mode 1 paper validation and expose graph-routing state updates.

    Mode 1 outputs are intentionally lightweight in this session:
    - paper_validator_mode1_complete
    - validation_manifest (when validation passes)
    - resolved_config pre-populated from manifest.base_resolved_config
    """
    validator_result = _validate_mode1_prereqs(state)
    if not validator_result.get("paper_validation_passed", False):
        return {
            **validator_result,
            "paper_validator_mode1_complete": False,
        }

    manifest = _build_validation_manifest(state)
    return {
        **validator_result,
        "paper_validator_mode1_complete": True,
        "validation_manifest": manifest,
        "resolved_config": dict(manifest.get("base_resolved_config", {})),
    }


def _validate_mode1_prereqs(state: GraphState) -> dict[str, Any]:
    """Validate minimum inputs needed for Mode 1 execution."""
    plan = state.get("plan")
    if not isinstance(plan, dict):
        return {
            "paper_validation_passed": False,
            "paper_validation_status": "failed",
            "paper_validation_reason": "missing_plan",
            "paper_design_deferred": False,
        }

    design = plan.get("paper_design")
    if not isinstance(design, dict):
        return {
            "paper_validation_passed": False,
            "paper_validation_status": "failed",
            "paper_validation_reason": "missing_paper_design",
            "paper_design_deferred": False,
        }

    if bool(design.get("deferred", False)):
        return {
            "paper_validation_passed": True,
            "paper_validation_status": "deferred",
            "paper_validation_reason": "design_deferred",
            "paper_design_deferred": True,
        }

    sections = design.get("sections")
    has_sections = isinstance(sections, list) and len(sections) > 0
    if not has_sections:
        return {
            "paper_validation_passed": False,
            "paper_validation_status": "failed",
            "paper_validation_reason": "missing_sections",
            "paper_design_deferred": False,
        }

    return {
        "paper_validation_passed": True,
        "paper_validation_status": "passed",
        "paper_validation_reason": "ok",
        "paper_design_deferred": False,
    }


def _build_validation_manifest(state: GraphState) -> dict[str, Any]:
    """Build a minimal serializable validation manifest for Mode 1."""
    plan = state.get("plan") if isinstance(state.get("plan"), dict) else {}
    design = plan.get("paper_design") if isinstance(plan.get("paper_design"), dict) else {}

    base_resolved_config = design.get("base_resolved_config")
    if not isinstance(base_resolved_config, dict):
        fallback = state.get("resolved_config")
        base_resolved_config = dict(fallback) if isinstance(fallback, dict) else {}

    raw_conditions = design.get("conditions")
    conditions = raw_conditions if isinstance(raw_conditions, list) else []
    if not conditions:
        conditions = [base_resolved_config]

    return {
        "paper_source": state.get("paper_source"),
        "paper_input_type": state.get("paper_input_type", "pdf"),
        "conditions": conditions,
        "is_sweep": len(conditions) > 1,
        "sweep_parameter": design.get("sweep_parameter"),
        "base_resolved_config": base_resolved_config,
    }
