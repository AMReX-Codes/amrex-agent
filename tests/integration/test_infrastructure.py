'''
Infrastructure validation tests.
Verifies that ladder fixtures work correctly before building Level 1-4 tests.
'''
import pytest
from pathlib import Path


class TestIntegrationInfrastructure:
    '''Verifies shared fixture infrastructure.'''

    @pytest.mark.integration_l1
    def test_integration_level_detection(self, integration_level):
        '''1. Verify marker detection works.'''
        assert integration_level == 1

    @pytest.mark.integration_l1
    def test_l1_state_has_required_fields(self, ladder_state):
        '''2. Verify L1 state has GraphState required fields.'''
        assert "user_requirement" in ladder_state
        assert "config" in ladder_state
        assert "mode" in ladder_state
        assert ladder_state["mode"] == "initial"
        assert ladder_state["iteration"] == 0

    @pytest.mark.integration_l2
    def test_l2_state_has_plan(self, ladder_state):
        '''3. Verify L2 state includes populated plan.'''
        assert "plan" in ladder_state
        assert ladder_state["plan"] is not None
        assert "baseline" in ladder_state["plan"]

    @pytest.mark.integration_l3
    def test_l3_state_has_mock_output(self, ladder_state):
        '''4. Verify L3 state points to valid mock files.'''
        run_dir = Path(ladder_state.get("run_directory", ladder_state.get("run_dir")))
        assert run_dir.exists()
        assert (run_dir / "run.log").exists()
        assert (run_dir / "plt00000" / "Header").exists()

        log_content = (run_dir / "run.log").read_text()
        assert "completed successfully" in log_content

    @pytest.mark.integration_l2
    def test_fixture_uses_tmp_path(self, ladder_state, tmp_path):
        '''5. Verify tmp_path isolation.'''
        assert str(tmp_path) in str(ladder_state["config"].output_dir)

    @pytest.mark.integration_l1
    def test_architect_node_fixture_is_real(self, architect_node):
        '''6. Verify L1 gets real architect_node function.'''
        assert callable(architect_node)
        assert hasattr(architect_node, "__name__")
        assert "architect" in architect_node.__name__.lower()

    @pytest.mark.integration_l3
    def test_analysis_node_fixture_is_real_at_l3(self, analysis_node):
        '''7. Verify L3 gets real analysis_node.'''
        assert callable(analysis_node)
        assert hasattr(analysis_node, "__name__")

    def test_unit_test_gets_mocks(self, architect_node, integration_level):
        '''8. Verify unit tests (no marker) get mocked nodes.'''
        assert integration_level == 0

        sample_state = {"config": None}
        result = architect_node(sample_state)

        assert isinstance(result, dict)
        assert "plan" in result
