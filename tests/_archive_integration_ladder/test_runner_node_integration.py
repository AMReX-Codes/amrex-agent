"""
Level 4 Integration: Runner Node State Integration

Tests runner_node orchestration and state updates:
- State validation (ready_to_run, file existence)
- Service integration
- Output mapping
- Error handling

Mocked: Actual job submission (uses dry_run)
Real: runner_node, state validation, service calls
"""
import pytest
from pathlib import Path
from unittest.mock import patch
from src.nodes.runner_node import runner_node
from src.config import AMReXAgentConfig
from textwrap import dedent


@pytest.mark.integration_l4
class TestRunnerNodeIntegration:
    """Level 4: Node-level integration tests."""

    def test_runner_node_updates_state(self, mock_baseline_dir, tmp_path):
        """
        Test 1: runner_node adds job info to state

        Given: Valid L2 state with run_directory
        When: runner_node executes (dry_run)
        Then: State updated with executable, job_id, script_path
        """
        # Prepare run directory
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        (run_dir / "inputs").write_text("amr.n_cell = 64 64 64")

        config = AMReXAgentConfig()
        state = {
            "config": config,
            "ready_to_run": True,
            "run_directory": str(run_dir),
            "inputs_file_path": str(run_dir / "inputs"),
            "baseline": {"local_path": str(mock_baseline_dir)},
            "workflow_history": []
        }

        # Mock submit to use dry_run
        with patch("src.services.run_superfacility.SuperfacilityRunner.submit") as mock_submit:
            mock_submit.return_value = {
                "job_id": "test_job_123",
                "method": "dry_run",
                "script_path": str(run_dir / "submit.sh"),
                "timestamp": "2024-01-01T00:00:00"
            }

            # Execute
            updates = runner_node(state)

        # Verify state updates
        assert updates["mode"] == "proceed"
        assert "executable" in updates
        assert "job_id" in updates
        assert updates["job_id"] == "test_job_123"
        assert "script_path" in updates
        assert updates["job_status"] == "submitted"

    def test_runner_node_validates_ready_flag(self, tmp_path):
        """
        Test 2: runner_node checks ready_to_run flag

        Given: State with ready_to_run=False
        When: runner_node executes
        Then: Returns fail mode, does not execute
        """
        config = AMReXAgentConfig()
        state = {
            "config": config,
            "ready_to_run": False,  # InputWriter failed
            "run_directory": str(tmp_path),
            "inputs_file_path": str(tmp_path / "inputs")
        }

        # Execute
        updates = runner_node(state)

        # Verify early exit
        assert updates["mode"] == "fail"
        assert "Input Writer did not complete" in updates["error"]

    def test_runner_node_validates_file_existence(self, tmp_path):
        """
        Test 3: runner_node checks inputs file exists

        Given: State with non-existent inputs_file_path
        When: runner_node executes
        Then: Returns fail mode with descriptive error
        """
        run_dir = tmp_path / "empty_run"
        run_dir.mkdir()

        config = AMReXAgentConfig()
        state = {
            "config": config,
            "ready_to_run": True,
            "run_directory": str(run_dir),
            "inputs_file_path": str(run_dir / "nonexistent.inputs")
        }

        # Execute
        updates = runner_node(state)

        # Verify validation error
        assert updates["mode"] == "fail"
        assert "Inputs file not found" in updates["error"]

    def test_runner_node_handles_missing_baseline(self, tmp_path):
        """
        Test 4: runner_node handles missing baseline path

        Given: State without baseline.local_path
        When: runner_node executes
        Then: Returns fail mode (executable discovery requires baseline)
        """
        run_dir = tmp_path / "run_no_baseline"
        run_dir.mkdir()
        (run_dir / "inputs").write_text("test")

        config = AMReXAgentConfig()
        state = {
            "config": config,
            "ready_to_run": True,
            "run_directory": str(run_dir),
            "inputs_file_path": str(run_dir / "inputs"),
            "baseline": {}  # Missing local_path
        }

        # Execute
        updates = runner_node(state)

        # Verify error
        assert updates["mode"] == "fail"
        assert "baseline path" in updates["error"].lower()

    def test_runner_preserves_workflow_history(self, mock_baseline_dir, tmp_path):
        """
        Test 5: runner_node appends to workflow_history

        Given: State with existing history from L1-L2
        When: runner_node executes
        Then: New entry appended with job info
        """
        run_dir = tmp_path / "run_history"
        run_dir.mkdir()
        (run_dir / "inputs").write_text("test")

        config = AMReXAgentConfig()
        initial_history = [
            {"node": "architect", "action": "plan_created"},
            {"node": "input_writer", "action": "files_written"}
        ]

        state = {
            "config": config,
            "ready_to_run": True,
            "run_directory": str(run_dir),
            "inputs_file_path": str(run_dir / "inputs"),
            "baseline": {"local_path": str(mock_baseline_dir)},
            "workflow_history": initial_history.copy()
        }

        # Mock submit
        with patch("src.services.run_superfacility.SuperfacilityRunner.submit") as mock_submit:
            mock_submit.return_value = {
                "job_id": "test_123",
                "script_path": str(run_dir / "submit.sh")
            }

            updates = runner_node(state)

        # Verify history updated
        new_history = updates["workflow_history"]
        assert len(new_history) == len(initial_history) + 1

        latest_entry = new_history[-1]
        assert latest_entry["node"] == "runner"
        assert latest_entry["action"] == "job_submitted"
        assert "job_id" in latest_entry
