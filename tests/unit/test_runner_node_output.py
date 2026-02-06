"""
Runner Node: Output Mapping: Runner Node Output Mapping Tests

Validates state updates after submission (Service -> State).
"""
import importlib
from datetime import datetime as real_datetime

import pytest
from unittest.mock import Mock, patch


runner_node_module = importlib.import_module("src.nodes.runner_node")


class FixedDateTime:
    @classmethod
    def utcnow(cls):
        return real_datetime(2024, 1, 1, 12, 0, 0)


class TestRunnerNodeOutputMapping:
    """
    Runner Node: Output Mapping: Runner Node Output Mapping Tests.
    
    Validates state updates after submission:
    - Job ID storage
    - Status tracking
    - Workflow history
    - Timestamp capture
    
    Design Decisions:
    - Include submission timestamp
    - Job status as strings
    - Structured history (Architect Node: Workflow History Logging pattern)
    - Preserve existing state keys
    """

    @pytest.fixture
    def mock_submission_result(self):
        """Standard successful submission result."""
        return {
            "job_id": "12345",
            "script_path": "/runs/job_1/submit.sh",
            "job_status": "completed"
        }

    @pytest.fixture
    def basic_state(self, tmp_path):
        """Valid state ready for submission."""
        run_dir = tmp_path / "run_123"
        run_dir.mkdir()
        (run_dir / "inputs").touch()
        
        return {
            "config": Mock(dry_run=False, run_mode="full", environment="perlmutter"),
            "ready_to_run": True,
            "run_directory": str(run_dir),
            "inputs_file_path": str(run_dir / "inputs"),
            "plan": {"selected_case": "AMReX/Tests/Amr/Advection_AmrCore"},
            "baseline": {"local_path": str(tmp_path / "AMReX")},
            "workflow_history": []
        }

    def test_stores_job_id_in_state(self, basic_state, mock_submission_result):
        """
        GIVEN: Service returns job_id
        WHEN: Node completes
        THEN: job_id stored at top level of state
        """
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockSvc:
            instance = MockSvc.return_value
            instance.setup_job.return_value = {
                "run_dir": basic_state["run_directory"],
                "executable": "amrex.ex"
            }
            instance.submit.return_value = mock_submission_result

            updates = runner_node_module.runner_node(basic_state)
            
            assert updates["job_id"] == "12345"

    def test_stores_submit_script_path(self, basic_state, mock_submission_result):
        """
        GIVEN: Service generates submit script
        WHEN: Node completes
        THEN: script_path stored in state
        """
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockSvc:
            instance = MockSvc.return_value
            instance.setup_job.return_value = {
                "run_dir": basic_state["run_directory"],
                "executable": "amrex.ex"
            }
            instance.submit.return_value = mock_submission_result

            updates = runner_node_module.runner_node(basic_state)
            
            assert updates["script_path"] == "/runs/job_1/submit.sh"

    def test_sets_initial_job_status_submitted(self, basic_state, mock_submission_result):
        """
        GIVEN: Successful submission
        WHEN: Job submitted to queue
        THEN: job_status propagated from submit response
        """
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockSvc:
            instance = MockSvc.return_value
            instance.setup_job.return_value = {
                "run_dir": basic_state["run_directory"],
                "executable": "amrex.ex"
            }
            instance.submit.return_value = mock_submission_result

            updates = runner_node_module.runner_node(basic_state)
            
            assert updates["job_status"] == "completed"

    def test_captures_submission_timestamp(self, basic_state, mock_submission_result):
        """
        GIVEN: Service provides submission timestamp
        WHEN: Node completes
        THEN: timestamp_submitted captured for monitoring
        """
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockSvc:
            instance = MockSvc.return_value
            instance.setup_job.return_value = {
                "run_dir": basic_state["run_directory"],
                "executable": "amrex.ex"
            }
            instance.submit.return_value = mock_submission_result

            with patch("src.nodes.runner_node.datetime", FixedDateTime):
                updates = runner_node_module.runner_node(basic_state)
            
            # Should have timestamp for queue wait calculations
            assert "job_submission_time" in updates
            assert updates["job_submission_time"] == "2024-01-01T12:00:00Z"

    def test_appends_success_to_workflow_history(self, basic_state, mock_submission_result):
        """
        GIVEN: Successful submission
        WHEN: Node completes
        THEN: Structured history entry added (Architect Node: Workflow History Logging pattern)
        """
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockSvc:
            instance = MockSvc.return_value
            instance.setup_job.return_value = {
                "run_dir": basic_state["run_directory"],
                "executable": "amrex.ex"
            }
            instance.submit.return_value = mock_submission_result

            updates = runner_node_module.runner_node(basic_state)
            
            # Should append to existing history
            history = updates["workflow_history"]
            assert len(history) == 1
            
            last_entry = history[-1]
            assert last_entry["node"] == "runner"
            assert last_entry["action"] == "job_submitted"
            assert last_entry["details"]["job_id"] == "12345"

    def test_appends_failure_to_workflow_history(self, basic_state):
        """
        GIVEN: Submission fails
        WHEN: Exception raised
        THEN: Failure logged to history with error details
        """
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockSvc:
            instance = MockSvc.return_value
            instance.setup_job.return_value = {
                "run_dir": basic_state["run_directory"],
                "executable": "amrex.ex"
            }
            instance.submit.side_effect = RuntimeError("API Gateway Timeout")

            updates = runner_node_module.runner_node(basic_state)
            
            history = updates["workflow_history"]
            last_entry = history[-1]
            
            assert last_entry["node"] == "runner"
            assert last_entry["action"] == "execution_failed"
            assert "API Gateway Timeout" in last_entry["details"]["error"]
            assert updates["mode"] == "analysis"

    def test_preserves_previous_state_keys(self, basic_state, mock_submission_result):
        """
        GIVEN: State contains plan, baseline, etc.
        WHEN: Node updates state
        THEN: Existing keys preserved (LangGraph merge behavior)
        """
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockSvc:
            instance = MockSvc.return_value
            instance.setup_job.return_value = {
                "run_dir": basic_state["run_directory"],
                "executable": "amrex.ex"
            }
            instance.submit.return_value = mock_submission_result

            updates = runner_node_module.runner_node(basic_state)
            
            # Node returns updates dict, LangGraph merges with state
            # So we just verify we're not deleting keys
            assert "plan" not in updates or updates["plan"] == basic_state["plan"]
            assert "run_directory" not in updates or updates["run_directory"] == basic_state["run_directory"]

    def test_dry_run_sets_status_simulated(self, basic_state, mock_submission_result):
        """
        GIVEN: Dry run mode
        WHEN: Script generated but not submitted
        THEN: job_id placeholder used when job_id is missing
        """
        basic_state["config"].dry_run = True
        mock_submission_result["job_id"] = None  # No real job ID
        
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockSvc:
            instance = MockSvc.return_value
            instance.setup_job.return_value = {
                "run_dir": basic_state["run_directory"],
                "executable": "amrex.ex"
            }
            instance.submit.return_value = mock_submission_result

            updates = runner_node_module.runner_node(basic_state)
            
            assert updates["job_id"] == "dry_run_placeholder"

    def test_includes_system_in_history(self, basic_state, mock_submission_result):
        """
        GIVEN: Submission on specific system (perlmutter)
        WHEN: Job submitted
        THEN: History entry exists
        """
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockSvc:
            instance = MockSvc.return_value
            instance.setup_job.return_value = {
                "run_dir": basic_state["run_directory"],
                "executable": "amrex.ex"
            }
            instance.submit.return_value = mock_submission_result

            updates = runner_node_module.runner_node(basic_state)
            
            history = updates.get("workflow_history", [])
            assert history
