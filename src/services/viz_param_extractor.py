"""
Deterministic visualization parameter extraction from user prompt text.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

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

# Schema source: database/schemas/ encodes concrete parameter keys per solver.
# This mapping was derived from schema inspection. If a new solver config is
# added to database/configs/, add its plotfile var parameter name here.
# Long-term: this mapping should be declared in each solver's BaseAMReXConfig
# subclass as a class-level attribute: plotfile_var_param: str = 'amr.plot_vars'
PLOTFILE_VAR_PARAM: dict[str, str] = {
    "AMReX": "amr.plot_vars",
    "PeleC": "amr.plot_vars",
    "PeleLMeX": "peleLM.derive_plot_vars",
    "ERF": "amr.plot_vars",
    "REMORA": "amr.plot_vars",
}
PLOTFILE_VAR_PARAM_DEFAULT = "amr.plot_vars"


def _extract_quantities(prompt_lower: str) -> list[str]:
    requested: list[str] = []
    has_vertical_velocity = any(
        keyword in prompt_lower for keyword in QUANTITY_KEYWORDS["vertical_velocity"]
    )
    for quantity, keywords in QUANTITY_KEYWORDS.items():
        if quantity == "velocity" and has_vertical_velocity:
            # Avoid double-counting generic velocity from "vertical velocity".
            continue
        if any(keyword in prompt_lower for keyword in keywords):
            requested.append(quantity)
    return requested


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


def get_plotfile_var_param(code_name: str) -> str:
    """
    Return the code-specific inputs file parameter name for plotfile variables.

    Falls back to amr.plot_vars with a warning for unknown solvers.
    """
    if not code_name:
        logger.warning("Unknown solver '' - falling back to %s", PLOTFILE_VAR_PARAM_DEFAULT)
        return PLOTFILE_VAR_PARAM_DEFAULT

    if code_name in PLOTFILE_VAR_PARAM:
        return PLOTFILE_VAR_PARAM[code_name]

    logger.warning("Unknown solver '%s' - falling back to %s", code_name, PLOTFILE_VAR_PARAM_DEFAULT)
    return PLOTFILE_VAR_PARAM_DEFAULT


def extract_viz_params_from_prompt(prompt: str) -> tuple[list[str], dict]:
    """
    Extract visualization parameters from prompt.

    Keyword matching only. No LLM. Deterministic.
    Returns empty list and empty dict when nothing found.

    B1 handoff: superseded by Intent Extraction Node when
    enable_intent_extraction=True.
    """
    normalized = (prompt or "").lower()
    requested_plot_vars = _extract_quantities(normalized)

    visualization_config: dict[str, str] = {}
    color_scale = _extract_color_scale(normalized)
    if color_scale:
        visualization_config["color_scale"] = color_scale

    viz_type = _extract_viz_type(normalized)
    if viz_type:
        visualization_config["viz_type"] = viz_type

    return requested_plot_vars, visualization_config
