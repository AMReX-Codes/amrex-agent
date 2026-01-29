"""
Analysis: Analysis Node Integration Tests

Validates the orchestration of AnalysisService within the LangGraph workflow.
Ensures state updates, error handling, and history logging work correctly.

Reference: Analysis, GraphState schema
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from src.nodes.analysis_node import analysis_node
from src.config import AMReXAgentConfig


class TestAnalysisNodeIntegration:
    """
    Tests for the analysis_node wrapper function.
    Mocks the underlying AnalysisService to focus on state logic.
    """

    @pytest.fixture
    def mock_config(self):
        return Mock(spec=AMReXAgentConfig)

    @pytest.fixture
    def basic_state(self, mock_config, tmp_path):
        """Standard valid input state for the node."""
        run_dir = tmp_path / "run_test_01"
        run_dir.mkdir()
        return {
            "config": mock_config,
            "run_directory": str(run_dir),
            "plan": {"selected_case": "PeleC/Tests"},
            "workflow_history": [],
            "history": []
        }

    def test_analysis_node_updates_state(self, basic_state):
        """
        GIVEN: A valid run directory
        WHEN: analysis_node executes successfully
        THEN: State is updated with analysis_report and status
        """
        # Mock the service to return a success report
        mock_report = {
            "status": "success",
            "metrics": {"final_time": 1.0},
            "issues": []
        }

        with patch("src.nodes.analysis_node.AnalysisService") as MockService:
            # Setup service instance mock
            instance = MockService.return_value
            instance.analyze_simulation.return_value = mock_report

            # Execute
            state = analysis_node(basic_state)

            # Assert state updates
            assert "analysis_report" in state
            assert state["analysis_report"]["status"] == "success"

            # Verify service called with correct path
            instance.analyze_simulation.assert_called_once()

    def test_analysis_preserves_upstream_state(self, basic_state):
        """
        GIVEN: State with upstream data (plan, run_directory)
        WHEN: analysis_node executes
        THEN: Updates are merged, preserving original keys
        """
        with patch("src.nodes.analysis_node.AnalysisService") as MockService:
            MockService.return_value.analyze_simulation.return_value = {"status": "success"}
            
            state = analysis_node(basic_state)

            # Node should preserve upstream keys
            assert state["plan"] == basic_state["plan"]
            assert state["run_directory"] == basic_state["run_directory"]

    def test_analysis_handles_missing_directory(self, basic_state):
        """
        GIVEN: run_directory in state does not exist on disk
        WHEN: analysis_node executes
        THEN: Returns gracefully with failed status
        """
        # Arrange: Delete the directory
        Path(basic_state["run_directory"]).rmdir()

        # Execute
        state = analysis_node(basic_state)
        
        # Assert graceful handling
        report = state.get("analysis_report", {})
        # Node should detect missing dir and skip or fail
        assert report.get("status") in ["skipped", "failed", "no_log_file"]

    def test_analysis_appends_workflow_history(self, basic_state):
        """
        GIVEN: Standard execution
        WHEN: analysis_node completes
        THEN: A structured entry is appended to workflow_history
        """
        with patch("src.nodes.analysis_node.AnalysisService") as MockService:
            MockService.return_value.analyze_simulation.return_value = {"status": "success"}

            state = analysis_node(basic_state)

            history = state.get("workflow_history", [])
            assert len(history) > 0
            
            # Check last entry
            entry = history[-1]
            assert entry["node"] == "analysis"
            assert "timestamp" in entry
            assert entry.get("status") == "success" or entry.get("action")

    def test_analysis_error_handling(self, basic_state):
        """
        GIVEN: AnalysisService raises an unexpected exception
        WHEN: analysis_node executes
        THEN: Exception is caught, status=failed
        """
        with patch("src.nodes.analysis_node.AnalysisService") as MockService:
            # Simulate crash
            MockService.return_value.analyze_simulation.side_effect = RuntimeError("Parser crashed")

            # Should not raise
            state = analysis_node(basic_state)

            # Assert graceful failure
            report = state.get("analysis_report", {})
            assert report.get("status") == "failed"

    def test_analysis_with_cfl_violation(self, basic_state, tmp_path):
        """
        GIVEN: AnalysisService returns unstable status (CFL violation)
        WHEN: analysis_node processes it
        THEN: Status is preserved for router
        """
        mock_report = {
            "status": "unstable",
            "issues": ["CFL violation detected"],
            "metrics": {}
        }

        with patch("src.nodes.analysis_node.AnalysisService") as MockService:
            MockService.return_value.analyze_simulation.return_value = mock_report

            state = analysis_node(basic_state)

            assert state["analysis_report"]["status"] == "unstable"
            assert len(state["analysis_report"]["issues"]) > 0
