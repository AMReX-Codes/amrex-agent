import importlib
from unittest.mock import Mock

import pytest


reviewer_node_module = importlib.import_module("src.nodes.reviewer_node")


def _require_gate_manager():
    if not hasattr(reviewer_node_module, "GateManager"):
        pytest.fail("GateManager not wired into reviewer_node.")
    return reviewer_node_module.GateManager


def _base_state(config):
    return {
        "config": config,
        "workflow_history": [
            {
                "node": "architect",
                "details": {
                    "selected_case": "PeleC/Exec/RegTests/PMF",
                    "modifications": [("amr.n_cell", "64 64 64")],
                    "baseline": {"local_path": "cases/PMF", "code_name": "PeleC"},
                    "reasoning": "baseline test",
                },
            }
        ],
        "review": {},
        "errors_found": [],
        "errors_fixed": [],
        "errors_active": [],
        "retry_count": 1,
        "iteration": 0,
    }


def test_reviewer_node_modifications_gate_invoked(monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.return_value = True
    gate_manager.present_gate.return_value = Mock(
        user_action="approved",
        selected_option="PeleC/Exec/RegTests/PMF",
        user_modification=None,
    )
    monkeypatch.setattr(reviewer_node_module, "GateManager", Mock(return_value=gate_manager))

    config = Mock(
        preconfirm_gate=False,
        preconfirm_gate_auto_approve=False,
        gate_strategy="terminal",
        gate_points=["modifications"],
    )

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan, retry_count=0):
            return type(
                "ValidationResult",
                (),
                {"violations": [], "mode": "proceed", "summary": "ok", "available_schema_params": []},
            )

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    updates = reviewer_node_module.reviewer_node(_base_state(config))

    gate_manager.present_gate.assert_called()
    assert gate_manager.present_gate.call_args.kwargs["gate_point"] == "modifications"
    history = updates.get("workflow_history", [])
    assert any(
        entry.get("node") == "preconfirm_gate" and entry.get("details", {}).get("gate_node") == "modifications"
        for entry in history
    )


def test_reviewer_node_auto_strategy_skips_gate(monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.return_value = False
    monkeypatch.setattr(reviewer_node_module, "GateManager", Mock(return_value=gate_manager))

    config = Mock(
        preconfirm_gate=False,
        preconfirm_gate_auto_approve=False,
        gate_strategy="auto",
        gate_points=[],
    )

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan, retry_count=0):
            return type(
                "ValidationResult",
                (),
                {"violations": [], "mode": "proceed", "summary": "ok", "available_schema_params": []},
            )

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    reviewer_node_module.reviewer_node(_base_state(config))

    gate_manager.present_gate.assert_not_called()
