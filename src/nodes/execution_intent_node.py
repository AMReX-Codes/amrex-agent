"""
Execution intent normalization node.

Builds a canonical execution_intent object from prompt + resolved config context.
"""

from __future__ import annotations

import re
from typing import Any

from src.models import GraphState
from src.models.execution_intent import ExecutionIntent

_PROCS_RE = re.compile(
    r"\b(\d+)\s*(?:mpi\s*)?(?:proc|procs|process(?:es)?|rank|ranks|task|tasks|ntasks?)\b",
    re.IGNORECASE,
)
_WALL_HOURS_RE = re.compile(r"\b(\d+)\s*(?:h|hr|hrs|hour|hours)\b", re.IGNORECASE)
_WALL_MINS_RE = re.compile(r"\b(\d+)\s*(?:m|min|mins|minute|minutes)\b", re.IGNORECASE)


def _coerce_positive_int(value: Any) -> int | None:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return None
    return candidate if candidate > 0 else None


def _coerce_walltime(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not token:
        return None
    if re.fullmatch(r"\d{2}:\d{2}:\d{2}", token):
        return token
    return None


def _read_execution_config_from_resolved(resolved: dict[str, Any]) -> dict[str, Any]:
    execution = resolved.get("execution")
    if isinstance(execution, dict):
        return dict(execution)
    return {}


def _extract_prompt_environment(prompt: str) -> str | None:
    lower = prompt.lower()
    if "perlmutter" in lower:
        return "perlmutter"
    if "local" in lower:
        return "local"
    if "mcp" in lower:
        return "mcp"
    return None


def _extract_prompt_run_mode(prompt: str) -> str | None:
    lower = prompt.lower()
    if "dry run" in lower or "run_mode dry" in lower:
        return "dry"
    if "stage only" in lower or "run_mode stage" in lower:
        return "stage"
    if "submit only" in lower or "run_mode submit" in lower:
        return "submit"
    if "full run" in lower or "run_mode full" in lower:
        return "full"
    return None


def _extract_prompt_total_procs(prompt: str) -> int | None:
    match = _PROCS_RE.search(prompt)
    if not match:
        return None
    return _coerce_positive_int(match.group(1))


def _extract_prompt_walltime(prompt: str) -> str | None:
    hours_match = _WALL_HOURS_RE.search(prompt)
    mins_match = _WALL_MINS_RE.search(prompt)
    if not hours_match and not mins_match:
        return None
    hours = int(hours_match.group(1)) if hours_match else 0
    mins = int(mins_match.group(1)) if mins_match else 0
    mins = mins % 60
    return f"{hours:02d}:{mins:02d}:00"


def _parse_from_prompt(prompt: str) -> dict[str, Any]:
    return {
        "environment": _extract_prompt_environment(prompt),
        "run_mode": _extract_prompt_run_mode(prompt),
        "total_procs": _extract_prompt_total_procs(prompt),
        "walltime": _extract_prompt_walltime(prompt),
    }


def _merge_execution_values(resolved: dict[str, Any], prompt: str, prior: dict[str, Any]) -> tuple[dict[str, Any], str]:
    execution = _read_execution_config_from_resolved(resolved)
    prompt_values = _parse_from_prompt(prompt)

    merged: dict[str, Any] = {}
    merged.update(prompt_values)
    merged.update(prior)
    merged.update(execution)
    # Flat legacy aliases on resolved_config take precedence over nested defaults.
    for source_key in ("environment", "run_mode", "run_ntasks", "mpi_ranks", "total_procs"):
        if source_key in resolved:
            merged[source_key] = resolved.get(source_key)

    source = "default"
    if any(prompt_values.values()):
        source = "prompt"
    if execution:
        source = "clarification"
    if prior:
        source = str(prior.get("source", source))
    if source not in {"prompt", "clarification", "default"}:
        source = "default"
    return merged, source


def build_execution_intent(
    *,
    prompt: str,
    resolved_config: dict[str, Any] | None = None,
    prior_intent: dict[str, Any] | None = None,
) -> ExecutionIntent:
    resolved = dict(resolved_config or {})
    prior = dict(prior_intent or {})
    merged, source = _merge_execution_values(resolved, prompt, prior)

    total_procs = (
        _coerce_positive_int(merged.get("run_ntasks"))
        or _coerce_positive_int(merged.get("mpi_ranks"))
        or _coerce_positive_int(merged.get("total_procs"))
    )
    walltime = _coerce_walltime(merged.get("walltime")) or _extract_prompt_walltime(prompt)
    environment = merged.get("environment")
    run_mode = merged.get("run_mode")

    if isinstance(environment, str):
        environment = environment.strip().lower() or None
    else:
        environment = None
    if isinstance(run_mode, str):
        run_mode = run_mode.strip().lower() or None
    else:
        run_mode = None

    payload = {
        "environment": environment,
        "run_mode": run_mode,
        "total_procs": total_procs,
        "walltime": walltime,
        "qos": merged.get("qos"),
        "constraint": merged.get("constraint"),
        "account": merged.get("account") or merged.get("superfacility_account"),
        "system": merged.get("system"),
        "source": source,
        "adjustments": list(prior.get("adjustments", [])) if isinstance(prior.get("adjustments"), list) else [],
        "execution_config": execution_payload_from_merged(merged, total_procs, walltime, environment, run_mode),
    }
    return ExecutionIntent.model_validate(payload)


def execution_payload_from_merged(
    merged: dict[str, Any],
    total_procs: int | None,
    walltime: str | None,
    environment: str | None,
    run_mode: str | None,
) -> dict[str, Any]:
    payload = dict(merged.get("execution_config", {})) if isinstance(merged.get("execution_config"), dict) else {}
    if total_procs is not None:
        payload["total_procs"] = total_procs
    if walltime is not None:
        payload["walltime"] = walltime
    if environment is not None:
        payload["environment"] = environment
    if run_mode is not None:
        payload["run_mode"] = run_mode
    return payload


def resolve_execution_intent(state: dict[str, Any]) -> dict[str, Any]:
    existing = state.get("execution_intent")
    if isinstance(existing, dict):
        try:
            return ExecutionIntent.model_validate(existing).model_dump()
        except Exception:
            pass

    prompt = str(state.get("prompt") or state.get("user_requirement") or "")
    resolved_config = state.get("resolved_config")
    model = build_execution_intent(
        prompt=prompt,
        resolved_config=resolved_config if isinstance(resolved_config, dict) else {},
        prior_intent=None,
    )
    return model.model_dump()


def execution_intent_node(state: GraphState) -> dict[str, Any]:
    prompt = str(state.get("prompt") or state.get("user_requirement") or "")
    resolved_config = state.get("resolved_config") if isinstance(state.get("resolved_config"), dict) else {}
    prior_intent = state.get("execution_intent") if isinstance(state.get("execution_intent"), dict) else {}
    model = build_execution_intent(
        prompt=prompt,
        resolved_config=resolved_config,
        prior_intent=prior_intent,
    )
    return {"execution_intent": model.model_dump()}
