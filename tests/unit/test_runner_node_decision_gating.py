import importlib
from unittest.mock import Mock

import pytest


runner_node_module = importlib.import_module("src.nodes.runner_node")


class DummyConfig:
    def __init__(self, environment="superfacility"):
        self.environment = environment
        self.preconfirm_gate = False
        self.preconfirm_gate_auto_approve = False
        self.run_mode = "full"
        self.dry_run = False
        self.gate_strategy = "terminal"
        self.gate_points = ["execution"]


def _state_with_files(tmp_path, config):
    run_dir = tmp_path / "run_123"
    run_dir.mkdir()
    inputs_file = run_dir / "inputs"
    inputs_file.write_text("# inputs")
    return {
        "config": config,
        "ready_to_run": True,
        "run_directory": str(run_dir),
        "inputs_file_path": str(inputs_file),
        "baseline": {"local_path": "cases/PMF"},
    }


def _require_gate_manager():
    if not hasattr(runner_node_module, "GateManager"):
        pytest.fail("GateManager not wired into runner_node.")
    return runner_node_module.GateManager


def test_runner_node_execution_gate_invoked(tmp_path, monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.return_value = True
    gate_manager.present_gate.return_value = Mock(
        user_action="approved",
        selected_option="execute",
        user_modification=None,
    )
    monkeypatch.setattr(runner_node_module, "GateManager", Mock(return_value=gate_manager))

    class FakeRunner:
        def __init__(self, _config):
            pass

        def setup_job(self, output_dir, case_dir):
            return {"run_dir": output_dir, "executable": "PeleC.ex"}

        def submit(self, run_directory):
            return {"job_id": "12345", "script_path": "submit.sh"}

    monkeypatch.setattr(runner_node_module, "SuperfacilityRunner", FakeRunner)

    config = DummyConfig()
    updates = runner_node_module.runner_node(_state_with_files(tmp_path, config))

    gate_manager.present_gate.assert_called()
    assert gate_manager.present_gate.call_args.kwargs["gate_point"] == "execution"
    history = updates.get("workflow_history", [])
    assert any(
        entry.get("node") == "preconfirm_gate" and entry.get("details", {}).get("gate_node") == "execution"
        for entry in history
    )


def test_runner_node_auto_strategy_skips_gate(tmp_path, monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.return_value = False
    monkeypatch.setattr(runner_node_module, "GateManager", Mock(return_value=gate_manager))

    class FakeRunner:
        def __init__(self, _config):
            pass

        def setup_job(self, output_dir, case_dir):
            return {"run_dir": output_dir, "executable": "PeleC.ex"}

        def submit(self, run_directory):
            return {"job_id": "12345", "script_path": "submit.sh"}

    monkeypatch.setattr(runner_node_module, "SuperfacilityRunner", FakeRunner)

    config = DummyConfig()
    config.gate_strategy = "auto"
    config.gate_points = []
    runner_node_module.runner_node(_state_with_files(tmp_path, config))

    gate_manager.present_gate.assert_not_called()
