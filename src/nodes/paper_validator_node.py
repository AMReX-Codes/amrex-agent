"""Paper validator mode 2 node (post-visualization report synthesis)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _resolve_ssim_threshold(state: dict[str, Any]) -> float:
    config = state.get("config")
    if isinstance(config, dict):
        value = config.get("ssim_pass_threshold", 0.85)
    else:
        value = getattr(config, "ssim_pass_threshold", 0.85)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.85


def _match_generated_plot(
    figure: dict[str, Any],
    generated_paths: list[str],
) -> str | None:
    quantity = str(figure.get("quantity_of_interest", "")).lower().strip()
    plot_type = str(figure.get("plot_type", "")).lower().strip()
    for candidate in generated_paths:
        name = Path(candidate).name.lower()
        if quantity and quantity not in name:
            continue
        if plot_type and plot_type not in name:
            continue
        return candidate
    return generated_paths[0] if generated_paths and not (quantity or plot_type) else None


def compute_ssim_score(reference_path: str, generated_path: str) -> tuple[float | None, str | None]:
    """Return SSIM score for two images, or an error reason when unavailable."""
    try:
        from PIL import Image
        import numpy as np
        from skimage.metrics import structural_similarity

        ref_image = Image.open(reference_path).convert("L")
        gen_image = Image.open(generated_path).convert("L").resize(ref_image.size)
        ref_array = np.asarray(ref_image)
        gen_array = np.asarray(gen_image)
        score = structural_similarity(ref_array, gen_array, data_range=255)
        return float(score), None
    except Exception as exc:  # pragma: no cover - exercised via monkeypatch in unit tests
        return None, f"ssim_computation_failed:{type(exc).__name__}"


def _figure_result(
    figure_id: str,
    reference_path: str,
    generated_path: str | None,
    threshold: float,
    score: float | None,
    failure_reason: str | None,
) -> dict[str, Any]:
    passed = score is not None and score >= threshold and failure_reason is None
    return {
        "figure_id": figure_id,
        "reference_image_path": reference_path,
        "generated_image_path": generated_path or "",
        "ssim_score": score,
        "pass_threshold": threshold,
        "passed": passed,
        "failure_reason": failure_reason,
    }


def paper_validator_node(state: dict[str, Any]) -> dict[str, Any]:
    manifest = state.get("validation_manifest")
    if not isinstance(manifest, dict):
        return {"paper_validator_mode2_complete": False}

    generated_paths = state.get("visualization_output_paths")
    if not isinstance(generated_paths, list):
        generated_paths = state.get("visualization_images")
    if not isinstance(generated_paths, list):
        generated_paths = []

    threshold = _resolve_ssim_threshold(state)
    figures = manifest.get("figures", [])
    if not isinstance(figures, list):
        figures = []

    results: list[dict[str, Any]] = []
    failed_figures: list[str] = []
    n_skipped = 0
    scores: list[float] = []

    for index, figure in enumerate(figures):
        if not isinstance(figure, dict):
            continue
        figure_id = str(figure.get("figure_id") or f"figure_{index + 1}")
        reference_path = str(figure.get("reference_image_path", ""))
        generated_path = _match_generated_plot(figure, generated_paths)
        if not generated_path:
            n_skipped += 1
            failed_figures.append(figure_id)
            results.append(
                _figure_result(
                    figure_id=figure_id,
                    reference_path=reference_path,
                    generated_path=None,
                    threshold=threshold,
                    score=None,
                    failure_reason="no_matching_generated_plot",
                )
            )
            continue

        score, error = compute_ssim_score(reference_path, generated_path)
        if score is not None:
            scores.append(score)
        result = _figure_result(
            figure_id=figure_id,
            reference_path=reference_path,
            generated_path=generated_path,
            threshold=threshold,
            score=score,
            failure_reason=error if score is None else None,
        )
        if not result["passed"]:
            failed_figures.append(figure_id)
        results.append(result)

    overall_mean = sum(scores) / len(scores) if scores else None
    report = {
        "paper_source": manifest.get("paper_source", ""),
        "overall_ssim_mean": overall_mean,
        "overall_passed": len(failed_figures) == 0 and len(results) > 0,
        "figures": results,
        "failed_figures": failed_figures,
        "reproduction_confidence": overall_mean,
        "n_figures_compared": len(results) - n_skipped,
        "n_figures_skipped": n_skipped,
    }
    return {
        "validation_report": report,
        "paper_validator_mode2_complete": True,
        "reproduction_confidence": overall_mean,
    }
