"""B1c clarification node."""

from __future__ import annotations

from typing import Any

from src.models import GraphState
from src.models.clarification_schemas import ClarificationQuestion, ClarificationRecord
from src.services.viz_param_extractor import get_plot_var_param_candidates


REQUIRED_FIELDS = ("n_cell", "max_level", "stop_time", "max_step")
RESOURCE_FIELDS = ("node_count", "time_limit", "cluster")
MAX_CLARIFICATION_TURNS = 3


def clarification_node(state: GraphState) -> dict[str, Any]:
    """
    Session 8 Clarification Node.
    Deterministic checks only; no LLM calls.
    """
    config = state.get("config")
    enabled = bool(getattr(config, "enable_clarification_subgraph", False))
    resolved = _as_dict(state.get("resolved_config"))
    locked_fields = _as_locked_fields(state.get("intent_locked_fields"))
    prompt = str(state.get("prompt") or state.get("user_requirement") or "")
    requested_plot_vars = state.get("requested_plot_vars")
    prior_history = _as_history(state.get("clarification_history"))
    history = list(prior_history)
    turns = int(state.get("clarification_turns") or 0)
    ai_answers = _as_dict(state.get("ai_clarification_answers"))

    context = _base_context(resolved, locked_fields, requested_plot_vars)
    insufficient_prompt = len(context["missing_fields"]) > 0

    if not enabled:
        return _no_block_result(
            history=prior_history,
            context=context,
            insufficient_prompt=insufficient_prompt,
            resolved_config=resolved,
        )
    if turns >= MAX_CLARIFICATION_TURNS:
        return _no_block_result(
            history=prior_history,
            context=context,
            insufficient_prompt=insufficient_prompt,
            resolved_config=resolved,
        )

    level_1_questions = _check_level_1_required_questions(
        resolved=resolved,
        locked_fields=locked_fields,
    )
    if level_1_questions:
        records = [_build_record(question=question, answers=ai_answers, turn=turns + 1) for question in level_1_questions]
        history = history + [record.model_dump() for record in records]
        resolved = _apply_records_to_resolved_config(resolved=resolved, records=records)
        context = _base_context(resolved, locked_fields, requested_plot_vars)
        pending_questions = [record.question for record in records if record.answered_by == "pending"]

        if state.get("interactive_available") is False:
            if not pending_questions:
                return _no_block_result(
                    history=history,
                    context=context,
                    insufficient_prompt=False,
                    unresolved_level=None,
                    resolved_config=resolved,
                )
            return _no_block_result(
                history=history,
                context=context,
                insufficient_prompt=True,
                unresolved_level=1,
                resolved_config=resolved,
            )

        if pending_questions:
            return {
                "clarification_needed": True,
                "clarification_questions": [question.model_dump() for question in pending_questions],
                "clarification_context": context,
                "clarification_history": history,
                "clarification_turns": turns + 1,
                "insufficient_prompt": False,
                "unresolved_level": 1,
                "resolved_config": resolved,
            }

    question = _select_question(
        state=state,
        resolved=resolved,
        locked_fields=locked_fields,
        prompt=prompt,
        requested_plot_vars=requested_plot_vars,
    )
    if question is None:
        return _no_block_result(
            history=history,
            context=context,
            insufficient_prompt=False,
            resolved_config=resolved,
        )

    if state.get("interactive_available") is False:
        return _no_block_result(
            history=history,
            context=context,
            insufficient_prompt=True,
            unresolved_level=question.decision_level,
            resolved_config=resolved,
        )

    record = _build_record(question=question, answers=ai_answers, turn=turns + 1)
    history = history + [record.model_dump()]
    resolved = _apply_records_to_resolved_config(resolved=resolved, records=[record])
    context = _base_context(resolved, locked_fields, requested_plot_vars)
    if record.answered_by == "ai_agent":
        return _no_block_result(
            history=history,
            context=context,
            insufficient_prompt=False,
            resolved_config=resolved,
        )

    return {
        "clarification_needed": True,
        "clarification_questions": [question.model_dump()],
        "clarification_context": context,
        "clarification_history": history,
        "clarification_turns": turns + 1,
        "insufficient_prompt": False,
        "unresolved_level": question.decision_level,
        "resolved_config": resolved,
    }


def _select_question(
    state: GraphState,
    resolved: dict[str, Any],
    locked_fields: set[str],
    prompt: str,
    requested_plot_vars: Any,
) -> ClarificationQuestion | None:
    checks = (
        _check_level_1_required,
        _check_level_2_physics_ambiguity,
        _check_level_3_resource_spec,
        _check_level_4_visualization,
        _check_level_5_optional_refinement,
        _check_level_6_high_cost_confirmation,
    )
    for check in checks:
        question = check(
            state=state,
            resolved=resolved,
            locked_fields=locked_fields,
            prompt=prompt,
            requested_plot_vars=requested_plot_vars,
        )
        if question is not None:
            return question
    return None


def _check_level_1_required(
    *,
    state: GraphState,
    resolved: dict[str, Any],
    locked_fields: set[str],
    prompt: str,
    requested_plot_vars: Any,
) -> ClarificationQuestion | None:
    del state, prompt, requested_plot_vars
    for field in REQUIRED_FIELDS:
        if field in locked_fields:
            continue
        if _is_missing(resolved.get(field)):
            return ClarificationQuestion(
                field_name=field,
                question_text=_required_field_question(field),
                decision_level=1,
                fallback_tier=_fallback_tier_for_field(field),
                context={"reason": "required_field_missing"},
            )
    return None


def _check_level_1_required_questions(
    *,
    resolved: dict[str, Any],
    locked_fields: set[str],
) -> list[ClarificationQuestion]:
    questions: list[ClarificationQuestion] = []
    for field in REQUIRED_FIELDS:
        if field in locked_fields:
            continue
        if _is_missing(resolved.get(field)):
            questions.append(
                ClarificationQuestion(
                    field_name=field,
                    question_text=_required_field_question(field),
                    decision_level=1,
                    fallback_tier=_fallback_tier_for_field(field),
                    context={"reason": "required_field_missing"},
                )
            )
    return questions


def _check_level_2_physics_ambiguity(
    *,
    state: GraphState,
    resolved: dict[str, Any],
    locked_fields: set[str],
    prompt: str,
    requested_plot_vars: Any,
) -> ClarificationQuestion | None:
    del state, resolved, locked_fields, requested_plot_vars
    text = prompt.lower()
    has_flame = "flame" in text
    has_turbulence = "turbulence" in text
    has_priority = any(token in text for token in ("priority", "prioritize", "focus"))
    if has_flame and has_turbulence and not has_priority:
        return ClarificationQuestion(
            field_name=None,
            question_text="Should this run prioritize flame chemistry or turbulence resolution?",
            decision_level=2,
            fallback_tier="free_text",
            context={"reason": "physics_ambiguity"},
        )
    return None


def _check_level_3_resource_spec(
    *,
    state: GraphState,
    resolved: dict[str, Any],
    locked_fields: set[str],
    prompt: str,
    requested_plot_vars: Any,
) -> ClarificationQuestion | None:
    del state, locked_fields, prompt, requested_plot_vars
    if all(_is_missing(resolved.get(field)) for field in RESOURCE_FIELDS):
        return ClarificationQuestion(
            field_name="node_count",
            question_text="What compute resources should be used (nodes, time limit, cluster)?",
            decision_level=3,
            fallback_tier="faiss",
            context={"reason": "resource_spec_missing"},
        )
    return None


def _check_level_4_visualization(
    *,
    state: GraphState,
    resolved: dict[str, Any],
    locked_fields: set[str],
    prompt: str,
    requested_plot_vars: Any,
) -> ClarificationQuestion | None:
    del locked_fields, prompt
    mapping_candidates = state.get("visualization_mapping_candidates")
    mapping_unresolved = state.get("visualization_mapping_unresolved")
    if isinstance(mapping_candidates, dict) and mapping_candidates:
        token = next(iter(mapping_candidates.keys()))
        entries = mapping_candidates.get(token, [])
        names: list[str] = []
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    name = str(entry.get("name", "")).strip()
                    if name:
                        names.append(name)
        if names:
            return ClarificationQuestion(
                field_name="requested_plot_vars",
                question_text=f"Which field should represent '{token}' in visualization output?",
                decision_level=4,
                fallback_tier="amrex_generic",
                context={
                    "reason": "visualization_mapping_ambiguity",
                    "token": token,
                    "candidates": names,
                },
            )
    if isinstance(mapping_unresolved, list) and mapping_unresolved:
        token = str(mapping_unresolved[0]).strip()
        return ClarificationQuestion(
            field_name="requested_plot_vars",
            question_text=f"No solver field matched '{token}'. Which plot variable should be used?",
            decision_level=4,
            fallback_tier="amrex_generic",
            context={"reason": "visualization_mapping_unresolved", "token": token, "candidates": []},
        )
    if requested_plot_vars == [] and not _has_plotfile_var(resolved, state):
        return ClarificationQuestion(
            field_name="plot_vars",
            question_text="Which variables should be written to plotfiles for visualization?",
            decision_level=4,
            fallback_tier="amrex_generic",
            context={"reason": "visualization_preference_missing"},
        )
    return None


def _check_level_5_optional_refinement(
    *,
    state: GraphState,
    resolved: dict[str, Any],
    locked_fields: set[str],
    prompt: str,
    requested_plot_vars: Any,
) -> ClarificationQuestion | None:
    del state, resolved, locked_fields, requested_plot_vars
    if "alchemical" in prompt.lower():
        return ClarificationQuestion(
            field_name="optional_refinement",
            question_text="Do you want to add any optional refinement constraints for this novel objective?",
            decision_level=5,
            fallback_tier="free_text",
            context={"reason": "optional_refinement"},
        )
    return None


def _check_level_6_high_cost_confirmation(
    *,
    state: GraphState,
    resolved: dict[str, Any],
    locked_fields: set[str],
    prompt: str,
    requested_plot_vars: Any,
) -> ClarificationQuestion | None:
    del resolved, locked_fields, prompt, requested_plot_vars
    pending = state.get("high_cost_operation_pending") is True
    config = state.get("config")
    require_confirmation = bool(getattr(config, "require_high_cost_confirmation", True))
    if pending and require_confirmation:
        return ClarificationQuestion(
            field_name="high_cost_operation",
            question_text="This is a high-cost operation. Confirm that execution should proceed.",
            decision_level=6,
            fallback_tier="report",
            context={"reason": "high_cost_confirmation"},
        )
    return None


def _build_record(
    *,
    question: ClarificationQuestion,
    answers: dict[str, Any],
    turn: int,
) -> ClarificationRecord:
    resolved_value = None
    answer = None
    answered_by = "pending"
    field = question.field_name
    if field and field in answers:
        resolved_value = answers[field]
        answer = str(resolved_value)
        answered_by = "ai_agent"
    return ClarificationRecord(
        question=question,
        answer=answer,
        answered_by=answered_by,
        resolved_value=resolved_value,
        turn=turn,
    )


def _apply_records_to_resolved_config(
    *,
    resolved: dict[str, Any],
    records: list[ClarificationRecord],
) -> dict[str, Any]:
    updated = dict(resolved)
    for record in records:
        field = record.question.field_name
        if record.answered_by == "ai_agent" and field and record.resolved_value is not None:
            updated[field] = record.resolved_value
    return updated


def _no_block_result(
    *,
    history: list[dict[str, Any]],
    context: dict[str, Any],
    insufficient_prompt: bool,
    unresolved_level: int | None = None,
    resolved_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "clarification_needed": False,
        "clarification_questions": [],
        "clarification_context": context,
        "clarification_history": history,
        "insufficient_prompt": insufficient_prompt,
        "unresolved_level": unresolved_level,
        "resolved_config": resolved_config or {},
    }


def _base_context(
    resolved: dict[str, Any],
    locked_fields: set[str],
    requested_plot_vars: Any,
) -> dict[str, Any]:
    missing_fields = []
    for field in REQUIRED_FIELDS:
        if field in locked_fields:
            continue
        if _is_missing(resolved.get(field)):
            missing_fields.append(field)
    return {
        "missing_fields": missing_fields,
        "ambiguous_fields": [],
        "requested_plot_vars_empty": requested_plot_vars == [],
        "missing_plotfile_vars": requested_plot_vars == [] and not _has_plotfile_var(resolved, None),
    }


def _required_field_question(field: str) -> str:
    if field == "n_cell":
        return "What base grid resolution (n_cell) should be used?"
    return f"What value should be used for required parameter '{field}'?"


def _fallback_tier_for_field(field: str) -> str:
    if field in {"n_cell", "stop_time", "max_step"}:
        return "report"
    if field == "max_level" or field.startswith("amr."):
        return "amrex_generic"
    if field in RESOURCE_FIELDS:
        return "faiss"
    return "free_text"


def _has_plotfile_var(resolved: dict[str, Any], state: GraphState | None) -> bool:
    solver = ""
    if isinstance(state, dict):
        solver = str(state.get("selected_solver") or "").strip()
    keys = get_plot_var_param_candidates(solver) + ["plot_vars"]
    for key in keys:
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


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_history(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(dict(item))
    return out


def _as_locked_fields(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}
