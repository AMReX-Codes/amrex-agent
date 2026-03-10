"""Meta-visualization artifacts for completed sweep results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def generate_meta_plots(summary: dict[str, Any], output_dir: Path) -> Path:
    """
    Generate parameter sweep plots from summary.
    Write to output_dir/meta_plots/.
    Create directory if absent.
    Return meta_plots path.

    Uses only completed children data.
    Failed children silently excluded.
    If no completed children: create empty
    meta_plots dir, return path, no exception.

    No matplotlib required - write a simple
    JSON data file per plot as the artifact.
    Tests check file existence, not rendering.
    """
    meta_plots_dir = output_dir / "meta_plots"
    meta_plots_dir.mkdir(parents=True, exist_ok=True)

    points = _collect_plot_data(summary)
    if not points:
        return meta_plots_dir

    metric_names = sorted({name for point in points for name in point["metrics"]})
    if not metric_names:
        return meta_plots_dir

    sweep_id = str(summary.get("sweep_id", "sweep"))
    parameter = str(summary.get("parameter", "parameter"))
    safe_sweep = _safe_token(sweep_id)
    safe_parameter = _safe_token(parameter)

    for metric_name in metric_names:
        metric_points = []
        for point in points:
            if metric_name in point["metrics"]:
                metric_points.append({"x": point["x"], "y": point["metrics"][metric_name]})

        if not metric_points:
            continue

        artifact = {
            "sweep_id": sweep_id,
            "parameter": parameter,
            "metric": metric_name,
            "points": metric_points,
        }
        artifact_name = f"{safe_sweep}_{safe_parameter}_{_safe_token(metric_name)}_plot.json"
        artifact_path = meta_plots_dir / artifact_name
        artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")

    return meta_plots_dir


def _collect_plot_data(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract parameter_value and any numeric
    metrics from completed children only.
    Returns list of {x: value, metrics: dict}.
    """
    children = summary.get("children", [])
    if not isinstance(children, list):
        return []

    points: list[dict[str, Any]] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("status") != "completed":
            continue

        raw_metrics = child.get("result_metrics", {})
        if not isinstance(raw_metrics, dict):
            raw_metrics = {}

        metrics: dict[str, float] = {}
        for key, value in raw_metrics.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                metrics[key] = float(value)

        points.append({"x": child.get("parameter_value"), "metrics": metrics})

    return points


def _safe_token(value: str) -> str:
    """Keep filenames stable and filesystem-safe."""
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)

