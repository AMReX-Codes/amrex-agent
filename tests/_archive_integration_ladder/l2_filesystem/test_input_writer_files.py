"""
Level 2 Integration: InputWriter File Generation

Tests file content and modification application:
- Inputs file created with modifications
- Modifications correctly applied
- File content validation

Mocked: ArchitectService, ReviewerOrchestrator
Real: InputWriterNode, InputWriterService, filesystem operations
"""
import pytest
from pathlib import Path
from src.nodes.input_writer_node import input_writer_node


@pytest.mark.integration_l2
@pytest.mark.requires_filesystem
class TestInputWriterFiles:
    """Level 2: File content validation."""

    def test_inputs_file_written_with_modifications(self, ladder_state, tmp_path):
        """
        Test 1: Inputs file created with modifications applied

        Given: Plan with amr.n_cell and pelec.cfl modifications
        When: InputWriterNode executes
        Then: inputs file exists with modified values
        """
        state = ladder_state  # L2 state from fixture

        # Verify L2 state has plan populated
        assert state["plan"] is not None
        assert "modifications" in state["plan"]

        # Update config to use tmp_path
        state["config"].output_dir = str(tmp_path)

        # Execute InputWriter
        updates = input_writer_node(state)

        # Verify file created
        assert "inputs_file_path" in updates
        inputs_path = Path(updates["inputs_file_path"])
        assert inputs_path.exists(), f"inputs file not created at {inputs_path}"

        # Read and verify content
        content = inputs_path.read_text()

        # Check modifications were applied
        # L2 state fixture has: amr.n_cell = "64 64 64"
        assert "amr.n_cell" in content
        assert "64 64 64" in content

        # Verify it's a valid inputs file (has some structure)
        assert len(content) > 0
        assert "=" in content  # Parameter assignment format

    def test_multiple_modifications_applied(self, tmp_path):
        """
        Test 2: Multiple modifications are all applied

        Given: Plan with 3 different modifications
        When: InputWriterNode executes
        Then: All modifications appear in inputs file
        """
        from tests.integration.fixtures.sample_graph_states import get_l2_state

        state = get_l2_state(tmp_path)

        # Add multiple modifications
        state["plan"]["modifications"] = [
            {"section": "amr", "parameter": "n_cell", "value": "128 128 128"},
            {"section": "pelec", "parameter": "cfl", "value": "0.3"},
            {"section": "amr", "parameter": "max_level", "value": "2"}
        ]

        state["config"].output_dir = str(tmp_path)

        # Execute
        updates = input_writer_node(state)

        # Verify all modifications
        content = Path(updates["inputs_file_path"]).read_text()

        assert "amr.n_cell" in content
        assert "128 128 128" in content

        assert "pelec.cfl" in content
        assert "0.3" in content

        assert "amr.max_level" in content
        assert "2" in content

    def test_empty_modifications_creates_baseline(self, tmp_path):
        """
        Test 3: Empty modifications list creates baseline file

        Given: Plan with empty modifications list
        When: InputWriterNode executes
        Then: Baseline inputs file is created
        """
        from tests.integration.fixtures.sample_graph_states import get_l2_state

        state = get_l2_state(tmp_path)
        state["plan"]["modifications"] = []  # No modifications
        state["config"].output_dir = str(tmp_path)

        # Execute
        updates = input_writer_node(state)

        # Verify file created even with no modifications
        inputs_path = Path(updates["inputs_file_path"])
        assert inputs_path.exists()

        # Should still have basic structure
        content = inputs_path.read_text()
        assert len(content) > 0
