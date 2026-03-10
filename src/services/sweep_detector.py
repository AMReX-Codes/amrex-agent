"""Deterministic sweep detection and SweepSpec creation utilities."""

from __future__ import annotations

import re
from uuid import uuid4

from src.models.sweep_schemas import SweepSpec, SweepType

SWEEP_TRIGGER_PHRASES: tuple[str, ...] = (
    "vary",
    "sweep",
    "parameter study",
    "parameter scan",
    "sensitivity study",
    "range of",
    "multiple values",
    "compare runs",
    "convergence study",
    "resolution study",
    "scaling study",
)

RESOLUTION_KEYWORDS: tuple[str, ...] = (
    "resolution",
    "grid",
    "refinement",
    "n_cell",
)

EXECUTION_KEYWORDS: tuple[str, ...] = (
    "node",
    "processor",
    "core",
    "resource",
    "scaling",
    "performance",
)

PARAMETER_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_\.]*)\b")
NUMERIC_PATTERN = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
SKIP_PARAMETER_TOKENS = {
    "a",
    "an",
    "and",
    "compare",
    "convergence",
    "for",
    "from",
    "in",
    "multiple",
    "of",
    "over",
    "parameter",
    "range",
    "resolution",
    "run",
    "runs",
    "scan",
    "scaling",
    "sensitivity",
    "study",
    "sweep",
    "the",
    "to",
    "values",
    "vary",
    "with",
}


def _normalize(prompt: str) -> str:
    return (prompt or "").strip().lower()


def _detect_trigger(prompt_lower: str) -> str | None:
    for phrase in SWEEP_TRIGGER_PHRASES:
        if phrase in prompt_lower:
            return phrase
    return None


def _detect_type(prompt_lower: str) -> SweepType:
    if any(keyword in prompt_lower for keyword in RESOLUTION_KEYWORDS):
        return SweepType.resolution
    if any(keyword in prompt_lower for keyword in EXECUTION_KEYWORDS):
        return SweepType.execution
    return SweepType.physics


def _to_number(token: str) -> int | float:
    if "." in token or "e" in token.lower():
        return float(token)
    return int(token)


def _detect_values(prompt_lower: str) -> list[int | float]:
    values: list[int | float] = []
    for token in NUMERIC_PATTERN.findall(prompt_lower):
        parsed = _to_number(token)
        if parsed not in values:
            values.append(parsed)
    return values


def _detect_parameter(prompt_lower: str, sweep_type: SweepType) -> str | None:
    vary_match = re.search(r"\bvary\s+([a-zA-Z_][a-zA-Z0-9_\.]*)", prompt_lower)
    if vary_match:
        return vary_match.group(1)

    scan_match = re.search(
        r"\b(?:parameter\s+scan|parameter\s+study|scan|study)\s+(?:over|of|for)?\s*([a-zA-Z_][a-zA-Z0-9_\.]*)",
        prompt_lower,
    )
    if scan_match:
        candidate = scan_match.group(1)
        if candidate not in SKIP_PARAMETER_TOKENS:
            return candidate

    for token in PARAMETER_PATTERN.findall(prompt_lower):
        if token in SKIP_PARAMETER_TOKENS:
            continue
        if NUMERIC_PATTERN.fullmatch(token):
            continue
        if sweep_type == SweepType.resolution and token in {"n_cell", "max_level"}:
            return token
        if sweep_type == SweepType.execution and token in {"nodes", "node", "cores", "core", "processors"}:
            return token
        if sweep_type == SweepType.physics and token not in RESOLUTION_KEYWORDS and token not in EXECUTION_KEYWORDS:
            return token

    if sweep_type == SweepType.resolution:
        return "n_cell"
    if sweep_type == SweepType.execution:
        return "nodes"
    return None


def detect_sweep_request(prompt: str) -> dict | None:
    """
    Keyword-based sweep detection.
    Returns detection dict or None if no sweep.
    No LLM calls. Deterministic.

    Returns:
        {
          'sweep_type': SweepType,
          'parameter_name': str | None,
          'parameter_values': list,
          'raw_match': str,
        }
        or None

    B2 handoff: when Intent Extraction is fully
    wired, sweep intent comes from resolved_config
    rather than keyword detection. This function
    remains as fallback when
    enable_intent_extraction=False.
    """
    prompt_lower = _normalize(prompt)
    trigger = _detect_trigger(prompt_lower)
    if not trigger:
        return None

    parameter_values = _detect_values(prompt_lower)
    if len(parameter_values) < 2:
        return None

    sweep_type = _detect_type(prompt_lower)
    parameter_name = _detect_parameter(prompt_lower, sweep_type)

    return {
        "sweep_type": sweep_type,
        "parameter_name": parameter_name,
        "parameter_values": parameter_values,
        "raw_match": trigger,
    }


def create_sweep_spec(detection: dict) -> SweepSpec:
    """
    Build validated SweepSpec from detection result.
    Generates unique sweep_id via uuid4.
    """
    parameter_name = detection.get("parameter_name") or "unknown_parameter"
    return SweepSpec(
        sweep_type=detection["sweep_type"],
        parameter_name=parameter_name,
        parameter_values=detection["parameter_values"],
        sweep_id=str(uuid4()),
        metadata={"raw_match": detection.get("raw_match", "")},
    )
