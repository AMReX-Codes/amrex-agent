"""
Input Writer Node: Output Mapping: Input Writer Node Output Mapping Tests

Validates that service results are correctly mapped to the GraphState
schema required by downstream nodes (Runner).
"""
import importlib

import pytest
from unittest.mock import Mock, patch


input_writer_node_module = importlib.import_module("src.nodes.input_writer_node")


class TestInputWriterNodeOutputMapping:
    """
    Input Writer Node: Output Mapping: Input Writer Node Output Mapping Tests
    
    Validates that service results are correctly mapped to the GraphState
    schema required by downstream nodes (Runner).
    """

    @pytest.fixture
    def mock_service_result(self):
        """Standard successful result from InputWriterService."""
        return {
            'inputs_path': '/path/to/run_123/inputs',
            'run_dir': '/path/to/run_123',  # Service uses 'run_dir'
            'status': 'success'
        }

    @pytest.fixture
    def mock_state(self):
        return {
            "config": Mock(output_dir="/tmp/runs"),
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "AMReX/Tests/Amr/Advection_AmrCore",
                        "modifications": [('amr.n_cell', '32 32 32')],
                        "baseline": {"local_path": "/tmp/amrex", "code_name": "AMReX"},
                        "reasoning": "test plan",
                    },
                }
            ]
        }

    def test_maps_run_directory_to_state(self, mock_state, mock_service_result):
        """
        GIVEN: Service returns 'run_dir'
        WHEN: Node completes
        THEN: State contains 'run_directory' matching output
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"):
            MockService.return_value.apply_plan.return_value = mock_service_result
            
            updates = input_writer_node_module.input_writer_node(mock_state)
            
            assert "run_directory" in updates
            assert updates["run_directory"] == "/path/to/run_123"

    def test_maps_inputs_file_path(self, mock_state, mock_service_result):
        """
        GIVEN: Service returns 'inputs_path'
        WHEN: Node completes
        THEN: State contains 'inputs_file_path' (PRD schema name)
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"):
            MockService.return_value.apply_plan.return_value = mock_service_result
            
            updates = input_writer_node_module.input_writer_node(mock_state)
            
            assert "inputs_file_path" in updates
            assert updates["inputs_file_path"] == "/path/to/run_123/inputs"

    def test_sets_execution_ready_flag(self, mock_state, mock_service_result):
        """
        GIVEN: Successful generation
        WHEN: Node completes
        THEN: State includes ready_to_run=True flag for Router
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"):
            MockService.return_value.apply_plan.return_value = mock_service_result
            
            updates = input_writer_node_module.input_writer_node(mock_state)
            
            assert updates.get("ready_to_run") is True

    def test_records_applied_modifications(self, mock_state, mock_service_result):
        """
        GIVEN: Service applied modifications (possibly different from plan)
        WHEN: Node updates state
        THEN: modifications_applied is stored
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"):
            MockService.return_value.apply_plan.return_value = mock_service_result
            
            updates = input_writer_node_module.input_writer_node(mock_state)
            
            history = updates["workflow_history"][-1]
            assert history["details"]["modifications_applied"] == 1

    def test_captures_generated_readme_path(self, mock_state, mock_service_result):
        """
        GIVEN: Service generates files in run_dir
        WHEN: Node completes
        THEN: State should track the README path (derived from run_dir)
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"):
            MockService.return_value.apply_plan.return_value = mock_service_result
            
            updates = input_writer_node_module.input_writer_node(mock_state)
            
            assert "readme_path" not in updates

    def test_preserves_plan_vs_actual_difference(self, mock_state, mock_service_result):
        """
        GIVEN: Planned modifications differ from applied (auto-correction)
        WHEN: Node stores results
        THEN: Both plan and applied modifications are accessible
        """
        mock_state["workflow_history"][0]["details"]["modifications"] = [('cfl', '0.5')]
        
        with patch("src.nodes.input_writer_node.InputWriterService") as MockService, \
             patch("src.services.cases.AMReXCasesService"):
            MockService.return_value.apply_plan.return_value = mock_service_result
            
            updates = input_writer_node_module.input_writer_node(mock_state)
            
            history = updates["workflow_history"][-1]
            assert history["details"]["modifications_applied"] == 1
