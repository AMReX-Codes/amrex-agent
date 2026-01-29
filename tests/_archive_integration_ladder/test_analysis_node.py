"""
Level 3 Integration: Analysis Node State Integration

Tests node-level orchestration and GraphState updates:
- State field updates (analysis_report)
- History tracking
- Error propagation
- Upstream state preservation

Mocked: Nothing (uses real mock simulation outputs from fixtures)
Real: analysis_node, AnalysisService, state updates
"""
import pytest
from unittest.mock import Mock
from pathlib import Path
from pathlib import Path
from src.nodes.analysis_node import analysis_node
from src.config import AMReXAgentConfig


@pytest.mark.integration_l3

@pytest.fixture
def basic_state(tmp_path):
    """State with run_directory and mock success log."""
    from src.config import AMReXAgentConfig
    mock_config = Mock(spec=AMReXAgentConfig)
    
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()
    
    # Create mock success log
    log_file = run_dir / "stdout.txt"
    log_file.write_text("""
STEP = 0  TIME = 0.0  DT = 1.0e-6
STEP = 100  TIME = 1.0e-3  DT = 1.0e-6
AMReX (24.12) finalized
""")
    
    return {
        "config": mock_config,
        "run_directory": str(run_dir),
        "workflow_history": [],
        "history": [],
        "error_logs": []
    }

class TestAnalysisNode:
    """Level 3: Node integration tests."""

    def test_analysis_node_updates_state(self, basic_state):
        """
        Test 1: analysis_node adds analysis_report to state

        Given: L3 state with valid run_dir
        When: analysis_node is executed
        Then: 'analysis_report' field added to state
        """
        state = basic_state  # L3 state from fixture

        # Verify L3 state has run_dir
        assert "run_directory" in state
        assert Path(state["run_directory"]).exists()

        # Execute analysis node
        result_state = analysis_node(state)

        # Verify analysis_report added
        assert "analysis_report" in result_state
        report = result_state["analysis_report"]

        assert "status" in report
        assert "issues" in report
        assert report["status"] == "success"  # Mock fixture has success log

    def test_analysis_preserves_upstream_state(self, basic_state):
        """
        Test 2: Upstream state fields preserved

        Given: State with plan, run_dir, inputs_path
        When: analysis_node executes
        Then: Original fields remain unchanged
        """
        state = basic_state

        # Capture original values
        original_run_dir = state["run_directory"]
        original_plan = state.get("plan")

        # Execute
        result_state = analysis_node(state)

        # Verify preservation
        assert result_state["run_directory"] == original_run_dir
        if original_plan:
            assert result_state["plan"] == original_plan

    def test_analysis_appends_to_history(self, basic_state):
        """
        Test 3: analysis_node appends to workflow history

        Given: State with existing history from L1-L2
        When: analysis_node executes
        Then: New history entry appended
        """
        state = basic_state

        # Add fake upstream history
        initial_history = state.get("history", [])
        initial_history_len = len(initial_history)

        # Execute
        result_state = analysis_node(state)

        # Verify history updated
        new_history = result_state["history"]
        assert len(new_history) > initial_history_len

        # Verify latest entry is from analysis
        latest_entry = new_history[-1]
        assert "Analysis" in latest_entry

    def test_analysis_handles_missing_run_dir(self):
        """
        Test 4: Gracefully handle missing run_dir

        Given: State without run_dir
        When: analysis_node executes
        Then: Status is 'skipped', does not crash
        """
        state = {
            "config": AMReXAgentConfig(),
            "history": []
        }

        # Execute (should not crash)
        result_state = analysis_node(state)

        # Verify graceful handling
        assert "analysis_report" in result_state
        assert result_state["analysis_report"]["status"] == "skipped"
        assert "Skipped" in result_state["history"][-1]

    def test_analysis_propagates_failures_to_error_logs(self, tmp_path):
        """
        Test 5: Failed analysis updates error_logs

        Given: Failed simulation with CFL violation
        When: analysis_node executes
        Then: error_logs populated with issues
        """
        from tests.integration.fixtures.mock_simulation_outputs import create_failed_simulation
        from tests.integration.fixtures.sample_graph_states import get_l3_state

        # Create failed simulation output
        run_dir = create_failed_simulation(tmp_path / "failed_sim")
        state = get_l3_state(run_dir)

        # Execute
        result_state = analysis_node(state)

        # Verify error propagation
        assert result_state["analysis_report"]["status"] == "failed"
        assert "error_logs" in result_state
        assert len(result_state["error_logs"]) > 0

    def test_analysis_with_unstable_simulation(self, sample_simulation_output):
        """
        Test 6: Unstable simulation detected

        Given: Simulation with CFL warnings
        When: analysis_node executes
        Then: Status is 'unstable', issues listed
        """
        # Modify mock output to have CFL violation
        log_file = Path(sample_simulation_output) / "run.log"
        log_content = log_file.read_text()
        log_content += "\nCFL = 1.2\n"  # Add violation
        log_file.write_text(log_content)

        state = {
            "config": AMReXAgentConfig(),
            "run_directory": str(sample_simulation_output),
            "history": []
        }

        # Execute
        result_state = analysis_node(state)

        # Verify unstable detection
        report = result_state["analysis_report"]
        assert report["status"] == "unstable"
        assert len(report["issues"]) > 0
