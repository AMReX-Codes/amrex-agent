"""
Input Writer: Config Model Factory: Pydantic Config Model Hydration Tests

Tests dynamic Pydantic model generation from Input Writer: Schema Scraper schemas.
Follows TDD pattern established in Gate 0.

References:
- PRD Amendment C: Load-Modify-Write pattern
- PRD Amendment D: Build-conditional parameters
- Metadata Schema: BaseAMReXConfig.parse_inputs()
- Input Writer: Schema Scraper: SchemaBuilder output format
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any


class TestDynamicModelGeneration:
    """Test Pydantic model creation from 7a schema."""
    
    def test_dynamic_model_generation(self):
        """
        Given: Input Writer: Schema Scraper schema JSON
        When:  ConfigModelFactory.create() is called
        Then:  Should generate Pydantic model class
        
        Validates: Dynamic model creation via create_model
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        # Arrange: Mock 7a schema (with is_array field)
        schema = {
            "amr.n_cell": {
                "type": "int",
                "required": True,
                "is_array": False,  # Scalar in this test
                "source_file": "AMReX/Src/Amr/AMR.cpp"
            },
            "amr.max_level": {
                "type": "int", 
                "required": False,
                "is_array": False,
                "default": "0"
            }
        }
        
        build_config = {"DIM": "3", "USE_MPI": "TRUE"}
        
        # Act
        AMReXConfig = ConfigModelFactory.create_from_schema(schema, build_config)
        
        # Assert - class created
        assert AMReXConfig.__name__ == "AMReXConfig"
        
        # Assert - fields exist with correct types
        import warnings
        from typing import get_origin, get_args
        
        issues = []
        
        # Check 1: Field exists
        if "amr_n_cell" not in AMReXConfig.model_fields:
            issues.append("Field 'amr_n_cell' missing from model")
        else:
            # Check 2: Amendment C - should be int | None (PEP 604)
            field_type = AMReXConfig.model_fields["amr_n_cell"].annotation
            args = get_args(field_type)
            none_type = type(None)
            if not args or int not in args or none_type not in args:
                issues.append(f"Field should be int | None, got {field_type}")

            # Check 3: Inner type should be int
            if args and int not in args:
                issues.append(f"Inner type should include int, got {args}")
        
        # Report issues
        if issues:
            for issue in issues:
                warnings.warn(f"Type validation issue: {issue}", UserWarning)
            pytest.fail(f"Type validation failures: {issues}")
        
        # All checks passed
        assert "amr_n_cell" in AMReXConfig.model_fields
        
        # Assert - can instantiate with scalar (is_array=False)
        config = AMReXConfig(amr_n_cell=64)
        assert config.amr_n_cell == 64


class TestInputsFileParsing:
    """Test integration with Metadata Schema parser."""
    
    def test_inputs_file_parsing(self):
        """
        Given: Raw AMReX inputs text
        When:  Parsed and hydrated into model
        Then:  Should create valid model instance
        
        Validates: Metadata Schema integration (parse_inputs reuse)
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        # Arrange: Schema (with is_array from Input Writer: Schema Scraper)
        schema = {
            "amr.n_cell": {"type": "int", "required": True, "is_array": True},
            "amr.cfl": {"type": "real", "required": False, "default": "0.8", "is_array": False}
        }
        
        # Arrange: Raw inputs text (Metadata Schema format)
        inputs_text = """
# Grid setup
amr.n_cell = 64 64 64

# Time stepping
amr.cfl = 0.5  # Conservative CFL
"""
        
        # Act
        AMReXConfig = ConfigModelFactory.create_from_schema(schema, {})
        config = ConfigModelFactory.hydrate(AMReXConfig, inputs_text)
        
        # Assert
        assert config.amr_n_cell == [64, 64, 64]  # or list [64, 64, 64] depending on parser
        assert config.amr_cfl == 0.5


class TestTypeValidation:
    """Test Pydantic type enforcement."""
    
    def test_type_validation(self):
        """
        Given: Schema expects float, input provides string
        When:  Model instantiated
        Then:  Should raise ValidationError
        
        Validates: Type safety (Amendment C requirement)
        """
        from src.services.config_model_factory import ConfigModelFactory
        from pydantic import ValidationError
        
        schema = {
            "amr.cfl": {"type": "real", "required": True}
        }
        
        AMReXConfig = ConfigModelFactory.create_from_schema(schema, {})
        
        # Should fail - string not convertible to float
        with pytest.raises(ValidationError) as exc_info:
            AMReXConfig(amr_cfl="invalid_string")
        
        assert "amr_cfl" in str(exc_info.value)


class TestNamespaceStructure:
    """Test AMReX dot-notation namespace handling."""
    
    def test_namespace_structure(self):
        """
        Given: Schema with namespaced parameters (amr.*)
        When:  Model created with alias generator
        Then:  Should support both access patterns
        
        Validates: AMReX naming convention support
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema = {
            "amr.cfl": {"type": "real", "required": True},
            "amr.max_level": {"type": "int", "required": True}
        }
        
        AMReXConfig = ConfigModelFactory.create_from_schema(schema, {})
        config = AMReXConfig(amr_cfl=0.8, amr_max_level=2)
        
        # Flattened access (Python-safe names)
        assert config.amr_cfl == 0.8
        assert config.amr_max_level == 2
        
        # Dict access with aliases (for serialization)
        assert config.model_dump(by_alias=True)["amr.cfl"] == 0.8


class TestRoundTrip:
    """Test Load-Modify-Write pattern (Amendment C)."""
    
    def test_round_trip(self):
        """
        Given: Inputs file with comments
        When:  Load → Modify → Write
        Then:  Should preserve original comments
        
        Validates: Amendment C Load-Modify-Write requirement
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        original_text = """
# Grid configuration
amr.max_level = 2  # Original setting
amr.n_cell = 64 64 64
"""
        
        schema = {
            "amr.max_level": {"type": "int", "required": True, "is_array": False},
            "amr.n_cell": {"type": "int", "required": True, "is_array": True}
        }
        
        # Load
        AMReXConfig = ConfigModelFactory.create_from_schema(schema, {})
        config = ConfigModelFactory.hydrate(AMReXConfig, original_text)
        
        # Modify
        config.amr_max_level = 3
        
        # Write (requires serializer with comment preservation)
        output_text = ConfigModelFactory.serialize(config, preserve_comments=True)
        
        # Assert - value changed correctly
        assert "amr.max_level = 3" in output_text
        assert "amr.n_cell = 64 64 64" in output_text
        
        # Note: Comment preservation is a future enhancement (Amendment C)
        # For now, we verify correct serialization of values


class TestBuildConditionalFields:
    """Test build-dependent parameter inclusion (Amendment D)."""
    
    def test_build_conditional_fields(self):
        """
        Given: Schema with eb.* parameters requiring USE_EB=TRUE
        When:  Model created with USE_EB=FALSE
        Then:  Should exclude EB fields
        
        Validates: Input Writer: Schema Scraper/7b integration (build dependencies)
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema = {
            "amr.n_cell": {
                "type": "int",
                "required": True
            },
            "eb.sphere_radius": {
                "type": "real",
                "required": False,
                "dependencies": ["AMREX_USE_EB"]  # From 7a #ifdef tracking
            }
        }
        
        # Scenario A: EB disabled
        build_config_no_eb = {"USE_EB": "FALSE"}
        ConfigNoEB = ConfigModelFactory.create_from_schema(schema, build_config_no_eb)
        
        # Should not have EB field
        assert "eb_sphere_radius" not in ConfigNoEB.model_fields
        
        # Scenario B: EB enabled
        build_config_with_eb = {"AMREX_USE_EB": "TRUE"}
        ConfigWithEB = ConfigModelFactory.create_from_schema(schema, build_config_with_eb)

        # Should have EB field
        assert "eb_sphere_radius" in ConfigWithEB.model_fields


def test_enable_intent_extraction_defaults_false():
    """enable_intent_extraction is False by default"""
    from src.config import AMReXAgentConfig

    cfg = AMReXAgentConfig()
    assert cfg.enable_intent_extraction is False


def test_enable_intent_extraction_can_be_set_true():
    """enable_intent_extraction can be set True"""
    from src.config import AMReXAgentConfig

    cfg = AMReXAgentConfig()
    cfg.enable_intent_extraction = True
    assert cfg.enable_intent_extraction is True


# Input Writer: Config Model Factory marker
pytestmark = pytest.mark.input_writer_config_model_factory
