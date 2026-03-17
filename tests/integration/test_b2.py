from __future__ import annotations

from src.graph import _route_after_sweep_detection
from src.session_manager import SESSION_DEPENDENCY_COMPLETION_MARKER


def _stub_sweep_detection(_state: dict) -> dict:
    return {
        "sweep_id": "sweep-b2-integration",
        "sweep_parameter": "transport.viscosity",
        "sweep_parameter_value": None,
    }


def test_b2_manifest_incomplete_routes_to_session_dependency_handler() -> None:
    state = {
        **_stub_sweep_detection({}),
        "gate_approvals": [
            {
                "decision": "rejected",
                "details": {"criterion": SESSION_DEPENDENCY_COMPLETION_MARKER},
            }
        ],
    }
    assert _route_after_sweep_detection(state) == "session_dependency_handler"


def test_b2_manifest_complete_routes_to_sweep_execution_handler() -> None:
    state = {
        **_stub_sweep_detection({}),
        "gate_approvals": [
            {
                "decision": "approved",
                "details": {"criterion": SESSION_DEPENDENCY_COMPLETION_MARKER},
            }
        ],
    }
    assert _route_after_sweep_detection(state) == "sweep_execution_handler"
