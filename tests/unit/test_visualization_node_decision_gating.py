import importlib
from unittest.mock import Mock


visualization_node_module = importlib.import_module("src.nodes.visualization_node")


def test_visualization_node_decision_gate_invoked(monkeypatch):
    gate_manager = Mock()
    gate_manager.should_gate.return_value = True
    gate_manager.present_gate.return_value = Mock(
        user_action="approved",
        selected_option="visualization",
        user_modification=None,
    )
    monkeypatch.setattr(visualization_node_module, "GateManager", Mock(return_value=gate_manager))

    config = Mock()
    config.preconfirm_gate = False
    config.preconfirm_gate_auto_approve = False
    config.gate_strategy = "terminal"
    config.gate_points = ["visualization"]

    state = {
        "config": config,
        "workflow_history": [],
        "analysis_report": {"status": "success"},
    }

    updates = visualization_node_module.visualization_node(state)

    gate_manager.present_gate.assert_called()
    assert gate_manager.present_gate.call_args.kwargs["gate_point"] == "visualization"
    history = updates.get("workflow_history", [])
    assert any(
        entry.get("node") == "preconfirm_gate" and entry.get("details", {}).get("gate_node") == "visualization"
        for entry in history
    )
