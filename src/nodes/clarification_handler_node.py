"""Schema-aware clarification handler node."""

from __future__ import annotations

from typing import Any

from src.models.clarification_schemas import ClarificationQuestion, ClarificationRecord

MAX_CLARIFICATION_TURNS = 3
_PLOT_VAR_FIELDS = {"requested_plot_vars", "plot_vars", "amr.plot_vars"}


def clarification_handler_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Schema-aware clarification handler.
    Finds first pending ClarificationRecord,
    resolves it from user or ai_agent response,
    updates resolved_config and history.
    """
    history = _as_history(state.get("clarification_history"))
    turns = _as_turns(state.get("clarification_turns"))

    if turns >= MAX_CLARIFICATION_TURNS:
        return {
            "clarification_history": history,
            "clarification_needed": False,
            "clarification_turns": turns,
            "skip_further_clarification": True,
        }

    pending_index, pending_record = _find_pending_record(history)
    if pending_record is None:
        return {
            "clarification_history": history,
            "clarification_needed": False,
            "clarification_turns": turns,
            "skip_further_clarification": False,
        }

    response, answered_by = _pick_response(
        user_response=state.get("user_response"),
        ai_agent_response=state.get("ai_agent_response"),
    )
    if response is None:
        return {
            "clarification_history": history,
            "clarification_needed": True,
            "clarification_turns": turns + 1,
            "skip_further_clarification": False,
        }

    updated_record = _resolve_record(pending_record, response, answered_by)
    history[pending_index] = updated_record

    updates = {
        "clarification_history": history,
        "clarification_needed": _any_pending(history),
        "clarification_turns": turns,
        "skip_further_clarification": False,
    }
    updates.update(
        _apply_resolved_value(
            state=state,
            question=updated_record.get("question", {}),
            resolved_value=response,
        )
    )
    return updates


def _find_pending_record(
    history: list[dict[str, Any]],
) -> tuple[int, dict[str, Any] | None]:
    """
    Return (index, record) of first record
    where answered_by == 'pending'.
    Return (-1, None) if none found.
    """
    for index, raw_record in enumerate(history):
        record = _record_to_dict(raw_record)
        if record.get("answered_by") == "pending":
            return index, record
    return -1, None


def _resolve_record(
    record: dict[str, Any],
    response: str,
    answered_by: str,  # 'human' | 'ai_agent'
) -> dict[str, Any]:
    """
    Mark record as answered.
    Set resolved_value from response.
    Return updated record dict.
    """
    updated = _record_to_dict(record)
    updated["answer"] = response
    updated["answered_by"] = answered_by
    updated["resolved_value"] = response
    updated["turn"] = _as_turns(updated.get("turn")) + 1
    return updated


def _apply_resolved_value(
    state: dict[str, Any],
    question: dict[str, Any],
    resolved_value: str,
) -> dict[str, Any]:
    """
    Write resolved_value to correct state field.
    decision_level=4 or field_name indicates
    plot vars -> write to requested_plot_vars.
    All others -> write to resolved_config.
    Returns updated state.
    """
    question_data = _question_to_dict(question)
    field_name = question_data.get("field_name")
    decision_level = _as_turns(question_data.get("decision_level"))

    if decision_level == 4 or field_name in _PLOT_VAR_FIELDS:
        requested_plot_vars = list(state.get("requested_plot_vars") or [])
        merged = _merge_plot_vars(requested_plot_vars, resolved_value)
        intent = dict(state.get("visualization_intent") or {})
        if not isinstance(intent, dict):
            intent = {}
        existing_requested = intent.get("requested_fields", intent.get("requested_plot_vars", []))
        if not isinstance(existing_requested, list):
            existing_requested = []
        intent_merged = _merge_plot_vars(existing_requested, resolved_value)
        intent["requested_fields"] = intent_merged
        return {"requested_plot_vars": merged, "visualization_intent": intent}

    if not field_name:
        return {}

    resolved_config = dict(state.get("resolved_config") or {})
    resolved_config[field_name] = resolved_value
    return {"resolved_config": resolved_config}


def _any_pending(history: list[dict[str, Any]]) -> bool:
    """
    Return True if any record has
    answered_by == 'pending'.
    """
    for record in history:
        if _record_to_dict(record).get("answered_by") == "pending":
            return True
    return False


def _route_after_clarification(state: dict[str, Any]) -> str:
    if state.get("clarification_needed", False):
        return "clarification_node"
    return "input_writer_node"


def _pick_response(user_response: Any, ai_agent_response: Any) -> tuple[str | None, str]:
    # Prefer explicit human feedback when both sources are present.
    if _has_text(user_response):
        return str(user_response).strip(), "human"
    if _has_text(ai_agent_response):
        return str(ai_agent_response).strip(), "ai_agent"
    return None, "human"


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _merge_plot_vars(current: list[Any], resolved_value: str) -> list[str]:
    merged: list[str] = [str(value) for value in current if str(value).strip() != ""]
    for token in resolved_value.replace(",", " ").split():
        cleaned = token.strip()
        if cleaned and cleaned not in merged:
            merged.append(cleaned)
    return merged


def _as_history(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_record_to_dict(item) for item in value]


def _record_to_dict(value: Any) -> dict[str, Any]:
    try:
        return ClarificationRecord.model_validate(value).model_dump()
    except Exception:
        if isinstance(value, dict):
            fallback = dict(value)
            fallback["question"] = _question_to_dict(fallback.get("question", {}))
            return fallback
        return {
            "question": {},
            "answer": None,
            "answered_by": "pending",
            "resolved_value": None,
            "turn": 0,
        }


def _question_to_dict(value: Any) -> dict[str, Any]:
    try:
        return ClarificationQuestion.model_validate(value).model_dump()
    except Exception:
        return dict(value) if isinstance(value, dict) else {}


def _as_turns(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
