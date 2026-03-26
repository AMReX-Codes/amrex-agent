"""Deterministic visualization intent extraction and solver-field mapping."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class VizMappingCatalogUnavailableError(RuntimeError):
    """Raised when solver code-derived viz catalog is required but unavailable."""


QUANTITY_KEYWORDS: dict[str, list[str]] = {
    "temperature": ["temperature", "temp", "thermal"],
    "velocity": ["velocity", "speed"],
    "vertical_velocity": [
        "vertical velocity",
        "vertical_velocity",
        "w-velocity",
        "w velocity",
        "updraft",
        "downdraft",
    ],
    "pressure": ["pressure", "pres"],
    "density": ["density", "rho"],
    "vorticity": ["vorticity", "vort"],
    "cloud_water": ["cloud water", "cloud_water", "liquid water", "cloud liquid", "qc"],
}

COLOR_SCALE_KEYWORDS: dict[str, list[str]] = {
    "logarithmic": ["log scale", "log-scale", "logarithmic", "log color"],
    "linear": ["linear scale", "linear color"],
}

VIZ_TYPE_KEYWORDS: dict[str, list[str]] = {
    "pseudocolor": ["pseudocolor", "false color", "colormap", "heatmap"],
    "contour": ["contour", "isolines"],
    "line": ["line plot", "time series"],
}

PLOTFILE_VAR_PARAM: dict[str, str] = {
    "AMReX": "amr.plot_vars",
    "PeleC": "amr.plot_vars",
    "PeleLMeX": "peleLM.derive_plot_vars",
    "ERF": "erf.plot_vars_1",
    "REMORA": "amr.plot_vars",
}
PLOTFILE_VAR_PARAM_DEFAULT = "amr.plot_vars"

PLOTFILE_PERIOD_PARAM: dict[str, str] = {
    "AMReX": "amr.plot_per",
    "PeleLMeX": "amr.plot_per",
    "ERF": "erf.plot_per_1",
    "REMORA": "remora.plot_int_time",
}

PLOTFILE_STEP_INTERVAL_PARAM: dict[str, str] = {
    "AMReX": "amr.plot_int",
    "PeleLMeX": "amr.plot_int",
    "ERF": "erf.plot_int_1",
    "REMORA": "remora.plot_int",
}


def _extract_quantities(prompt_lower: str) -> list[str]:
    requested: list[str] = []
    has_vertical_velocity = any(
        keyword in prompt_lower for keyword in QUANTITY_KEYWORDS["vertical_velocity"]
    )
    for quantity, keywords in QUANTITY_KEYWORDS.items():
        if quantity == "velocity" and has_vertical_velocity:
            continue
        if any(keyword in prompt_lower for keyword in keywords):
            requested.append(quantity)
    return requested


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _extract_color_scale(prompt_lower: str) -> str | None:
    for color_scale, keywords in COLOR_SCALE_KEYWORDS.items():
        if any(keyword in prompt_lower for keyword in keywords):
            return color_scale
    return None


def _extract_viz_type(prompt_lower: str) -> str | None:
    for viz_type, keywords in VIZ_TYPE_KEYWORDS.items():
        if any(keyword in prompt_lower for keyword in keywords):
            return viz_type
    return None


def _extract_plot_interval_seconds(prompt_lower: str) -> int | None:
    pattern = re.compile(
        r"\b(?:every|each)\s+(\d+(?:\.\d+)?)\s*"
        r"(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)\b"
    )
    match = pattern.search(prompt_lower)
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("h"):
        seconds = amount * 3600.0
    elif unit.startswith("m"):
        seconds = amount * 60.0
    else:
        seconds = amount
    if seconds <= 0:
        return None
    return int(round(seconds))


def _extract_timestep_scope(prompt_lower: str, has_cadence: bool) -> str | None:
    if has_cadence:
        return "all"
    if any(
        kw in prompt_lower
        for kw in ("movie", "animation", "evolution", "all timesteps", "all plotfiles")
    ):
        return "all"
    return None


def _normalize_tier1(raw: Any) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, dict):
        raw = {}
    for token, spec in raw.items():
        token_name = str(token).strip()
        if not token_name:
            continue
        aliases = [token_name]
        if isinstance(spec, dict):
            for alias in spec.get("aliases", []) or []:
                alias_str = str(alias).strip()
                if alias_str:
                    aliases.append(alias_str)
        normalized[token_name] = {"aliases": _dedupe_preserve_order(aliases)}
    return normalized


def _normalize_candidates(raw: Any) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(raw, dict):
        return out
    for token, entries in raw.items():
        token_name = str(token).strip()
        if not token_name or not isinstance(entries, list):
            continue
        token_entries: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            aliases = [name]
            for alias in entry.get("aliases", []) or []:
                alias_str = str(alias).strip()
                if alias_str:
                    aliases.append(alias_str)
            token_entries.append(
                {
                    "name": name,
                    "aliases": _dedupe_preserve_order(aliases),
                    "units": entry.get("units"),
                    "source": entry.get("source"),
                    "description": entry.get("description"),
                }
            )
        if token_entries:
            out[token_name] = token_entries
    return out


def _build_alias_index(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    alias_index: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        for alias in entry.get("aliases", []) or []:
            key = str(alias).strip().lower()
            if not key:
                continue
            alias_index.setdefault(key, []).append(entry)
    return alias_index


def get_plot_var_param_candidates(code_name: str) -> list[str]:
    if not code_name:
        return [PLOTFILE_VAR_PARAM_DEFAULT]
    try:
        from database.configs.registry import get_config_class

        config_cls = get_config_class(code_name)
        getter = getattr(config_cls, "get_plot_var_param_candidates", None)
        if callable(getter):
            values = getter()
            if isinstance(values, list):
                cleaned = [str(v).strip() for v in values if str(v).strip()]
                if cleaned:
                    return _dedupe_preserve_order(cleaned)
    except Exception as exc:
        logger.debug("plot-var candidates lookup failed for %s: %s", code_name, exc)

    legacy = PLOTFILE_VAR_PARAM.get(code_name)
    if legacy:
        return [legacy]
    logger.warning("Unknown solver '%s' - falling back to %s", code_name, PLOTFILE_VAR_PARAM_DEFAULT)
    return [PLOTFILE_VAR_PARAM_DEFAULT]


def get_plotfile_var_param(code_name: str) -> str:
    return get_plot_var_param_candidates(code_name)[0]


def resolve_viz_field_mapping(
    requested: list[str],
    *,
    code_name: str | None,
    repo_root: str | Path | None = None,
    require_solver_catalog: bool = True,
) -> dict[str, Any]:
    requested_tokens = _dedupe_preserve_order([str(t).strip() for t in requested if str(t).strip()])
    result: dict[str, Any] = {
        "resolved_fields": [],
        "candidate_fields_by_token": {},
        "unresolved_tokens": [],
        "ambiguous_tokens": [],
        "mapping_source": "none",
        "mapping_confidence": 1.0,
    }
    if not requested_tokens:
        return result
    if not code_name:
        result["resolved_fields"] = requested_tokens
        result["mapping_source"] = "semantic_only"
        return result

    from database.configs.registry import get_config_class

    config_cls = get_config_class(code_name)
    unknown_solver = getattr(config_cls, "code_name", "amrex_base") == "amrex_base" and code_name not in PLOTFILE_VAR_PARAM
    tier1_getter = getattr(config_cls, "get_viz_tier1_intents", None)
    tier2_getter = getattr(config_cls, "build_viz_tier2_candidates", None)
    tier1 = _normalize_tier1(tier1_getter() if callable(tier1_getter) else {})
    tier2_raw = tier2_getter(Path(repo_root) if repo_root else None) if callable(tier2_getter) else {}
    tier2 = _normalize_candidates(tier2_raw)
    if not tier2:
        catalog_getter = getattr(config_cls, "get_viz_variable_catalog", None)
        if callable(catalog_getter):
            catalog = catalog_getter(Path(repo_root) if repo_root else None) or []
            normalized_catalog = _normalize_candidates(
                {
                    token: catalog
                    for token in (list(tier1.keys()) or requested_tokens)
                }
            )
            tier2 = normalized_catalog

    if require_solver_catalog and not tier2 and not unknown_solver:
        repo_hint = str(repo_root) if repo_root else "<solver-repo-root>"
        raise VizMappingCatalogUnavailableError(
            "Visualization mapping requires solver code-derived catalog but none was found for "
            f"'{code_name}'. Set a valid repository path (e.g. {repo_hint}) and retry."
        )
    if not tier2 and unknown_solver:
        result["resolved_fields"] = requested_tokens
        result["mapping_source"] = "semantic_only"
        return result

    combined_entries: list[dict[str, Any]] = []
    for entries in tier2.values():
        combined_entries.extend(entries)
    alias_index = _build_alias_index(combined_entries)

    resolved: list[str] = []
    for token in requested_tokens:
        token_key = token.lower()
        candidates = list(alias_index.get(token_key, []))
        if not candidates:
            semantic_spec = tier1.get(token, {})
            for alias in semantic_spec.get("aliases", []) or [token]:
                candidates.extend(alias_index.get(str(alias).lower(), []))
        if not candidates and token in tier2:
            candidates.extend(tier2.get(token, []))

        unique: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for entry in candidates:
            name = str(entry.get("name", "")).strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            unique.append(entry)

        if len(unique) == 1:
            resolved.append(unique[0]["name"])
            result["candidate_fields_by_token"][token] = unique
            continue
        if len(unique) > 1:
            result["candidate_fields_by_token"][token] = unique
            result["ambiguous_tokens"].append(token)
            continue
        result["unresolved_tokens"].append(token)

    result["resolved_fields"] = _dedupe_preserve_order(resolved)
    result["mapping_source"] = "solver_catalog"
    total = len(requested_tokens)
    mapped = len(result["resolved_fields"])
    result["mapping_confidence"] = float(mapped / total) if total else 1.0
    return result


def canonicalize_requested_plot_vars(
    requested: list[str],
    code_name: str | None = None,
    repo_root: str | Path | None = None,
) -> list[str]:
    if not requested:
        return []
    if not code_name:
        return _dedupe_preserve_order(requested)
    mapping = resolve_viz_field_mapping(
        requested,
        code_name=code_name,
        repo_root=repo_root,
        require_solver_catalog=True,
    )
    return mapping["resolved_fields"]


def get_plotfile_period_param(code_name: str) -> str | None:
    if not code_name:
        return None

    try:
        from database.configs.registry import get_config_class

        config_cls = get_config_class(code_name)
        getter = getattr(config_cls, "get_plotfile_period_param", None)
        if callable(getter):
            value = getter()
            if isinstance(value, str) and value.strip():
                return value.strip()
            return None
    except Exception as exc:
        logger.debug("plotfile-period param lookup via config failed for %s: %s", code_name, exc)

    return PLOTFILE_PERIOD_PARAM.get(code_name)


def get_plotfile_step_interval_param(code_name: str) -> str | None:
    if not code_name:
        return None

    try:
        from database.configs.registry import get_config_class

        config_cls = get_config_class(code_name)
        getter = getattr(config_cls, "get_plotfile_step_interval_param", None)
        if callable(getter):
            value = getter()
            if isinstance(value, str) and value.strip():
                return value.strip()
            return None
    except Exception as exc:
        logger.debug("plotfile-step param lookup via config failed for %s: %s", code_name, exc)

    return PLOTFILE_STEP_INTERVAL_PARAM.get(code_name)


def convert_prompt_seconds_to_solver_time(code_name: str, prompt_seconds: int | float | None) -> float | None:
    if prompt_seconds is None:
        return None
    try:
        seconds = float(prompt_seconds)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    if not code_name:
        return None

    try:
        from database.configs.registry import get_config_class

        config_cls = get_config_class(code_name)
        if getattr(config_cls, "code_name", "") == "amrex_base" and code_name not in PLOTFILE_PERIOD_PARAM:
            return None
        supports_fn = getattr(config_cls, "supports_physical_time_cadence", None)
        if callable(supports_fn) and supports_fn() is False:
            return None
        converter = getattr(config_cls, "convert_plot_cadence_prompt_seconds_to_solver_time", None)
        if callable(converter):
            converted = converter(seconds)
            if converted is None:
                return None
            converted_value = float(converted)
            if converted_value <= 0:
                return None
            return converted_value
    except Exception as exc:
        logger.debug("cadence conversion via config failed for %s: %s", code_name, exc)

    if code_name in PLOTFILE_PERIOD_PARAM:
        return seconds
    return None


def extract_viz_params_from_prompt(
    prompt: str,
    code_name: str | None = None,
    repo_root: str | Path | None = None,
) -> tuple[list[str], dict]:
    del code_name, repo_root
    normalized = (prompt or "").lower()
    requested_plot_vars = _dedupe_preserve_order(_extract_quantities(normalized))

    visualization_config: dict[str, Any] = {}
    color_scale = _extract_color_scale(normalized)
    if color_scale:
        visualization_config["color_scale"] = color_scale

    viz_type = _extract_viz_type(normalized)
    if viz_type:
        visualization_config["viz_type"] = viz_type

    plot_interval_seconds = _extract_plot_interval_seconds(normalized)
    if plot_interval_seconds is not None:
        visualization_config["plot_interval_seconds"] = plot_interval_seconds

    timestep_scope = _extract_timestep_scope(
        normalized,
        has_cadence=plot_interval_seconds is not None,
    )
    if timestep_scope:
        visualization_config["timesteps"] = timestep_scope

    return requested_plot_vars, visualization_config
