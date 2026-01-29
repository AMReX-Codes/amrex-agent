"""
Level 4 Integration: Runner Job Setup

Tests job setup without actual execution:
- Executable discovery
- File copying to run directory
- SLURM script generation
- Dry run mode

Mocked: Nothing (uses dry_run mode)
Real: SuperfacilityRunner.setup_job(), file operations
"""
import pytest
from pathlib import Path
from src.nodes.runner_node import runner_node
from src.services.run_superfacility import SuperfacilityRunner
from src.config import AMReXAgentConfig
from textwrap import dedent


@pytest.mark.integration_l4
class TestRunnerSetup:
    """Level 4: Job setup tests (no execution)."""

    def test_runner_finds_executable_in_baseline(self, mock_baseline_dir, tmp_path):
        """
        Test 1: Runner discovers .ex file in baseline directory

        Given: Baseline directory with PeleC.ex
        When: SuperfacilityRunner.setup_job() is called
        Then: Executable is found and copied to run_dir
        """
        config = AMReXAgentConfig()
        runner = SuperfacilityRunner(config)

        # Setup job
        result = runner.setup_job(
            case_dir=mock_baseline_dir,
            output_dir=tmp_path,
            base_name="test_setup"
        )

        # Verify executable found
        assert "executable" in result
        assert Path(result["executable"]).name == "PeleC.ex"

        # Verify run directory created
        assert "run_dir" in result
        run_dir = Path(result["run_dir"])
        assert run_dir.exists()
        assert run_dir.parent == tmp_path

    def test_runner_copies_inputs_to_run_dir(self, mock_baseline_dir, tmp_path):
        """
        Test 2: Inputs file copied to run directory

        Given: Baseline with inputs file
        When: setup_job() executes
        Then: inputs file exists in run_dir
        """
        config = AMReXAgentConfig()
        runner = SuperfacilityRunner(config)

        result = runner.setup_job(
            case_dir=mock_baseline_dir,
            output_dir=tmp_path
        )

        # Verify inputs copied
        run_dir = Path(result["run_dir"])
        inputs_path = run_dir / "inputs"

        assert inputs_path.exists()
        assert "amr.n_cell" in inputs_path.read_text()

    def test_runner_generates_slurm_script(self, mock_baseline_dir, tmp_path):
        """
        Test 3: SLURM submit script generated

        Given: Valid run directory
        When: submit(dry_run=True) is called
        Then: submit.sh created with correct parameters
        """
        config = AMReXAgentConfig()
        runner = SuperfacilityRunner(config)

        # Setup job first
        setup_result = runner.setup_job(
            case_dir=mock_baseline_dir,
            output_dir=tmp_path
        )

        # Submit in dry run mode
        submit_result = runner.submit(
            run_dir=setup_result["run_dir"],
            nodes=2,
            walltime="00:30:00",
            dry_run=True
        )

        # Verify script generated
        assert "script_path" in submit_result
        script_path = Path(submit_result["script_path"])

        assert script_path.exists()
        assert script_path.name == "submit.sh"

        # Verify script content
        script_content = script_path.read_text()
        assert "#SBATCH --nodes=2" in script_content
        assert "#SBATCH --time=00:30:00" in script_content
        assert "PeleC.ex" in script_content
