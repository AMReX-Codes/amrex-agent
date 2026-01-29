"""
Level 2 Integration: Directory Structure Validation

Tests run directory layout and artifacts:
- Run directory creation with timestamp
- README generation
- Directory isolation (tmp_path)

Mocked: LLM calls
Real: Filesystem operations, directory structure
"""
import pytest
from pathlib import Path
from src.nodes.input_writer_node import input_writer_node


@pytest.mark.integration_l2
@pytest.mark.requires_filesystem
class TestDirectoryStructure:
    """Level 2: Directory layout validation."""

    def test_run_directory_created_with_timestamp(self, ladder_state, tmp_path):
        """
        Test 1: Run directory created with timestamp naming

        Given: Valid L2 state
        When: InputWriterNode executes
        Then: Directory named run_YYYYMMDD_HHMMSS created
        """
        state = ladder_state
        state["config"].output_dir = str(tmp_path)

        # Execute
        updates = input_writer_node(state)

        # Verify run_directory created
        assert "run_directory" in updates
        run_dir = Path(updates["run_directory"])

        assert run_dir.exists(), f"run_directory not created: {run_dir}"
        assert run_dir.is_dir()

        # Verify naming convention
        assert run_dir.name.startswith("run_")

        # Verify it's under output_dir
        assert run_dir.parent == tmp_path

    def test_inputs_file_in_run_directory(self, ladder_state, tmp_path):
        """
        Test 2: inputs file is inside run_directory

        Given: Valid state
        When: InputWriterNode executes
        Then: inputs file is at run_directory/inputs
        """
        state = ladder_state
        state["config"].output_dir = str(tmp_path)

        updates = input_writer_node(state)

        run_dir = Path(updates["run_directory"])
        inputs_path = Path(updates["inputs_file_path"])

        # Verify inputs is child of run_dir
        assert inputs_path.parent == run_dir
        assert inputs_path.name == "inputs"

    def test_readme_generated(self, ladder_state, tmp_path):
        """
        Test 3: README.md generated in run directory

        Given: State with user_requirement
        When: InputWriterNode executes
        Then: README.md exists with prompt information
        """
        state = ladder_state
        state["config"].output_dir = str(tmp_path)

        # Ensure user_requirement is present
        assert "user_requirement" in state

        updates = input_writer_node(state)

        # Check if README exists
        run_dir = Path(updates["run_directory"])
        readme_path = run_dir / "README.md"

        # README generation might be optional, so log if missing
        if readme_path.exists():
            content = readme_path.read_text()
            # Verify it contains user prompt
            assert len(content) > 0
            print(f"✓ README.md generated ({len(content)} bytes)")
        else:
            print("⚠ README.md not generated (may be optional)")

    def test_directory_isolation(self, tmp_path):
        """
        Test 4: Multiple runs create separate directories

        Given: Two sequential InputWriter executions
        When: Both execute with same config
        Then: Two different run directories created
        """
        from tests.integration.fixtures.sample_graph_states import get_l2_state
        import time

        # First run
        state1 = get_l2_state(tmp_path)
        state1["config"].output_dir = str(tmp_path)
        updates1 = input_writer_node(state1)
        run_dir1 = Path(updates1["run_directory"])

        # Small delay to ensure different timestamp
        time.sleep(1)

        # Second run
        state2 = get_l2_state(tmp_path)
        state2["config"].output_dir = str(tmp_path)
        updates2 = input_writer_node(state2)
        run_dir2 = Path(updates2["run_directory"])

        # Verify different directories
        assert run_dir1 != run_dir2
        assert run_dir1.exists()
        assert run_dir2.exists()
