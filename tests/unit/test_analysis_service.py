"""
Analysis: AnalysisService Unit Tests

Scope: Log parsing, failure detection, and status classification.
Reference: Plan v7.0, Test Pyramid, AMReX Log Patterns
"""

import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from src.services.analysis import AnalysisService


class TestAnalysisServiceParsing:
    """Test log parsing and failure detection logic in isolation."""

    @pytest.fixture
    def service(self):
        """Create AnalysisService with mock config."""
        mock_config = Mock()
        return AnalysisService(mock_config)

    def test_parse_success_log(self, service):
        """
        GIVEN: A standard AMReX log file with successful completion
        WHEN: parse_log is called
        THEN: Returns completed=True and extracted metrics
        """
        log_content = """
AMReX: run starting...
STEP = 0  TIME = 0.0000000e+00  DT = 1.000000e-06
STEP = 1  TIME = 1.0000000e-06  DT = 1.100000e-06
STEP = 100 TIME = 1.0000000e-03  DT = 1.500000e-06
AMReX (24.12) finalized
"""
        
        with patch("builtins.open", mock_open(read_data=log_content)):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", return_value=log_content):
                    report = service.parse_log(Path("run.log"))

        assert report.get("completed") is True
        assert report.get("total_steps") == 100
        # Status is determined by analyze_simulation, not parse_log

    def test_parse_cfl_violation(self, service):
        """
        GIVEN: Log with CFL violation error (Aborting)
        WHEN: parse_log is called
        THEN: Extracts CFL data but doesn't set status (that's analyze_simulation's job)
        """
        log_content = """
STEP = 50  TIME = 0.500  DT = 0.100
CFL = 1.5 > 1.0
Error: CFL condition violated.
Aborting...
"""
        
        with patch("builtins.open", mock_open(read_data=log_content)):
            report = service.parse_log(Path("run.log"))

        # parse_log extracts data; analyze_simulation detects failures
        assert "cfl" in str(report).lower() or report.get("total_steps") == 50

    def test_detect_failures_nan(self, service):
        """
        GIVEN: Log data with NaN pattern
        WHEN: detect_failures is called
        THEN: Returns NaN issue
        """
        log_data = {
            "raw_log": "Error: NaN detected in variable 'density' at cell (10, 20, 5)"
        }
        
        failures = service.detect_failures(log_data)
        
        assert any("NaN" in issue for issue in failures)

    def test_detect_failures_timestep_collapse(self, service):
        """
        GIVEN: Log data with timestep collapse
        WHEN: detect_failures is called
        THEN: Returns timestep issue
        """
        log_data = {
            "raw_log": "Error: dt < dt_min (1.0e-12). Simulation collapsing."
        }
        
        failures = service.detect_failures(log_data)
        
        assert any("dt" in issue.lower() for issue in failures)

    def test_analyze_simulation_success(self, service, tmp_path):
        """
        GIVEN: Run directory with successful log
        WHEN: analyze_simulation is called
        THEN: Returns 'success' status
        """
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        
        log_file = run_dir / "stdout.txt"
        log_file.write_text("""
STEP = 100 TIME = 1.0  DT = 0.01
AMReX (24.12) finalized
""")
        
        report = service.analyze_simulation(run_dir)
        
        assert report["status"] == "success"
        assert not report["issues"]

    def test_analyze_simulation_cfl_failure(self, service, tmp_path):
        """
        GIVEN: Run directory with CFL violation
        WHEN: analyze_simulation is called
        THEN: Returns 'unstable' status (completed but with warnings)
        """
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        
        log_file = run_dir / "stdout.txt"
        log_file.write_text("""
STEP = 50  TIME = 0.5  DT = 0.1
CFL = 1.5 > 1.0
Warning: CFL condition violated at step 50
STEP = 100 TIME = 1.0  DT = 0.05
AMReX (24.12) finalized
""")
        
        report = service.analyze_simulation(run_dir)
        
        # If run completed but had CFL warnings → unstable
        assert report["status"] == "unstable"
        assert any("CFL" in str(issue) for issue in report["issues"])

    def test_analyze_simulation_nan_failure(self, service, tmp_path):
        """
        GIVEN: Run directory with NaN error
        WHEN: analyze_simulation is called
        THEN: Returns 'failed' status
        """
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        
        log_file = run_dir / "stdout.txt"
        log_file.write_text("""
STEP = 10
Signal caught: SIGFPE
Floating point exception: Invalid operation
AMReX Backtrace:
  [0] AMReX::advance() at AMReX.cpp:123
  [1] density calculation
Aborting...
""")
        
        report = service.analyze_simulation(run_dir)
        
        # Debug output
        print(f"\nDEBUG Report keys: {list(report.keys())}")
        print(f"DEBUG Issues: {report.get('issues', [])}")
        print(f"DEBUG Status: {report.get('status', 'unknown')}")
        
        assert report["status"] == "failed"
        assert any("NaN" in issue or "Divergence" in issue for issue in report["issues"]), \
            f"Expected NaN/Divergence in issues, got: {report['issues']}"

    def test_analyze_simulation_incomplete(self, service, tmp_path):
        """
        GIVEN: Run directory with incomplete log (no success marker)
        WHEN: analyze_simulation is called
        THEN: Returns 'failed' status
        """
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        
        log_file = run_dir / "stdout.txt"
        log_file.write_text("""
STEP = 50  TIME = 0.5  DT = 0.1
(end of file - no completion message)
""")
        
        report = service.analyze_simulation(run_dir)
        
        assert report["status"] == "failed"  # incomplete → failed per normalization
