"""
Level 4 Integration: Real Subprocess Execution

Tests actual process execution using shim executable:
- Successful execution
- Failure handling (exit code 1)
- Output file creation
- Timeout behavior

Mocked: Nothing (real subprocess.run)
Real: Process execution, file I/O, shim behavior

WARNING: These tests execute real subprocesses. Mark as slow.
"""
import pytest
import subprocess
from pathlib import Path
import time
from textwrap import dedent


@pytest.mark.integration_l4
@pytest.mark.slow
class TestRunnerExecution:
    """Level 4: Real process execution tests."""

    def test_shim_successful_execution(self, shim_executable, tmp_path):
        """
        Test 1: Shim executes successfully

        Given: Shim executable with no flags
        When: Execute as subprocess
        Then: Exit code 0, log file created
        """
        # Prepare inputs
        inputs_file = tmp_path / "inputs"
        inputs_file.write_text("# Test inputs")

        # Execute shim
        result = subprocess.run(
            [str(shim_executable), str(inputs_file)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=5
        )

        # Verify success
        assert result.returncode == 0
        assert "Shim execution complete" in result.stdout

        # Verify outputs created
        log_file = tmp_path / "run.log"
        assert log_file.exists()
        assert "completed successfully" in log_file.read_text()

        # Verify plotfile
        assert (tmp_path / "plt00010").exists()
        assert (tmp_path / "plt00010" / "Header").exists()

    def test_shim_failure_exit_code(self, shim_executable, tmp_path):
        """
        Test 2: Shim handles --fail flag

        Given: Shim with --fail argument
        When: Execute as subprocess
        Then: Exit code 1, error message in log
        """
        inputs_file = tmp_path / "inputs"
        inputs_file.write_text("# Test inputs")

        # Execute with failure flag
        result = subprocess.run(
            [str(shim_executable), str(inputs_file), "--fail"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=5
        )

        # Verify failure
        assert result.returncode == 1

        # Verify log has error
        log_file = tmp_path / "run.log"
        assert log_file.exists()
        assert "CFL violation" in log_file.read_text()

    def test_shim_timeout_behavior(self, shim_executable, tmp_path):
        """
        Test 3: Shim --sleep respects timeout

        Given: Shim with --sleep 10
        When: Execute with timeout=1
        Then: TimeoutExpired raised
        """
        inputs_file = tmp_path / "inputs"
        inputs_file.write_text("# Test inputs")

        # Execute with sleep and short timeout
        with pytest.raises(subprocess.TimeoutExpired):
            subprocess.run(
                [str(shim_executable), str(inputs_file), "--sleep", "10"],
                cwd=tmp_path,
                capture_output=True,
                timeout=1  # Timeout before sleep finishes
            )

    def test_shim_creates_expected_artifacts(self, shim_executable, tmp_path):
        """
        Test 4: Shim creates all expected output files

        Given: Successful shim execution
        When: Process completes
        Then: run.log and plt00010 directory created
        """
        inputs_file = tmp_path / "inputs"
        inputs_file.write_text("# Test inputs")

        subprocess.run(
            [str(shim_executable), str(inputs_file)],
            cwd=tmp_path,
            timeout=5
        )

        # Verify artifacts
        assert (tmp_path / "run.log").exists()
        assert (tmp_path / "plt00010").exists()
        assert (tmp_path / "plt00010" / "Header").exists()

        # Verify log structure matches AnalysisService expectations
        log_content = (tmp_path / "run.log").read_text()
        assert "STEP =" in log_content
        assert "TIME =" in log_content
        assert "DT =" in log_content
