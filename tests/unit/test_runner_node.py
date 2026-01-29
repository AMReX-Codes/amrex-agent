import importlib
from pathlib import Path

import pytest


runner_node_module = importlib.import_module("src.nodes.runner_node")


class DummyConfig:
    def __init__(self, environment="superfacility"):
        self.environment = environment


def _state_with_files(tmp_path):
    run_dir = tmp_path / "run_123"
    run_dir.mkdir()
    inputs_file = run_dir / "inputs"
    inputs_file.write_text("# inputs")
    return run_dir, inputs_file


def test_requires_config(tmp_path):
    run_dir, inputs_file = _state_with_files(tmp_path)
    state = {
        "ready_to_run": True,
        "run_directory": str(run_dir),
        "inputs_file_path": str(inputs_file),
        "baseline": {"local_path": "cases/PMF"},
    }
    updates = runner_node_module.runner_node(state)
    assert updates["mode"] == "fail"
    assert "config" in updates["error"].lower()


def test_ready_to_run_false_fails(tmp_path):
    run_dir, inputs_file = _state_with_files(tmp_path)
    state = {
        "config": DummyConfig(),
        "ready_to_run": False,
        "run_directory": str(run_dir),
        "inputs_file_path": str(inputs_file),
        "baseline": {"local_path": "cases/PMF"},
    }
    updates = runner_node_module.runner_node(state)
    assert updates["mode"] == "fail"
    assert "ready_to_run" in updates["error"]


def test_missing_run_directory_fails(tmp_path):
    _, inputs_file = _state_with_files(tmp_path)
    state = {
        "config": DummyConfig(),
        "ready_to_run": True,
        "inputs_file_path": str(inputs_file),
        "baseline": {"local_path": "cases/PMF"},
    }
    updates = runner_node_module.runner_node(state)
    assert updates["mode"] == "fail"
    assert "run_directory" in updates["error"].lower()


def test_missing_inputs_file_path_fails(tmp_path):
    run_dir, _ = _state_with_files(tmp_path)
    state = {
        "config": DummyConfig(),
        "ready_to_run": True,
        "run_directory": str(run_dir),
        "baseline": {"local_path": "cases/PMF"},
    }
    updates = runner_node_module.runner_node(state)
    assert updates["mode"] == "fail"
    assert "inputs_file_path" in updates["error"]


def test_missing_baseline_path_fails(tmp_path):
    run_dir, inputs_file = _state_with_files(tmp_path)
    state = {
        "config": DummyConfig(),
        "ready_to_run": True,
        "run_directory": str(run_dir),
        "inputs_file_path": str(inputs_file),
        "plan": {},
        "baseline": {},
    }
    updates = runner_node_module.runner_node(state)
    assert updates["mode"] == "fail"
    assert "baseline path" in updates["error"].lower()


def test_success_calls_runner(tmp_path, monkeypatch):
    run_dir, inputs_file = _state_with_files(tmp_path)
    state = {
        "config": DummyConfig(),
        "ready_to_run": True,
        "run_directory": str(run_dir),
        "inputs_file_path": str(inputs_file),
        "baseline": {"local_path": "cases/PMF"},
    }
    call_state = {}

    class FakeRunner:
        def __init__(self, _config):
            call_state["init"] = True

        def setup_job(self, output_dir, case_dir):
            call_state["setup"] = (output_dir, case_dir)
            return {"run_dir": output_dir, "executable": "PeleC.ex"}

        def submit(self, run_directory):
            call_state["submit"] = run_directory
            return {"job_id": "12345", "script_path": "submit.sh"}

    monkeypatch.setattr(runner_node_module, "SuperfacilityRunner", FakeRunner)

    updates = runner_node_module.runner_node(state)

    assert updates["mode"] == "proceed"
    assert updates["job_id"] == "12345"
    assert call_state["setup"][1] == "cases/PMF"
