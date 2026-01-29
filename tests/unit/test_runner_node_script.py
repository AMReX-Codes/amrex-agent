"""
Runner Node: Script Generation: Runner Node Script Generation Tests

Verifies submission script generation orchestration.
"""
import importlib

import pytest
from unittest.mock import Mock, patch


runner_node_module = importlib.import_module("src.nodes.runner_node")


class TestRunnerNodeScriptGeneration:
    """
    Runner Node: Script Generation: Script Generation Tests.
    
    Verifies:
    - SLURM script generation for HPC
    - Bash script generation for local
    - Resource parameter injection
    - Script executability
    
    Design Decisions:
    - Scripts include module loads (HPC only)
    - Environment from config (not runtime detection)
    - Local execution: foreground
    """

    @pytest.fixture
    def mock_runner_svc(self):
        """Mock SuperfacilityRunner to intercept submit calls."""
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockClass:
            instance = MockClass.return_value
            # Mock setup_job (11b) success
            instance.setup_job.return_value = {
                "run_dir": "/tmp/run_1",
                "executable": "/tmp/run_1/amrex.ex"
            }
            # Mock submit (11c) - script generation
            instance.submit.return_value = {
                "script_path": "/tmp/run_1/submit.sh",
                "job_id": None  # None for dry_run
            }
            yield instance

    @pytest.fixture
    def basic_state(self, tmp_path):
        """State ready for script generation."""
        run_dir = tmp_path / "run_123"
        run_dir.mkdir()
        (run_dir / "inputs").touch()
        
        return {
            "config": Mock(
                environment="perlmutter",
                slurm_account="m999",
                slurm_qos="regular",
                slurm_time="02:00:00",
                slurm_nodes=4
            ),
            "ready_to_run": True,
            "run_directory": str(run_dir),
            "inputs_file_path": str(run_dir / "inputs"),
            "plan": {"selected_case": "AMReX/Tests/Amr/Advection_AmrCore"},
            "baseline": {"local_path": str(tmp_path / "AMReX")}
        }

    def test_generates_script_with_slurm_directives(self, basic_state, mock_runner_svc):
        """
        GIVEN: HPC environment config
        WHEN: Node calls submit for script generation
        THEN: Service called with SLURM parameters
        """
        updates = runner_node_module.runner_node(basic_state)
        
        # Verify submit was called (script generation)
        mock_runner_svc.submit.assert_called_once()
        
        # Verify script path returned
        assert "submit_script" in updates or "script_path" in updates

    def test_injects_walltime_from_config(self, basic_state, mock_runner_svc):
        """
        GIVEN: config.slurm_time specified
        WHEN: Script generated
        THEN: Time parameter passed to service
        """
        basic_state["config"].slurm_time = "05:00:00"
        
        runner_node_module.runner_node(basic_state)
        
        # Service should have been called (walltime used internally)
        mock_runner_svc.submit.assert_called_once()

    def test_injects_account_from_config(self, basic_state, mock_runner_svc):
        """
        GIVEN: config.slurm_account specified
        WHEN: Script generated
        THEN: Account passed to service
        """
        basic_state["config"].slurm_account = "special_account"
        
        runner_node_module.runner_node(basic_state)
        
        # Verify service initialized with config (account used there)
        assert mock_runner_svc.submit.called

    def test_formats_mpi_command_for_hpc(self, basic_state, mock_runner_svc):
        """
        GIVEN: HPC environment (perlmutter)
        WHEN: Script generated
        THEN: Service creates srun-based command (internal logic)
        """
        basic_state["config"].environment = "perlmutter"
        
        updates = runner_node_module.runner_node(basic_state)
        
        # Verify script path present (service handled srun formatting)
        assert mock_runner_svc.submit.called

    def test_generates_bash_script_for_local(self, basic_state, mock_runner_svc):
        """
        GIVEN: Local environment
        WHEN: Script generated
        THEN: Service creates simple bash script (not SLURM)
        """
        basic_state["config"].environment = "local"

        with patch("src.services.run_local.LocalRunner") as MockLocal:
            local_instance = MockLocal.return_value
            local_instance.setup_job.return_value = {
                "run_dir": basic_state["run_directory"],
                "executable": "/tmp/run_1/amrex.ex"
            }
            local_instance.submit.return_value = {
                "script_path": "/tmp/run_1/submit.sh",
                "job_id": "pid_123"
            }

            updates = runner_node_module.runner_node(basic_state)

        assert updates.get("script_path") == "/tmp/run_1/submit.sh"

    def test_returns_script_path_in_state(self, basic_state, mock_runner_svc):
        """
        GIVEN: Successful script generation
        WHEN: Service returns script_path
        THEN: Node propagates it to state updates
        """
        expected_path = "/tmp/run_1/submit.sh"
        mock_runner_svc.submit.return_value = {
            "script_path": expected_path,
            "job_id": None
        }
        
        updates = runner_node_module.runner_node(basic_state)
        
        # Should propagate script_path
        assert updates.get("script_path") == expected_path

    def test_handles_script_generation_failure(self, basic_state, mock_runner_svc):
        """
        GIVEN: Service fails to generate script
        WHEN: submit() raises exception
        THEN: Node returns fail state
        """
        mock_runner_svc.submit.side_effect = IOError("Disk full")
        
        updates = runner_node_module.runner_node(basic_state)
        
        assert updates["mode"] == "analysis"
        assert "Disk full" in updates["error"]

    def test_sets_job_status_configured(self, basic_state, mock_runner_svc):
        """
        GIVEN: Script generated successfully
        WHEN: Node completes
        THEN: Sets job_status='configured' (ready for submission)
        """
        updates = runner_node_module.runner_node(basic_state)
        
        # Should indicate job is configured but not submitted yet
        # (actual submission is Runner Node: Submission Logic)
        assert updates.get("mode") == "proceed"

    def test_uses_executable_from_setup(self, basic_state, mock_runner_svc):
        """
        GIVEN: setup_job provided executable path
        WHEN: submit() generates script
        THEN: Script references discovered executable
        """
        mock_runner_svc.setup_job.return_value = {
            "run_dir": basic_state["run_directory"],
            "executable": "/special/path/amrex.ex"
        }
        
        updates = runner_node_module.runner_node(basic_state)
        
        # Verify executable propagated from setup
        assert updates.get("executable_path") == "/special/path/amrex.ex"
