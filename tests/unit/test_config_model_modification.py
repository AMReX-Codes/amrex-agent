"""
Input Writer: Config Model Factory Extension: Model Modification Tests

Tests ConfigModelFactory.apply_modifications() method.
Bridges Architect output (tuples) to Pydantic model updates.

TDD: Tests written FIRST to define expected behavior.
"""

import pytest
from pydantic import BaseModel, Field, ConfigDict


@pytest.fixture
def sample_model():
    """Create a sample Pydantic model for testing."""
    class TestConfig(BaseModel):
        model_config = ConfigDict(
            populate_by_name=True,
            extra='allow'  # Allow unknown fields
        )
        
        # Fields with aliases
        amr_n_cell: list[int] = Field(default=[32, 32, 32], alias="amr.n_cell")
        amr_max_level: int = Field(default=0, alias="amr.max_level")
        amr_cfl: float = Field(default=0.9, alias="amr.cfl")
        geometry_is_periodic: list[int] = Field(default=[0, 0, 0], alias="geometry.is_periodic")
    
    return TestConfig()


class TestApplyModifications:
    """Test modification application to Pydantic models."""
    
    def test_alias_resolution(self, sample_model):
        """
        Given: Modification using dot notation (alias)
        When:  apply_modifications() called
        Then:  Should update the correct field
        
        Validates: Alias → attribute mapping
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        modifications = [
            ("amr.n_cell", [128, 128, 128])
        ]
        
        updated = ConfigModelFactory.apply_modifications(
            sample_model,
            modifications
        )
        
        # Verify field updated via alias
        assert updated.amr_n_cell == [128, 128, 128]
        # Original attribute name should work too
        assert updated.amr_n_cell == [128, 128, 128]
    
    def test_type_coercion_string_to_list(self, sample_model):
        """
        Given: String value for list field
        When:  apply_modifications() called
        Then:  Should parse string to list
        
        Validates: Type coercion (Architect outputs strings)
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        modifications = [
            ("amr.n_cell", "256 256 256")  # String, not list
        ]
        
        updated = ConfigModelFactory.apply_modifications(
            sample_model,
            modifications
        )
        
        # Should parse to [256, 256, 256]
        assert updated.amr_n_cell == [256, 256, 256]
        assert isinstance(updated.amr_n_cell, list)
        assert all(isinstance(x, int) for x in updated.amr_n_cell)
    
    def test_type_coercion_string_to_float(self, sample_model):
        """
        Given: String value for float field
        When:  apply_modifications() called
        Then:  Should parse to float
        
        Validates: Scalar type coercion
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        modifications = [
            ("amr.cfl", "0.5")  # String
        ]
        
        updated = ConfigModelFactory.apply_modifications(
            sample_model,
            modifications
        )
        
        assert updated.amr_cfl == 0.5
        assert isinstance(updated.amr_cfl, float)
    
    def test_type_coercion_string_to_int(self, sample_model):
        """
        Given: String value for int field
        When:  apply_modifications() called
        Then:  Should parse to int
        
        Validates: Integer type coercion
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        modifications = [
            ("amr.max_level", "2")  # String
        ]
        
        updated = ConfigModelFactory.apply_modifications(
            sample_model,
            modifications
        )
        
        assert updated.amr_max_level == 2
        assert isinstance(updated.amr_max_level, int)
    
    def test_unknown_parameter_permissive(self, sample_model):
        """
        Given: Modification with hallucinated parameter
        When:  apply_modifications() called
        Then:  Should warn but not crash
        
        Validates: Permissive handling (Architect may hallucinate)
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        modifications = [
            ("hallucinated.param", "value"),  # Not in schema
            ("amr.n_cell", [64, 64, 64])  # Valid
        ]
        
        # Should not raise exception
        updated = ConfigModelFactory.apply_modifications(
            sample_model,
            modifications
        )
        
        # Valid param should be updated
        assert updated.amr_n_cell == [64, 64, 64]
        
        # Hallucinated param may be set if extra='allow'
        # or skipped - either is acceptable
    
    def test_multiple_modifications(self, sample_model):
        """
        Given: Multiple modifications in one call
        When:  apply_modifications() called
        Then:  Should apply all modifications
        
        Validates: Batch updates
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        modifications = [
            ("amr.n_cell", [128, 128, 128]),
            ("amr.max_level", 2),
            ("amr.cfl", 0.5),
        ]
        
        updated = ConfigModelFactory.apply_modifications(
            sample_model,
            modifications
        )
        
        assert updated.amr_n_cell == [128, 128, 128]
        assert updated.amr_max_level == 2
        assert updated.amr_cfl == 0.5
    
    def test_preserves_unchanged_fields(self, sample_model):
        """
        Given: Modification affecting some fields
        When:  apply_modifications() called
        Then:  Should preserve unchanged fields
        
        Validates: Selective updates
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        original_periodic = sample_model.geometry_is_periodic
        
        modifications = [
            ("amr.n_cell", [128, 128, 128])
        ]
        
        updated = ConfigModelFactory.apply_modifications(
            sample_model,
            modifications
        )
        
        # Changed
        assert updated.amr_n_cell == [128, 128, 128]
        
        # Unchanged
        assert updated.geometry_is_periodic == original_periodic


# Input Writer: Config Model Factory extension marker
pytestmark = pytest.mark.input_writer_config_model_factory
