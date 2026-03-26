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
    if not isinstance(state, dict):
        return {"paper_validator_mode2_complete": False}

    manifest = state.get("validation_manifest")
    if isinstance(manifest, dict):
        return _run_mode2_validation(state, manifest)

    # Compatibility passthrough for legacy call paths without planning context.
    if (
        not isinstance(state.get("plan"), dict)
        and state
        and not bool(state.get("paper_validator_enabled"))
    ):
        return state

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


def compute_ssim_score(reference_path: str, generated_path: str) -> tuple[float | None, str | None]:
    """Compute SSIM score for a figure pair. Placeholder implementation for compatibility."""
    _ = (reference_path, generated_path)
    return None, "ssim_not_implemented"


def _run_mode2_validation(state: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    figures_raw = manifest.get("figures")
    figures = figures_raw if isinstance(figures_raw, list) else []

    generated_raw = state.get("visualization_output_paths")
    if not isinstance(generated_raw, list):
        generated_raw = state.get("visualization_images")
    generated_paths = [path for path in generated_raw if isinstance(path, str)] if isinstance(generated_raw, list) else []

    config = state.get("config")
    threshold_raw = config.get("ssim_pass_threshold") if isinstance(config, dict) else getattr(config, "ssim_pass_threshold", 0.85)
    try:
        ssim_threshold = float(threshold_raw)
    except (TypeError, ValueError):
        ssim_threshold = 0.85

    compared_scores: list[float] = []
    failed_figures: list[str] = []
    report_rows: list[dict[str, Any]] = []
    skipped = 0

    for index, figure in enumerate(figures):
        if not isinstance(figure, dict):
            continue
        figure_id = str(figure.get("figure_id") or f"figure_{index + 1}")
        quantity = str(figure.get("quantity_of_interest") or "").lower()
        ref_path = figure.get("reference_image_path")
        generated_match = None
        for candidate in generated_paths:
            if quantity and quantity in candidate.lower():
                generated_match = candidate
                break

        if not generated_match:
            skipped += 1
            failed_figures.append(figure_id)
            report_rows.append({"figure_id": figure_id, "status": "skipped", "reason": "generated_image_missing"})
            continue

        score, error = compute_ssim_score(str(ref_path or ""), generated_match)
        if isinstance(score, (int, float)):
            score = float(score)
            compared_scores.append(score)
            passed = score >= ssim_threshold
            if not passed:
                failed_figures.append(figure_id)
            report_rows.append(
                {
                    "figure_id": figure_id,
                    "status": "passed" if passed else "failed",
                    "ssim_score": score,
                    "ssim_threshold": ssim_threshold,
                    "generated_image_path": generated_match,
                }
            )
            continue

        failed_figures.append(figure_id)
        report_rows.append(
            {
                "figure_id": figure_id,
                "status": "failed",
                "reason": error or "ssim_unavailable",
                "generated_image_path": generated_match,
            }
        )

    overall_mean = (sum(compared_scores) / len(compared_scores)) if compared_scores else None
    report = {
        "paper_source": manifest.get("paper_source"),
        "figures": report_rows,
        "n_figures_compared": len(compared_scores),
        "n_figures_skipped": skipped,
        "failed_figures": failed_figures,
        "overall_ssim_mean": overall_mean,
        "reproduction_confidence": overall_mean,
        "overall_passed": bool(report_rows) and len(failed_figures) == 0,
    }
    return {
        "paper_validator_mode2_complete": True,
        "validation_report": report,
        "reproduction_confidence": overall_mean,
    }
