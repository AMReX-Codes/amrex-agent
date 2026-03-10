import importlib
from unittest.mock import Mock


analysis_node_module = importlib.import_module("src.nodes.analysis_node")


def test_analysis_node_decision_gate_invoked(tmp_path, monkeypatch):
    gate_manager = Mock()
    gate_manager.should_gate.return_value = True
    gate_manager.present_gate.return_value = Mock(
        user_action="approved",
        selected_option="analysis",
        user_modification=None,
    )
    monkeypatch.setattr(analysis_node_module, "GateManager", Mock(return_value=gate_manager))

    class FakeAnalysisService:
        def __init__(self, _config):
            pass

        def analyze_simulation(self, **_kwargs):
            return {"status": "success", "issues": [], "warnings": [], "metrics": {}}

    monkeypatch.setattr(analysis_node_module, "AnalysisService", FakeAnalysisService)

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    config = Mock()
    config.run_mode = "full"
    config.dry_run = False
    config.preconfirm_gate = False
    config.preconfirm_gate_auto_approve = False
    config.gate_strategy = "terminal"
    config.gate_points = ["analysis"]

    state = {
        "config": config,
        "workflow_history": [
            {"node": "input_writer", "details": {"run_directory": str(run_dir)}}
        ],
    }

    updates = analysis_node_module.analysis_node(state)

    gate_manager.present_gate.assert_called()
    assert gate_manager.present_gate.call_args.kwargs["gate_point"] == "analysis"
    history = updates.get("workflow_history", [])
    assert any(
        entry.get("node") == "preconfirm_gate" and entry.get("details", {}).get("gate_node") == "analysis"
        for entry in history
    )
