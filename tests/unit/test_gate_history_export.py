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


def test_build_gate_history_from_decision_gates():
    if not hasattr(gate, "build_gate_history_from_workflow_history"):
        pytest.fail("build_gate_history_from_workflow_history not implemented.")

    workflow_history = [
        {
            "node": "preconfirm_gate",
            "timestamp": "2026-02-11T11:00:00Z",
            "action": "approved",
            "iteration": 2,
            "details": {
                "gate_node": "execution",
                "selection": {"value": "run_dir"},
                "reason": "decision_gate",
            },
        },
        {
            "node": "preconfirm_gate",
            "timestamp": "2026-02-11T11:01:00Z",
            "action": "approved",
            "iteration": 2,
            "details": {
                "gate_node": "modifications",
                "selection": {"value": "case"},
                "reason": "decision_gate",
            },
        },
    ]

    payload = gate.build_gate_history_from_workflow_history(workflow_history)

    assert payload == [
        {
            "gate_point": "execution",
            "selected": "run_dir",
            "user_action": "approved",
            "timestamp": "2026-02-11T11:00:00Z",
        },
        {
            "gate_point": "modifications",
            "selected": "case",
            "user_action": "approved",
            "timestamp": "2026-02-11T11:01:00Z",
        },
    ]
