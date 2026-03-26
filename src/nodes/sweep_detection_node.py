"""B2b node for deterministic sweep detection."""

from __future__ import annotations

from typing import Any

from src.services.sweep_detector import create_sweep_spec, detect_sweep_request


def sweep_detection_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    B2b Sweep Detection Node.
    Reads prompt from state, runs detect_sweep_request.
    Writes sweep_id, sweep_parameter to state if found.
    sweep_parameter_value stays None at parent level.
    No LLM calls. Non-blocking.
    """
    prompt = state.get("prompt", "")
    detection = detect_sweep_request(prompt)

    if detection is None:
        return {
            "sweep_id": None,
            "sweep_parameter": None,
            "sweep_parameter_value": None,
        }

    spec = create_sweep_spec(detection)
    return {
        "sweep_id": spec.sweep_id,
        "sweep_parameter": spec.parameter_name,
        "sweep_parameter_value": None,
    }
