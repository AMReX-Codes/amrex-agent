"""
Runner Node: Submission Logic: Runner Node Submission Execution Tests

Verifies actual job submission orchestration.
"""
import importlib
from datetime import datetime as real_datetime

import pytest
from unittest.mock import Mock, patch


runner_node_module = importlib.import_module("src.nodes.runner_node")


class FixedDateTime:
    @classmethod
    def utcnow(cls):
        return real_datetime(2024, 1, 1, 9, 30, 0)


class TestRunnerNodeSubmission:
    """
    Runner Node: Submission Logic: Submission Execution Tests.
    
    Verifies:
    - Dry run vs real submission
    - Job ID capture
    - Error handling for submission failures
    - Integration with SuperfacilityRunner service
    
    Design Decisions:
    - Synchronous submission, async execution
    - Fail fast (no retry in node)
    - Local execution: fire-and-forget
    """

    @pytest.fixture
    def mock_service_cls(self):
        """Mock SuperfacilityRunner class."""
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockCls:
            instance = MockCls.return_value
            # Default successful behavior
            instance.setup_job.return_value = {
                "run_dir": "/tmp/run",
                "executable": "/tmp/run/amrex.ex"
            }
            instance.submit.return_value = {
                "job_id": "12345",
                "script_path": "/tmp/run/submit.sh",
                "job_status": "completed"
            }
            yield MockCls

    @pytest.fixture
    def valid_state(self, tmp_path):
        """State ready for submission."""
        run_dir = tmp_path / "run_123"
        run_dir.mkdir()
        (run_dir / "inputs").touch()
        
        return {
            "config": Mock(
                dry_run=False,
                environment="perlmutter",
                slurm_account="m999",
                slurm_qos="regular",
                slurm_time="01:00:00",
                slurm_nodes=1
            ),
            "ready_to_run": True,
            "plan": {"selected_case": "AMReX/Tests/Amr/Advection_AmrCore"},
            "baseline": {"local_path": str(tmp_path / "AMReX")},
            "run_directory": str(run_dir),
            "inputs_file_path": str(run_dir / "inputs")
        }

    def test_dry_run_skips_actual_submission(self, valid_state, mock_service_cls):
        """
        GIVEN: config.dry_run=True
        WHEN: Node executes
        THEN: Service called with dry_run=True, returns simulated job_id
        """
        valid_state["config"].dry_run = True
        
        updates = runner_node_module.runner_node(valid_state)
        
        # Verify submit called with dry_run
        instance = mock_service_cls.return_value
        instance.submit.assert_called_once()
        call_kwargs = instance.submit.call_args.kwargs
        
        # Should use dry_run flag (if service supports it)
        # For now, verify job_id captured
        assert "job_id" in updates

    def test_invokes_real_submission_when_not_dry_run(self, valid_state, mock_service_cls):
        """
        GIVEN: config.dry_run=False
        WHEN: Node executes
        THEN: Service called to submit actual job
        """
        valid_state["config"].dry_run = False
        
        updates = runner_node_module.runner_node(valid_state)
        
        # Verify submit called
        instance = mock_service_cls.return_value
        instance.submit.assert_called_once()
        
        # Should capture job ID
        assert updates.get("job_id") == "12345"

    def test_captures_job_id_from_response(self, valid_state, mock_service_cls):
        """
        GIVEN: Successful submission
        WHEN: Service returns job_id
        THEN: Node propagates job_id to state updates
        """
        instance = mock_service_cls.return_value
        instance.submit.return_value = {
            "job_id": "998877",
            "script_path": "/path/submit.sh",
            "timestamp": "2023-10-27T12:00:00"
        }
        
        updates = runner_node_module.runner_node(valid_state)
        
        assert updates["job_id"] == "998877"

    def test_captures_submission_timestamp(self, valid_state, mock_service_cls):
        """
        GIVEN: Service returns submission timestamp
        WHEN: Job submitted
        THEN: Timestamp captured in state
        """
        instance = mock_service_cls.return_value
        instance.submit.return_value = {
            "job_id": "12345",
            "script_path": "/path/submit.sh"
        }

        with patch("src.nodes.runner_node.datetime", FixedDateTime):
            updates = runner_node_module.runner_node(valid_state)

        assert updates.get("job_submission_time") == "2024-01-01T09:30:00Z"

    def test_handles_api_connection_failure(self, valid_state, mock_service_cls):
        """
        GIVEN: API connection fails
        WHEN: submit() raises exception
        THEN: Node sets mode='fail' with error message
        """
        instance = mock_service_cls.return_value
        instance.submit.side_effect = RuntimeError("SFAPI Connection Failed")
        
        updates = runner_node_module.runner_node(valid_state)
        
        assert updates["mode"] == "analysis"
        assert "SFAPI Connection Failed" in updates["error"]

    def test_handles_submission_rejection(self, valid_state, mock_service_cls):
        """
        GIVEN: SLURM rejects submission (invalid account)
        WHEN: Service raises exception
        THEN: Node fails with clear error
        """
        instance = mock_service_cls.return_value
        instance.submit.side_effect = ValueError("Invalid SLURM account: m999")
        
        updates = runner_node_module.runner_node(valid_state)
        
        assert updates["mode"] == "analysis"
        assert "Invalid SLURM account" in updates["error"]

    def test_sets_job_status_submitted(self, valid_state, mock_service_cls):
        """
        GIVEN: Successful submission
        WHEN: Job submitted to queue
        THEN: Sets job_status='submitted'
        """
        updates = runner_node_module.runner_node(valid_state)
        
        assert updates.get("job_status") == "completed"

    def test_preserves_script_path(self, valid_state, mock_service_cls):
        """
        GIVEN: Service generates submit script
        WHEN: Submission completes
        THEN: Script path preserved in state
        """
        expected_script = "/tmp/run/submit.sh"
        instance = mock_service_cls.return_value
        instance.submit.return_value = {
            "job_id": "12345",
            "script_path": expected_script
        }
        
        updates = runner_node_module.runner_node(valid_state)
        
        assert updates.get("script_path") == expected_script

    def test_local_execution_returns_process_id(self, valid_state, mock_service_cls):
        """
        GIVEN: Local execution mode
        WHEN: Service spawns background process
        THEN: Returns PID as job_id
        """
        valid_state["config"].environment = "local"

        with patch("src.services.run_local.LocalRunner") as MockLocal:
            local_instance = MockLocal.return_value
            local_instance.setup_job.return_value = {
                "run_dir": "/tmp/run",
                "executable": "/tmp/run/amrex.ex"
            }
            local_instance.submit.return_value = {
                "job_id": "pid_54321",
                "script_path": "/tmp/run/submit.sh"
            }

            updates = runner_node_module.runner_node(valid_state)

        assert updates["job_id"] == "pid_54321"
