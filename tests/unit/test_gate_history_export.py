import pytest

from src.utils import gate


def test_build_gate_history_from_workflow_history():
    if not hasattr(gate, "build_gate_history_from_workflow_history"):
        pytest.fail("build_gate_history_from_workflow_history not implemented.")

    workflow_history = [
        {
            "node": "preconfirm_gate",
            "timestamp": "2026-02-11T10:00:00Z",
            "action": "proceed",
            "iteration": 1,
            "details": {
                "gate_node": "baseline",
                "selection": {"value": "FlameSheet"},
                "reason": None,
            },
        },
        {
            "node": "architect",
            "timestamp": "2026-02-11T10:00:05Z",
            "action": "plan_created",
            "iteration": 1,
            "details": {},
        },
    ]

    payload = gate.build_gate_history_from_workflow_history(workflow_history)

    assert payload == [
        {
            "gate_point": "baseline",
            "selected": "FlameSheet",
            "user_action": "approved",
            "timestamp": "2026-02-11T10:00:00Z",
        }
    ]
