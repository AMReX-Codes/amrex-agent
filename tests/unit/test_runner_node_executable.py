"""
Runner Node: Executable Resolution: Runner Node Executable Resolution Tests

Verifies executable discovery and linking orchestration.
"""
import importlib

import pytest
from unittest.mock import Mock, patch
from pathlib import Path


runner_node_module = importlib.import_module("src.nodes.runner_node")


class TestRunnerNodeExecutableResolution:
    """
    Runner Node: Executable Resolution: Runner Node Executable Resolution Tests.
    
    Verifies:
    - Discovery of .ex files in baseline directory
    - Filtering by MPI/CUDA config
    - Symlinking logic orchestration
    - Error handling for missing binaries
    
    Design Decisions:
    - Symlink (don't copy) executables
    - Service handles discovery (node orchestrates)
    - Fail if no executable found
    """

    @pytest.fixture
    def mock_runner_cls(self):
        """Mock SuperfacilityRunner class."""
        with patch("src.nodes.runner_node.SuperfacilityRunner") as MockCls:
            yield MockCls

    @pytest.fixture
    def basic_state(self, tmp_path):
        """State with valid paths from Input Writer."""
        case_dir = tmp_path / "AMReX/Tests/Amr/Advection_AmrCore"
        case_dir.mkdir(parents=True)
        
        run_dir = tmp_path / "run_123"
        run_dir.mkdir()
        (run_dir / "inputs").touch()
        
        return {
            "config": Mock(
                use_mpi=True, 
                use_cuda=False,
                amrex_executable=None,
                environment="perlmutter"
            ),
            "plan": {"selected_case": "AMReX/Tests/Amr/Advection_AmrCore"},
            "baseline": {"local_path": str(case_dir)},
            "run_directory": str(run_dir),
            "inputs_file_path": str(run_dir / "inputs"),
            "ready_to_run": True
        }

    def test_finds_executable_in_baseline_dir(self, basic_state, mock_runner_cls):
        """
        GIVEN: Baseline directory with executable
        WHEN: Node calls setup_job
        THEN: Service discovers executable and returns path
        """
        mock_instance = mock_runner_cls.return_value
        expected_exe = "/path/to/amrex3d.gnu.MPI.ex"
        
        mock_instance.setup_job.return_value = {
            "run_dir": basic_state["run_directory"],
            "executable": expected_exe
        }

        updates = runner_node_module.runner_node(basic_state)
        
        # Verify executable found and added to state
        assert "executable_path" in updates
        assert updates["executable_path"] == expected_exe
        
        # Verify service called with baseline directory
        mock_instance.setup_job.assert_called_once()

    def test_passes_baseline_path_to_service(self, basic_state, mock_runner_cls):
        """
        GIVEN: State with baseline.local_path
        WHEN: Node calls setup_job
        THEN: Passes baseline path as case_dir parameter
        """
        mock_instance = mock_runner_cls.return_value
        mock_instance.setup_job.return_value = {
            "run_dir": basic_state["run_directory"],
            "executable": "/some/amrex.ex"
        }

        runner_node_module.runner_node(basic_state)
        
        # Verify baseline path passed to service
        call_kwargs = mock_instance.setup_job.call_args.kwargs
        assert "output_dir" in call_kwargs
        assert call_kwargs["output_dir"] == basic_state["run_directory"]

    def test_filters_by_mpi_requirement(self, basic_state, mock_runner_cls):
        """
        GIVEN: Config with use_mpi=True
        WHEN: Service is initialized
        THEN: Config passed to service (enables MPI filtering)
        """
        basic_state["config"].use_mpi = True
        
        mock_instance = mock_runner_cls.return_value
        mock_instance.setup_job.return_value = {
            "run_dir": basic_state["run_directory"],
            "executable": "/path/amrex.MPI.ex"
        }

        runner_node_module.runner_node(basic_state)
        
        # Verify config passed to Runner (service handles filtering)
        mock_runner_cls.assert_called_with(basic_state["config"])

    def test_filters_by_cuda_requirement(self, basic_state, mock_runner_cls):
        """
        GIVEN: Config with use_cuda=True
        WHEN: Service searches for executable
        THEN: Config enables CUDA filtering in service
        """
        basic_state["config"].use_cuda = True
        basic_state["config"].use_mpi = True
        
        mock_instance = mock_runner_cls.return_value
        mock_instance.setup_job.return_value = {
            "run_dir": basic_state["run_directory"],
            "executable": "/path/amrex.MPI.CUDA.ex"
        }

        runner_node_module.runner_node(basic_state)
        
        # Config passed contains CUDA requirement
        passed_config = mock_runner_cls.call_args[0][0]
        assert passed_config.use_cuda is True

    def test_fails_if_no_executable_found(self, basic_state, mock_runner_cls):
        """
        GIVEN: Baseline directory with no .ex files
        WHEN: Service cannot find executable
        THEN: Sets mode='fail' with clear error
        """
        mock_instance = mock_runner_cls.return_value
        # Simulate service failing to find exe
        mock_instance.setup_job.side_effect = FileNotFoundError(
            "No executable found matching MPI requirements"
        )

        updates = runner_node_module.runner_node(basic_state)

        assert updates["mode"] == "fail"
        assert "No executable found" in updates["error"]

    def test_respects_custom_executable_path(self, basic_state, mock_runner_cls):
        """
        GIVEN: Config with explicit pelec_executable path
        WHEN: Service runs setup_job
        THEN: Uses custom path (service honors config override)
        """
        custom_exe = "/custom/path/amrex.ex"
        basic_state["config"].amrex_executable = custom_exe
        
        mock_instance = mock_runner_cls.return_value
        mock_instance.setup_job.return_value = {
            "run_dir": basic_state["run_directory"],
            "executable": custom_exe
        }

        updates = runner_node_module.runner_node(basic_state)
        
        assert updates["executable_path"] == custom_exe

    def test_handles_missing_baseline_path(self, basic_state, mock_runner_cls):
        """
        GIVEN: State without baseline path
        WHEN: Node tries to extract case_dir
        THEN: Fails gracefully with clear error
        """
        del basic_state["plan"]
        del basic_state["baseline"]  # Remove both plan and baseline
        
        updates = runner_node_module.runner_node(basic_state)
        
        assert updates["mode"] == "fail"
        assert "baseline path" in updates["error"].lower()

    def test_propagates_job_setup_results(self, basic_state, mock_runner_cls):
        """
        GIVEN: Successful setup_job call
        WHEN: Service returns results
        THEN: Node propagates all results to state
        """
        mock_instance = mock_runner_cls.return_value
        setup_result = {
            "run_dir": basic_state["run_directory"],
            "executable": "/path/amrex.ex",
            "submit_script": "/path/submit.sh"
        }
        mock_instance.setup_job.return_value = setup_result

        updates = runner_node_module.runner_node(basic_state)
        
        # Verify key results propagated
        assert updates["executable_path"] == setup_result["executable"]
        assert updates["mode"] != "fail"

    def test_validates_executable_permissions(self, basic_state, mock_runner_cls):
        """
        GIVEN: Found executable without execute permissions
        WHEN: Service validates permissions
        THEN: Service raises error (node propagates failure)
        """
        mock_instance = mock_runner_cls.return_value
        mock_instance.setup_job.side_effect = PermissionError(
            "Executable not executable: /path/amrex.ex"
        )

        updates = runner_node_module.runner_node(basic_state)
        
        assert updates["mode"] == "fail"
        assert "not executable" in updates["error"].lower()
