"""
Level 3 Integration: AnalysisService Log Parsing

Tests service-level log parsing without node orchestration:
- Success log parsing
- Failure detection (CFL, NaN, timestep collapse)
- Missing log handling
- Metrics extraction

Mocked: Nothing (real file I/O, real regex parsing)
Real: AnalysisService, log parsing, failure detection
"""
import pytest
from pathlib import Path
from textwrap import dedent
from src.services.analysis import AnalysisService
from src.config import AMReXAgentConfig


@pytest.mark.integration_l3
class TestAnalysisParsing:
    """Level 3: Service-level log parsing tests."""

    @pytest.fixture
    def service(self):
        """Create AnalysisService instance."""
        config = AMReXAgentConfig()
        return AnalysisService(config)

    def test_parse_successful_log(self, service, tmp_path):
        """
        Test 1: Parse successful simulation log

        Given: Log with STEP lines and completion marker
        When: analyze_simulation is called
        Then: Status is 'success', metrics extracted
        """
        # Create successful log
        run_dir = tmp_path / "success_run"
        run_dir.mkdir()

        log_file = run_dir / "stdout.txt"
        log_file.write_text(dedent("""                AMReX: run starting...
            STEP = 0  TIME = 0.0000000e+00  DT = 1.000000e-06
            STEP = 10 TIME = 1.0000000e-05  DT = 1.000000e-06
            STEP = 20 TIME = 2.0000000e-05  DT = 1.000000e-06
            AMReX finalized
            """))

        # Analyze
        report = service.analyze_simulation(run_dir)

        # Verify success
        assert report["status"] == "success"
        assert report["total_steps"] == 20
        assert report["final_time"] == 2.0e-05
        assert len(report["issues"]) == 0
        assert report["completed"] is True

    def test_detect_cfl_violation(self, service, tmp_path):
        """
        Test 2: Detect CFL > 1.0 violation

        Given: Log with CFL = 1.2 (exceeds limit)
        When: analyze_simulation is called
        Then: Status is 'unstable', CFL issue reported
        """
        run_dir = tmp_path / "cfl_fail"
        run_dir.mkdir()

        (run_dir / "stdout.txt").write_text(dedent("""                STEP = 0  TIME = 0.0  DT = 1e-6
            CFL = 0.5
            STEP = 10 TIME = 1e-5  DT = 1e-6
            CFL = 1.2
            STEP = 11 TIME = 1.1e-5  DT = 5e-7
            AMReX finalized
            """))

        report = service.analyze_simulation(run_dir)

        # Verify CFL detection
        assert report["status"] == "unstable"
        assert len(report["issues"]) > 0
        assert any("CFL" in issue and "exceeded" in issue for issue in report["issues"])

        # Verify CFL history
        cfl_history = report.get("cfl_history", [])
        assert len(cfl_history) == 2
        assert max(cfl_history) == 1.2

    def test_detect_nan_failure(self, service, tmp_path):
        """
        Test 3: Detect NaN in min/max values

        Given: Log with min(Temp) = NaN
        When: analyze_simulation is called
        Then: Status is 'failed', NaN issue reported
        """
        run_dir = tmp_path / "nan_fail"
        run_dir.mkdir()

        (run_dir / "stdout.txt").write_text(dedent("""
            STEP = 0  TIME = 0.0  DT = 1e-6
            min(Temp) = 300.0  max(Temp) = 2000.0
            STEP = 10 TIME = 1e-5  DT = 1e-6
            min(Temp) = nan  max(Temp) = nan
            
            Signal caught: SIGFPE
            Floating point exception: Invalid operation
            AMReX Backtrace:
              [0] AMReX::advance() at AMReX.cpp:456
            Aborting...
            """))

        report = service.analyze_simulation(run_dir)

        # Verify NaN detection
        assert report["status"] == "failed"
        assert any("NaN" in issue for issue in report["issues"])

    @pytest.mark.skip(reason="Timestep collapse detection - Phase 5 feature")
    def test_detect_timestep_collapse(self, service, tmp_path):
        """
        Test 4: Detect timestep collapse (dt → 0)

        Given: Log with dt decreasing to 1e-15
        When: analyze_simulation is called
        Then: Timestep collapse issue reported
        """
        run_dir = tmp_path / "dt_collapse"
        run_dir.mkdir()

        log_content = "AMReX: run starting...\n"
        # Create timesteps with collapsing dt
        for i in range(20):
            dt = 1e-6 * (0.5 ** i)  # Exponentially decreasing
            log_content += f"STEP = {i}  TIME = {i*1e-6:.6e}  DT = {dt:.6e}\n"

        (run_dir / "stdout.txt").write_text(log_content)

        report = service.analyze_simulation(run_dir)

        # Verify timestep collapse detection
        assert any("collapsed" in issue.lower() for issue in report["issues"])

    def test_handle_missing_log_file(self, service, tmp_path):
        """
        Test 5: Handle missing log file gracefully

        Given: Empty run directory
        When: analyze_simulation is called
        Then: Status is 'no_log_file', does not crash
        """
        run_dir = tmp_path / "empty_run"
        run_dir.mkdir()

        # Analyze (no log file)
        report = service.analyze_simulation(run_dir)

        # Verify graceful handling
        assert report["status"] == "failed"  # Canonical: no_log_file → failed
        assert len(report["issues"]) > 0
        assert "No log file found" in report["issues"][0]

    def test_extract_performance_metrics(self, service, tmp_path):
        """
        Test 6: Extract performance metrics

        Given: Log with cells/sec data
        When: analyze_simulation is called
        Then: Performance metrics extracted
        """
        run_dir = tmp_path / "perf_run"
        run_dir.mkdir()

        (run_dir / "stdout.txt").write_text(dedent("""                STEP = 0  TIME = 0.0  DT = 1e-6
            Cells advanced: 1.0e6  cells/s: 5.0e5
            STEP = 10 TIME = 1e-5  DT = 1e-6
            Cells advanced: 1.0e6  cells/s: 5.2e5
            AMReX finalized
            """))

        report = service.analyze_simulation(run_dir)

        # Verify performance data
        assert report["status"] == "success"
        performance = report.get("performance", {})
        assert "avg_cells_per_sec" in performance
        assert performance["avg_cells_per_sec"] > 0

    def test_suggestions_generated_for_failures(self, service, tmp_path):
        """
        Test 7: Suggestions generated when issues found

        Given: Log with CFL violation
        When: analyze_simulation is called
        Then: Suggestions list contains remediation advice
        """
        run_dir = tmp_path / "cfl_suggest"
        run_dir.mkdir()

        (run_dir / "stdout.txt").write_text(dedent("""                STEP = 0  TIME = 0.0  DT = 1e-6
            CFL = 1.5
            """))

        report = service.analyze_simulation(run_dir)

        # Verify suggestions
        assert "suggestions" in report
        assert len(report["suggestions"]) > 0
        assert any("timestep" in s.lower() or "dt" in s.lower() for s in report["suggestions"])
