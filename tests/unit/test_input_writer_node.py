from datetime import datetime as real_datetime
import importlib

import pytest

import src.services.cases as cases_module

input_writer_node_module = importlib.import_module("src.nodes.input_writer_node")


class DummyConfig:
    def __init__(self, output_dir):
        self.output_dir = output_dir


class FixedDateTime:
    @classmethod
    def now(cls):
        return real_datetime(2025, 1, 1, 12, 0, 0)

    @classmethod
    def utcnow(cls):
        return real_datetime(2025, 1, 1, 12, 0, 0)


def _base_state(tmp_path, details_overrides=None):
    details = {
        "selected_case": "PeleC/Exec/RegTests/PMF",
        "modifications": [("amr.n_cell", "64 64 64")],
        "baseline": {"local_path": "cases/PMF", "code_name": "PeleC"},
        "reasoning": "baseline test",
    }
    if details_overrides:
        details.update(details_overrides)
    return {
        "config": DummyConfig(output_dir=str(tmp_path)),
        "workflow_history": [
            {"node": "architect", "details": details}
        ],
    }


def test_requires_config():
    with pytest.raises(ValueError, match="requires 'config'"):
        input_writer_node_module.input_writer_node({"workflow_history": []})


def test_missing_architect_plan_returns_fail(tmp_path):
    state = {"config": DummyConfig(output_dir=str(tmp_path)), "workflow_history": []}
    updates = input_writer_node_module.input_writer_node(state)
    assert updates["mode"] == "fail"
    assert "Missing architect plan" in updates["error"]


def test_success_path_maps_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(input_writer_node_module, "datetime", FixedDateTime)

    call_state = {}
    result = {
        "run_dir": f"{tmp_path}/run_20250101_120000",
        "inputs_path": f"{tmp_path}/run_20250101_120000/inputs",
        "status": "success",
    }

    class DummyCasesService:
        def __init__(self, _config):
            pass

    class FakeService:
        def __init__(self, _config):
            self.cases_svc = None

        def apply_plan(self, **kwargs):
            call_state["kwargs"] = kwargs
            return result

    monkeypatch.setattr(cases_module, "AMReXCasesService", DummyCasesService)
    monkeypatch.setattr(input_writer_node_module, "InputWriterService", FakeService)

    updates = input_writer_node_module.input_writer_node(_base_state(tmp_path))

    assert updates["mode"] == "proceed"
    assert updates["run_directory"] == result["run_dir"]
    assert updates["inputs_file_path"] == result["inputs_path"]
    assert updates["workflow_history"][-1]["action"] == "inputs_generated"
    assert "run_20250101_120000" in call_state["kwargs"]["output_dir"]


def test_parameter_resolution_routes_to_review(tmp_path, monkeypatch):
    monkeypatch.setattr(input_writer_node_module, "datetime", FixedDateTime)

    result = {
        "run_dir": f"{tmp_path}/run_20250101_120000",
        "inputs_path": f"{tmp_path}/run_20250101_120000/inputs",
        "status": "success",
        "requires_parameter_resolution": True,
        "unresolved_parameters": ["amr.max_level"],
        "resolution_guidance": "Provide amr.max_level",
        "available_schema_params": ["amr.max_level", "amr.n_cell"],
        "suggested_params": {"amr.max_level": "1"},
    }

    class DummyCasesService:
        def __init__(self, _config):
            pass

    class FakeService:
        def __init__(self, _config):
            self.cases_svc = None

        def apply_plan(self, **_kwargs):
            return result

    monkeypatch.setattr(cases_module, "AMReXCasesService", DummyCasesService)
    monkeypatch.setattr(input_writer_node_module, "InputWriterService", FakeService)

    updates = input_writer_node_module.input_writer_node(_base_state(tmp_path))

    assert updates["mode"] == "review"
    assert updates["requires_parameter_resolution"] is True
    assert updates["workflow_history"][-1]["action"] == "parameter_resolution_failed"


def test_service_error_status_returns_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(input_writer_node_module, "datetime", FixedDateTime)

    result = {"status": "error", "errors": ["Invalid parameter: cfl"]}

    class DummyCasesService:
        def __init__(self, _config):
            pass

    class FakeService:
        def __init__(self, _config):
            self.cases_svc = None

        def apply_plan(self, **_kwargs):
            return result

    monkeypatch.setattr(cases_module, "AMReXCasesService", DummyCasesService)
    monkeypatch.setattr(input_writer_node_module, "InputWriterService", FakeService)

    updates = input_writer_node_module.input_writer_node(_base_state(tmp_path))

    assert updates["mode"] == "retry"
    assert updates["errors_active"] == ["Invalid parameter: cfl"]
