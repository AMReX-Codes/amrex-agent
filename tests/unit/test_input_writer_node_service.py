import importlib
from datetime import datetime as real_datetime
import re

import pytest
from unittest.mock import Mock, patch


input_writer_node_module = importlib.import_module("src.nodes.input_writer_node")


class FixedDateTime:
    @classmethod
    def now(cls):
        return real_datetime(2024, 1, 1, 12, 0, 0)

    @classmethod
    def utcnow(cls):
        return real_datetime(2024, 1, 1, 12, 0, 0)


def _state(output_dir="/tmp/runs"):
    return {
        "config": Mock(output_dir=output_dir),
        "workflow_history": [
            {
                "node": "architect",
                "details": {
                    "selected_case": "AMReX/Tests/Amr/Advection_AmrCore",
                    "modifications": [("amr.n_cell", "64 64 64")],
                    "baseline": {"local_path": "/tmp/amrex", "code_name": "AMReX"},
                    "reasoning": "test run",
                },
            }
        ],
    }


class TestInputWriterNodeServiceOrchestration:
    def test_initializes_input_writer_service(self):
        state = _state()
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"):
            MockService.return_value.apply_plan.return_value = {
                "status": "success",
                "run_dir": "/tmp/runs/run_20240101_120000",
                "inputs_path": "/tmp/runs/run_20240101_120000/inputs",
            }

            input_writer_node_module.input_writer_node(state)
            MockService.assert_called_once_with(state["config"])

    def test_generates_timestamped_directory(self):
        state = _state()
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"), \
             patch("src.nodes.input_writer_node.datetime", FixedDateTime):
            MockService.return_value.apply_plan.return_value = {
                "status": "success",
                "run_dir": "/tmp/runs/run_20240101_120000",
                "inputs_path": "/tmp/runs/run_20240101_120000/inputs",
            }

            input_writer_node_module.input_writer_node(state)
            call_kwargs = MockService.return_value.apply_plan.call_args.kwargs
            output_dir = str(call_kwargs.get("output_dir", ""))

            assert output_dir.startswith("/tmp/runs")
            assert re.search(r"run_\d{8}_\d{6}", output_dir) is not None

    def test_calls_apply_plan_with_components(self):
        state = _state()
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"):
            MockService.return_value.apply_plan.return_value = {
                "status": "success",
                "run_dir": "/tmp/runs/run_20240101_120000",
                "inputs_path": "/tmp/runs/run_20240101_120000/inputs",
            }

            input_writer_node_module.input_writer_node(state)

            call_kwargs = MockService.return_value.apply_plan.call_args.kwargs
            assert call_kwargs["selected_case"] == "AMReX/Tests/Amr/Advection_AmrCore"
            assert call_kwargs["modifications"] == [("amr.n_cell", "64 64 64")]
            assert call_kwargs["baseline"]["local_path"] == "/tmp/amrex"
            assert call_kwargs["reasoning"] == "test run"

    def test_returns_run_directory_and_inputs(self):
        state = _state()
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"):
            MockService.return_value.apply_plan.return_value = {
                "status": "success",
                "run_dir": "/path/to/run",
                "inputs_path": "/path/to/run/inputs",
            }

            result = input_writer_node_module.input_writer_node(state)

            assert result["run_directory"] == "/path/to/run"
            assert result["inputs_file"] == "/path/to/run/inputs"

    def test_output_dir_from_config(self):
        state = _state(output_dir="/custom/path/output")
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"):
            MockService.return_value.apply_plan.return_value = {
                "status": "success",
                "run_dir": "/custom/path/output/run_20240101_120000",
                "inputs_path": "/custom/path/output/run_20240101_120000/inputs",
            }

            input_writer_node_module.input_writer_node(state)
            call_kwargs = MockService.return_value.apply_plan.call_args.kwargs
            assert str(call_kwargs["output_dir"]).startswith("/custom/path/output")
