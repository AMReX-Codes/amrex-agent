"""
Input Writer: Inputs File Writer: Inputs File Writer - Unit Tests

Tests the "Ghostwriter" serialization pattern:
- Preserve comments and formatting
- Modify values in-place
- Append new parameters

TDD: These tests define expected behavior BEFORE implementation.
"""

import pytest
from pydantic import BaseModel, Field, ConfigDict


# Fixtures

@pytest.fixture
def mock_model_class():
    """Create a temporary Pydantic model representing an AMReX config."""
    class MockConfig(BaseModel):
        model_config = ConfigDict(populate_by_name=True)
        
        amr_n_cell: list[int] = Field(alias="amr.n_cell")
        amr_cfl: float = Field(alias="amr.cfl")
        geometry_is_periodic: list[int] = Field(alias="geometry.is_periodic")
        # Optional field for addition tests
        new_param: str | None = Field(default=None, alias="amr.new_param")
    
    return MockConfig


@pytest.fixture
def sample_text():
    return """# Grid Configuration
amr.n_cell = 64 64 64

# Physics Settings
amr.cfl     = 0.9  # High efficiency
geometry.is_periodic = 0 0 0
"""


# Tests

class TestInputsFileWriterSerialization:
    """Test serialization without original text (scratch generation)."""
    
    def test_basic_serialization(self, mock_model_class):
        """
        Given: Pydantic model with values
        When:  Serialize without original_text
        Then:  Should generate clean AMReX format
        
        Validates: Scratch file generation (no Ghostwriter)
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        # Arrange
        model = mock_model_class(
            amr_n_cell=[32, 32, 32], 
            amr_cfl=0.5, 
            geometry_is_periodic=[1, 1, 0]
        )
        
        # Act
        output = InputsFileWriter.serialize(model)
        
        # Assert
        assert "amr.n_cell = 32 32 32" in output
        assert "amr.cfl = 0.5" in output
        assert "geometry.is_periodic = 1 1 0" in output
        # Should not have comments since no source text
        assert "#" not in output
    
    def test_multiline_value_handling(self, mock_model_class):
        """
        Given: Model with list values
        When:  Serialize
        Then:  Should format as space-separated string
        
        Validates: Array serialization
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        model = mock_model_class(
            amr_n_cell=[128, 64, 32],
            amr_cfl=0.9,
            geometry_is_periodic=[1, 0, 1]
        )
        
        output = InputsFileWriter.serialize(model)
        
        assert "amr.n_cell = 128 64 32" in output
        # Ensure not printing Python list repr
        assert "[" not in output
        assert "]" not in output


class TestGhostwriterPattern:
    """Test the Ghostwriter pattern: preserve formatting, change values."""
    
    def test_full_round_trip_no_changes(self, mock_model_class, sample_text):
        """
        Given: Model matching original text exactly
        When:  Serialize with original_text
        Then:  Should preserve bytes exactly (idempotency)
        
        Validates: Amendment C - Round-trip preservation
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        # Arrange - model matches original
        model = mock_model_class(
            amr_n_cell=[64, 64, 64],
            amr_cfl=0.9,
            geometry_is_periodic=[0, 0, 0]
        )
        
        # Act
        output = InputsFileWriter.serialize(model, original_text=sample_text)
        
        # Assert - exact preservation
        assert output.strip() == sample_text.strip()
    
    def test_modified_value_injection(self, mock_model_class, sample_text):
        """
        Given: Model with changed value
        When:  Serialize with original_text
        Then:  Should change value but preserve comment and spacing
        
        Validates: Ghostwriter - surgical value replacement
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        # Arrange - change CFL from 0.9 to 0.1
        model = mock_model_class(
            amr_n_cell=[64, 64, 64],
            amr_cfl=0.1,  # Changed
            geometry_is_periodic=[0, 0, 0]
        )
        
        # Act
        output = InputsFileWriter.serialize(model, original_text=sample_text)
        
        # Assert - value changed, formatting preserved
        assert "amr.cfl     = 0.1  # High efficiency" in output
        # Original had extra spaces: "amr.cfl     = "
    
    def test_new_parameter_insertion(self, mock_model_class, sample_text):
        """
        Given: Model with new parameter not in original
        When:  Serialize with original_text
        Then:  Should append new param at end
        
        Validates: Agent can add new parameters
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        # Arrange - add new parameter
        model = mock_model_class(
            amr_n_cell=[64, 64, 64],
            amr_cfl=0.9,
            geometry_is_periodic=[0, 0, 0],
            new_param="added_value"  # New
        )
        
        # Act
        output = InputsFileWriter.serialize(model, original_text=sample_text)
        
        # Assert - new param appended
        assert "amr.new_param = added_value" in output
        # Should be at the end
        assert output.strip().endswith("amr.new_param = added_value")
    
    def test_formatting_preservation(self, mock_model_class):
        """
        Given: Original with unusual spacing
        When:  Modify value
        Then:  Should preserve spacing around equals
        
        Validates: User formatting preferences respected
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        text = "amr.n_cell   =   64 64 64"
        model = mock_model_class(
            amr_n_cell=[128, 128, 128],  # Changed
            amr_cfl=0.9,
            geometry_is_periodic=[0, 0, 0]
        )
        
        output = InputsFileWriter.serialize(model, original_text=text)
        
        # Value changes, spacing remains
        assert "amr.n_cell   =   128 128 128" in output
    
    def test_comment_preservation(self, mock_model_class):
        """
        Given: Original with block and inline comments
        When:  Modify value
        Then:  Should preserve all comments
        
        Validates: Comment preservation (Amendment C requirement)
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        text = """# Block Comment
amr.cfl = 0.5 # Inline Comment
"""
        model = mock_model_class(
            amr_n_cell=[64, 64, 64],
            amr_cfl=0.1,  # Changed
            geometry_is_periodic=[0, 0, 0]
        )
        
        output = InputsFileWriter.serialize(model, original_text=text)
        
        assert "# Block Comment" in output
        assert "# Inline Comment" in output
        assert "amr.cfl = 0.1 # Inline Comment" in output

    def test_parameter_ordering(self, mock_model_class, sample_text):
        """
        Given: Original with specific parameter order
        When:  Modify some values
        Then:  Should preserve original parameter order
        
        Validates: Parameter ordering maintained
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        model = mock_model_class(
            amr_n_cell=[64, 64, 64],
            amr_cfl=0.1,  # Changed
            geometry_is_periodic=[0, 0, 0]
        )
        
        output = InputsFileWriter.serialize(model, original_text=sample_text)
        lines = [l for l in output.split(' ') if l.strip() and not l.strip().startswith('#')]
        
        # amr.n_cell should come before amr.cfl
        n_cell_idx = next(i for i, l in enumerate(lines) if 'amr.n_cell' in l)
        cfl_idx = next(i for i, l in enumerate(lines) if 'amr.cfl' in l)
        assert n_cell_idx < cfl_idx
    
    def test_namespace_section_handling(self, mock_model_class):
        """
        Given: Parameters from multiple namespaces
        When:  Serialize
        Then:  Should group by namespace (optional enhancement)
        
        Validates: Namespace grouping
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        model = mock_model_class(
            amr_n_cell=[64, 64, 64],
            amr_cfl=0.9,
            geometry_is_periodic=[0, 0, 0]
        )
        
        output = InputsFileWriter.serialize(model)
        
        # All parameters should be present
        assert 'amr.n_cell' in output
        assert 'amr.cfl' in output
        assert 'geometry.is_periodic' in output
    
    def test_inline_comment_alignment(self, mock_model_class):
        """
        Given: Original with aligned inline comments
        When:  Modify values with different lengths
        Then:  Should preserve comment alignment (best effort)
        
        Validates: Comment column alignment
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        text = """amr.n_cell = 64 64 64          # Grid
amr.cfl = 0.9                # CFL"""
        
        model = mock_model_class(
            amr_n_cell=[128, 128, 128],
            amr_cfl=0.1,
            geometry_is_periodic=[0, 0, 0]
        )
        
        output = InputsFileWriter.serialize(model, original_text=text)
        
        # Comments should still be present
        assert "# Grid" in output
        assert "# CFL" in output
    
    def test_round_trip_single_modification(self, mock_model_class, sample_text):
        """
        Given: Model with one value changed
        When:  Round-trip
        Then:  Only one line should differ from original
        
        Validates: Minimal diff principle
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        model = mock_model_class(
            amr_n_cell=[64, 64, 64],  # Unchanged
            amr_cfl=0.1,  # Changed from 0.9
            geometry_is_periodic=[0, 0, 0]  # Unchanged
        )
        
        output = InputsFileWriter.serialize(model, original_text=sample_text)
        
        original_lines = sample_text.split(' ')
        output_lines = output.split(' ')
        
        # Count different lines
        differences = sum(1 for o, n in zip(original_lines, output_lines) if o != n)
        
        # Should have minimal differences (1 value change)
        assert differences <= 2  # Allow some tolerance
    
    def test_metadata_preservation(self, mock_model_class):
        """
        Given: Original with blank lines and section headers
        When:  Serialize
        Then:  Should preserve structural elements
        
        Validates: Non-parameter content preservation
        """
        from src.services.inputs_file_writer import InputsFileWriter
        
        text = """# ===== Grid Setup =====

amr.n_cell = 64 64 64

# ===== Physics =====

amr.cfl = 0.9
"""
        model = mock_model_class(
            amr_n_cell=[64, 64, 64],
            amr_cfl=0.9,
            geometry_is_periodic=[0, 0, 0]
        )
        
        output = InputsFileWriter.serialize(model, original_text=text)
        
        # Section headers should be preserved
        assert "# ===== Grid Setup =====" in output
        assert "# ===== Physics =====" in output
        
        # Blank lines should be preserved (approximately)
        assert ' ' in output



# Input Writer: Inputs File Writer marker
pytestmark = pytest.mark.input_writer_inputs_file_writer
