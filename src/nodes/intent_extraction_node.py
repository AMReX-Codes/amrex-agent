"""
Intent Extraction Node.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.models import GraphState

logger = logging.getLogger(__name__)


def intent_extraction_node(state: GraphState) -> dict[str, Any]:
    """
    B1b Intent Extraction Node.
    Extracts structured simulation intent from prompt.
    Never blocks pipeline on failure.
    """
    config = state.get("config")
    if not config:
        raise ValueError("Intent Extraction Node requires 'config' in state")

    prompt = state.get("prompt") or state.get("user_requirement") or ""
    cli_values = _coerce_mapping(
        state.get("cli_values")
        or state.get("cli_overrides")
        or state.get("cli_flags")
    )
    config_values = _coerce_mapping(
        state.get("config_values")
        or state.get("config_file_values")
        or state.get("config_overrides")
    )

    enable_extraction = getattr(config, "enable_intent_extraction", False) is True
    llm_values: dict[str, Any] = {}
    applied = False
    error: str | None = None

    if enable_extraction:
        try:
            llm_values = _call_llm_for_intent(prompt=prompt, config=config)
            applied = True
        except Exception as exc:
            logger.exception("Intent extraction failed; continuing with CLI/config values")
            error = str(exc)

    resolved_config, locked_fields = _merge_with_precedence(
        cli_values=cli_values,
        config_values=config_values,
        llm_values=llm_values,
    )

    return {
        "resolved_config": resolved_config,
        "intent_extraction_applied": applied,
        "intent_extraction_error": error,
        "intent_locked_fields": locked_fields,
    }


def _call_llm_for_intent(
    prompt: str,
    config,
) -> dict[str, Any]:
    """
    Call LLM to extract structured intent.
    Returns dict of parameter: value pairs.
    Raises on LLM failure - caller handles.
    """
    from src.config import get_llm_client
    from src.utils.llm_calls import LLMCallSpec, call_llm

    llm_client = get_llm_client(config)
    spec = LLMCallSpec(
        model=config.llm_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract AMReX simulation intent from user text. "
                    "Return only a JSON object mapping parameter names to values."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=getattr(config, "llm_max_tokens", None),
        purpose="intent_extraction",
        template_name="intent_extraction",
        template_source="intent_extraction_node",
    )
    result = call_llm(llm_client, spec, config=config)
    payload = _extract_payload(result)

    try:
        parsed = json.loads(payload)
    except Exception as exc:
        raise ValueError(f"Intent extraction response is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Intent extraction response must be a JSON object")
    return parsed


def _merge_with_precedence(
    cli_values: dict[str, Any],
    config_values: dict[str, Any],
    llm_values: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """
    Merge with Tier 1 > Tier 2 > LLM precedence.
    Returns (resolved_config, locked_fields).
    locked_fields: keys where CLI value was used.
    """
    resolved: dict[str, Any] = {}
    resolved.update(llm_values or {})
    resolved.update(config_values or {})
    resolved.update(cli_values or {})

    locked_fields = sorted((cli_values or {}).keys())
    return resolved, locked_fields


def _extract_payload(result: Any) -> str:
    """Normalize LLM response payload to raw JSON string."""
    if isinstance(result, dict):
        return json.dumps(result)
    if isinstance(result, str):
        return result

    content = (
        getattr(result, "choices", [None])[0]
        and getattr(result.choices[0], "message", None)
        and getattr(result.choices[0].message, "content", None)
    )
    if isinstance(content, str):
        return content
    raise ValueError("Intent extraction LLM response missing text content")


def _coerce_mapping(value: Any) -> dict[str, Any]:
    """Return a shallow dict copy if value is dict-like, else empty dict."""
    return dict(value) if isinstance(value, dict) else {}
