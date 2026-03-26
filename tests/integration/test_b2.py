from __future__ import annotations

from src.graph import create_graph
from src.session_manager import SESSION_DEPENDENCY_COMPLETION_MARKER


def _stub_sweep_detection(_state: dict) -> dict:
    return {
        "sweep_id": "sweep-b2-integration",
        "sweep_parameter": "transport.viscosity",
        "sweep_parameter_value": None,
    }


def test_b2_manifest_incomplete_routes_to_session_dependency_handler(monkeypatch) -> None:
    monkeypatch.setattr("src.graph.sweep_detection_node", _stub_sweep_detection)

    app = create_graph().compile()
    steps = list(
        app.stream(
            {
                "prompt": "run sweep",
                "gate_approvals": [
                    {
                        "decision": "rejected",
                        "details": {"criterion": SESSION_DEPENDENCY_COMPLETION_MARKER},
                    }
                ],
            }
        )
    )

    node_sequence = [next(iter(step.keys())) for step in steps]
    assert node_sequence == ["sweep_detection_node", "session_dependency_handler"]


def test_b2_manifest_complete_routes_to_sweep_execution_handler(monkeypatch) -> None:
    monkeypatch.setattr("src.graph.sweep_detection_node", _stub_sweep_detection)

    app = create_graph().compile()
    steps = list(
        app.stream(
            {
                "prompt": "run sweep",
                "gate_approvals": [
                    {
                        "decision": "approved",
                        "details": {"criterion": SESSION_DEPENDENCY_COMPLETION_MARKER},
                    }
                ],
            }
        )
    )

    node_sequence = [next(iter(step.keys())) for step in steps]
    assert node_sequence == ["sweep_detection_node", "sweep_execution_handler"]
