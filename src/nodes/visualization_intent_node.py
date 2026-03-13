"""
Visualization intent normalization node.

Builds a canonical visualization_intent object from prompt + solver context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.models import GraphState
from src.models.visualization_intent import VisualizationIntent, VisualizationPlotSpec
from src.services.viz_param_extractor import (
    canonicalize_requested_plot_vars,
    convert_prompt_seconds_to_solver_time,
    extract_viz_params_from_prompt,
)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def _infer_solver_name(state: dict[str, Any]) -> str:
    plan = state.get("plan") or {}
    baseline = plan.get("baseline") if isinstance(plan, dict) else {}
    if not isinstance(baseline, dict):
        baseline = {}

    if isinstance(state.get("selected_solver"), str) and state.get("selected_solver"):
        return str(state.get("selected_solver"))
    if isinstance(plan.get("selected_solver"), str) and plan.get("selected_solver"):
        return str(plan.get("selected_solver"))
    if isinstance(baseline.get("code_name"), str) and baseline.get("code_name"):
        return str(baseline.get("code_name"))

    history = state.get("workflow_history")
    if isinstance(history, list):
        for entry in reversed(history):
            if not isinstance(entry, dict) or entry.get("node") != "architect":
                continue
            details = entry.get("details")
            if not isinstance(details, dict):
                continue
            baseline_details = details.get("baseline")
            if isinstance(baseline_details, dict):
                code_name = baseline_details.get("code_name") or baseline_details.get("code")
                if isinstance(code_name, str) and code_name.strip():
                    return code_name.strip()
    return ""


def _infer_repo_root(state: dict[str, Any], solver_name: str) -> str | None:
    config = state.get("config")
    repos = getattr(config, "repositories", None)
    if isinstance(repos, dict):
        repo_path = repos.get(solver_name)
        if repo_path:
            return str(repo_path)

    plan = state.get("plan") or {}
    baseline = plan.get("baseline") if isinstance(plan, dict) else {}
    if isinstance(baseline, dict):
        repo_path = baseline.get("repo_path")
        if repo_path:
            return str(repo_path)
    return None


def build_visualization_intent(
    *,
    prompt: str,
    solver_name: str = "",
    repo_root: str | Path | None = None,
    requested_plot_vars: list[str] | None = None,
    visualization_config: dict[str, Any] | None = None,
    prior_intent: dict[str, Any] | None = None,
) -> VisualizationIntent:
    """
    Build a canonical visualization_intent payload.

    precedence:
    - explicit requested_plot_vars / visualization_config / prior_intent
      augment prompt-derived extraction.
    """
    extracted_vars, extracted_config = extract_viz_params_from_prompt(
        prompt or "",
        code_name=solver_name or None,
        repo_root=repo_root,
    )

    prior = prior_intent if isinstance(prior_intent, dict) else {}
    prior_fields = prior.get("requested_fields", [])
    if not isinstance(prior_fields, list):
        prior_fields = []
    prior_vars = prior.get("requested_plot_vars", [])
    if not isinstance(prior_vars, list):
        prior_vars = []

    merged_requested = _dedupe_preserve_order(
        extracted_vars
        + list(requested_plot_vars or [])
        + list(prior_fields)
        + list(prior_vars)
    )
    if solver_name:
        merged_requested = canonicalize_requested_plot_vars(
            merged_requested,
            code_name=solver_name,
            repo_root=repo_root,
        )

    merged_config: dict[str, Any] = {}
    if isinstance(extracted_config, dict):
        merged_config.update(extracted_config)
    prior_config = prior.get("visualization_config", {})
    if isinstance(prior_config, dict):
        merged_config.update(prior_config)
    if isinstance(visualization_config, dict):
        merged_config.update(visualization_config)

    cadence_prompt_seconds_raw = merged_config.get("plot_interval_seconds")
    cadence_prompt_seconds: int | None = None
    if isinstance(cadence_prompt_seconds_raw, (int, float)):
        candidate = int(round(float(cadence_prompt_seconds_raw)))
        cadence_prompt_seconds = candidate if candidate > 0 else None

    adjustments: list[str] = []
    cadence_solver_time: float | None = None
    if cadence_prompt_seconds is not None:
        cadence_solver_time = convert_prompt_seconds_to_solver_time(
            solver_name,
            cadence_prompt_seconds,
        )
        merged_config["cadence_prompt_seconds"] = cadence_prompt_seconds
        if cadence_solver_time is not None:
            merged_config["cadence_solver_time"] = cadence_solver_time
            merged_config["cadence_mode"] = "time"
        else:
            fallback_steps = max(1, cadence_prompt_seconds)
            merged_config["cadence_solver_steps"] = fallback_steps
            merged_config["cadence_mode"] = "step"
            adjustments.append("cadence_fallback_to_steps_unknown_time_units")
    timestep_scope = str(merged_config.get("timesteps", "latest")).strip().lower() or "latest"
    if timestep_scope not in {"latest", "all"}:
        timestep_scope = "latest"
        merged_config["timesteps"] = timestep_scope

    solver_mappings_applied = bool(solver_name)

    plots_payload = merged_config.get("plots", [])
    parsed_plots: list[VisualizationPlotSpec] = []
    if isinstance(plots_payload, list):
        for entry in plots_payload:
            if not isinstance(entry, dict):
                continue
            field = str(entry.get("field", "")).strip()
            if not field:
                continue
            parsed_plots.append(
                VisualizationPlotSpec(
                    type=str(entry.get("type", "slice")),
                    field=field,
                    axis=str(entry.get("axis")) if entry.get("axis") is not None else None,
                )
            )

    source = "default"
    if prior:
        source = str(prior.get("source", "default")).strip().lower() or "default"
    if extracted_vars or extracted_config:
        source = "prompt"
    if not solver_mappings_applied and not merged_requested:
        source = "default"
    if source not in {"prompt", "clarification", "default"}:
        source = "default"

    return VisualizationIntent(
        requested_fields=merged_requested,
        cadence_prompt_seconds=cadence_prompt_seconds,
        cadence_solver_time=cadence_solver_time,
        timestep_scope=timestep_scope,
        plots=parsed_plots,
        solver_name=solver_name or None,
        source=source,
        adjustments=adjustments,
        visualization_config=merged_config,
    )


def resolve_visualization_intent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Return canonical visualization intent from state, with legacy fallback.
    """
    existing = state.get("visualization_intent")
    if isinstance(existing, dict):
        requested = existing.get("requested_fields", existing.get("requested_plot_vars", []))
        vis_cfg = existing.get("visualization_config", {})
        if not isinstance(requested, list):
            requested = []
        if not isinstance(vis_cfg, dict):
            vis_cfg = {}
        prepared = dict(existing)
        prepared["requested_fields"] = _dedupe_preserve_order([str(v) for v in requested])
        prepared["visualization_config"] = vis_cfg
        if "cadence_prompt_seconds" not in prepared and isinstance(prepared.get("cadence_seconds"), (int, float)):
            converted_prompt = int(round(float(prepared["cadence_seconds"])))
            prepared["cadence_prompt_seconds"] = converted_prompt if converted_prompt > 0 else None
        timestep_scope = str(prepared.get("timestep_scope", vis_cfg.get("timesteps", "latest"))).strip().lower()
        prepared["timestep_scope"] = timestep_scope if timestep_scope in {"latest", "all"} else "latest"
        prepared["source"] = prepared.get("source") if prepared.get("source") in {"prompt", "clarification", "default"} else "default"
        try:
            model = VisualizationIntent.model_validate(prepared)
            return model.model_dump()
        except Exception:
            # Keep existing behavior if legacy payload is malformed.
            return prepared

    solver_name = _infer_solver_name(state)
    repo_root = _infer_repo_root(state, solver_name)
    prompt = str(state.get("prompt") or state.get("user_requirement") or "")
    model = build_visualization_intent(
        prompt=prompt,
        solver_name=solver_name,
        repo_root=repo_root,
        requested_plot_vars=[],
        visualization_config={},
        prior_intent=None,
    )
    return model.model_dump()


def visualization_intent_node(state: GraphState) -> dict[str, Any]:
    """
    Graph node that materializes visualization_intent into canonical state.
    """
    solver_name = _infer_solver_name(state)
    repo_root = _infer_repo_root(state, solver_name)
    prompt = str(state.get("prompt") or state.get("user_requirement") or "")
    prior_intent = state.get("visualization_intent") if isinstance(state.get("visualization_intent"), dict) else {}

    model = build_visualization_intent(
        prompt=prompt,
        solver_name=solver_name,
        repo_root=repo_root,
        requested_plot_vars=[],
        visualization_config={},
        prior_intent=prior_intent,
    )
    intent = model.model_dump()

    return {
        "visualization_intent": intent,
        "requested_plot_vars": list(model.requested_fields),
        "visualization_config": dict(intent.get("visualization_config", {})),
    }
