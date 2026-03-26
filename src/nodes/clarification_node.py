"""B1c clarification node."""

from __future__ import annotations

from typing import Any

from src.models import GraphState


REQUIRED_FIELDS = [
    "n_cell",
    "max_level",
    "stop_time",
    "max_step",
]

PLOTFILE_VAR_KEYS = (
    "amr.plot_vars",
    "peleLM.derive_plot_vars",
    "plot_vars",
)


def clarification_node(state: GraphState) -> dict[str, Any]:
    """
    B1c Clarification Node.
    Inspects resolved_config for gaps.
    Writes clarification_needed and questions.
    No LLM calls. Deterministic.
    """
    resolved_config = state.get("resolved_config")
    resolved = dict(resolved_config) if isinstance(resolved_config, dict) else {}
    locked_fields = {
        str(field)
        for field in (state.get("intent_locked_fields") or [])
        if isinstance(field, str)
    }
    requested_plot_vars = state.get("requested_plot_vars")

    missing_fields: list[str] = []
    ambiguous_fields: list[str] = []
    questions: list[str] = []

    for field in REQUIRED_FIELDS:
        if field in locked_fields:
            continue
        value = resolved.get(field)
        if _is_missing(value):
            missing_fields.append(field)
            questions.append(_required_field_question(field))
        elif _is_ambiguous(value):
            ambiguous_fields.append(field)
            questions.append(_ambiguous_field_question(field, value))

    needs_viz_question = requested_plot_vars == [] and not _has_plotfile_var(resolved)
    if needs_viz_question:
        questions.append(
            "Which variables should be written to plotfiles for visualization "
            "(for example: temperature, density, velocity)?"
        )

    clarification_needed = len(questions) > 0
    context = {
        "missing_fields": missing_fields,
        "ambiguous_fields": ambiguous_fields,
        "requested_plot_vars_empty": requested_plot_vars == [],
        "missing_plotfile_vars": needs_viz_question,
    }

    return {
        "clarification_needed": clarification_needed,
        "clarification_questions": questions,
        "clarification_context": context,
    }


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _is_ambiguous(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower() in {"?", "unknown", "tbd", "ambiguous"}


def _has_plotfile_var(resolved: dict[str, Any]) -> bool:
    for key in PLOTFILE_VAR_KEYS:
        if _has_value(resolved.get(key)):
            return True
    return False


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _required_field_question(field: str) -> str:
    if field == "n_cell":
        return "What base grid resolution (n_cell) should be used?"
    return f"What value should be used for required parameter '{field}'?"


def _ambiguous_field_question(field: str, value: Any) -> str:
    return f"The value for '{field}' looks ambiguous ('{value}'). What exact value should be used?"
