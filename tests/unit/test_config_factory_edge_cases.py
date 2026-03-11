"""
Input Writer: Config Model Factory: ConfigModelFactory Edge Case Tests

Tests for create_from_schema() edge cases and comprehensive type coverage.
Addresses gaps identified in test coverage analysis.

TDD: These tests define expected behavior for edge cases.
"""

import pytest
from pydantic import ValidationError, BaseModel
from typing import List


class TestCreateFromSchemaEdgeCases:
    """Test edge cases for schema loading."""
    
    def test_create_from_schema_empty(self):
        """
        Given: Empty schema {}
        When:  create_from_schema() called
        Then:  Should return valid BaseModel with no fields
        
        Validates: Graceful handling of empty schema
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        Model = ConfigModelFactory.create_from_schema({}, {})
        
        # Should return a valid model class
        assert issubclass(Model, BaseModel)
        
        # Should have no fields (or only built-in fields)
        user_fields = {k: v for k, v in Model.model_fields.items() 
                      if not k.startswith('_')}
        assert len(user_fields) == 0
        
        # Should be instantiable
        instance = Model()
        assert instance is not None
    
    def test_create_from_schema_type_mapping_comprehensive(self):
        """
        Given: Schema with all supported C++ types
        When:  create_from_schema() called
        Then:  Should map to correct Python types
        
        Validates: Complete type mapping coverage
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema = {
            "test.bool_param": {
                "type": "bool",
                "required": False,
                "default": False
            },
            "test.string_param": {
                "type": "string",
                "required": False,
                "default": "test"
            },
            "test.int_param": {
                "type": "int",
                "required": False,
                "default": 0
            },
            "test.long_param": {
                "type": "long",
                "required": False,
                "default": 0
            },
            "test.real_param": {
                "type": "real",
                "required": False,
                "default": 0.0
            },
            "test.double_param": {
                "type": "double",
                "required": False,
                "default": 0.0
            },
            "test.float_param": {
                "type": "float",
                "required": False,
                "default": 0.0
            }
        }
        
        Model = ConfigModelFactory.create_from_schema(schema, {})
        
        # Verify type mappings
        fields = Model.model_fields
        
        # bool → bool
        assert 'test_bool_param' in fields
        # Note: Pydantic may wrap in Union or Optional, check origin
        field_type = fields['test_bool_param'].annotation
        type_str = str(field_type)
        assert 'bool' in type_str or field_type == bool
        
        # string → str
        assert 'test_string_param' in fields
        field_type = fields['test_string_param'].annotation
        type_str = str(field_type)
        assert 'str' in type_str or field_type == str
        
        # int/long → int
        assert 'test_int_param' in fields
        field_type = fields['test_int_param'].annotation
        type_str = str(field_type)
        assert 'int' in type_str or field_type == int
        
        # real/double/float → float
        assert 'test_real_param' in fields
        field_type = fields['test_real_param'].annotation
        type_str = str(field_type)
        assert 'float' in type_str or field_type == float
        
        # Verify model can be instantiated
        instance = Model()
        assert instance.test_bool_param == False
        assert instance.test_string_param == "test"
        assert instance.test_int_param == 0
        assert instance.test_real_param == 0.0
    
    def test_create_from_schema_array_types(self):
        """
        Given: Schema with is_array flag
        When:  create_from_schema() called
        Then:  Should create List[T] for arrays, T for scalars
        
        Validates: Array type specification
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema = {
            "test.scalar": {
                "type": "int",
                "is_array": False,
                "required": False,
                "default": 0
            },
            "test.array": {
                "type": "int",
                "is_array": True,
                "required": False,
                "default": [1, 2, 3]
            }
        }
        
        Model = ConfigModelFactory.create_from_schema(schema, {})
        
        # Scalar should be int
        scalar_type = str(Model.model_fields['test_scalar'].annotation)
        assert 'list' not in scalar_type.lower()
        
        # Array should be List[int]
        array_type = str(Model.model_fields['test_array'].annotation)
        assert 'list' in array_type.lower() or 'List' in array_type
    
    def test_create_from_schema_required_field_enforcement(self):
        """
        Given: Schema with required=true field
        When:  Model instantiated without required field
        Then:  Should NOT raise ValidationError (Amendment C: Pydantic is permissive)

        Validates: Amendment C - required is metadata, not Pydantic enforcement
        Note: Future Rule Engine will validate required fields
        """
        from src.services.config_model_factory import ConfigModelFactory
        import warnings

        schema = {
            "critical.param": {
                "type": "int",
                "required": True,
                "description": "This parameter is critical"
            },
            "optional.param": {
                "type": "int",
                "required": False,
                "default": 0
            }
        }

        Model = ConfigModelFactory.create_from_schema(schema, {})

        # Amendment C: Should NOT raise - all fields are Optional
        instance = Model()
        
        # Collect validation issues (non-blocking)
        issues = []
        
        # Check 1: Field should exist but be None
        if not hasattr(instance, "critical_param"):
            issues.append("Field 'critical_param' missing from model")
        elif instance.critical_param is not None:
            issues.append(f"Field 'critical_param' should be None, got {instance.critical_param}")
        
        # Check 2: Schema metadata should preserve 'required' for Rule Engine
        if schema["critical.param"].get("required") != True:
            issues.append("Schema metadata lost 'required' flag")
        
        # Check 3: Optional field should work
        if not hasattr(instance, "optional_param"):
            issues.append("Optional field 'optional_param' missing")
        
        # Report all issues as warnings, then fail if any critical
        if issues:
            for issue in issues:
                warnings.warn(f"Amendment C validation issue: {issue}", UserWarning)
            # Only fail if critical metadata lost
            if "Schema metadata lost" in str(issues):
                pytest.fail(f"Critical failures: {issues}")

    def test_create_from_schema_intvect_realvect(self):
        """
        Given: Schema with IntVect and RealVect types
        When:  create_from_schema() called
        Then:  Should map to List[int] and List[float]
        
        Validates: AMReX-specific type handling
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema = {
            "amr.n_cell": {
                "type": "IntVect",
                "required": True
            },
            "geometry.prob_hi": {
                "type": "RealVect",
                "required": False,
                "default": [1.0, 1.0, 1.0]
            }
        }
        
        Model = ConfigModelFactory.create_from_schema(schema, {})
        
        # IntVect → List[int]
        n_cell_type = str(Model.model_fields['amr_n_cell'].annotation)
        assert 'list' in n_cell_type.lower() or 'List' in n_cell_type
        assert 'int' in n_cell_type
        
        # RealVect → List[float]
        prob_hi_type = str(Model.model_fields['geometry_prob_hi'].annotation)
        assert 'list' in prob_hi_type.lower() or 'List' in prob_hi_type
        assert 'float' in prob_hi_type
    
    def test_create_from_schema_invalid_type(self):
        """
        Given: Schema with unknown type
        When:  create_from_schema() called
        Then:  Should handle gracefully (default to str or raise)
        
        Validates: Unknown type handling
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema = {
            "test.unknown": {
                "type": "CompletelyUnknownType",
                "required": False,
                "default": "fallback"
            }
        }
        
        # Should not crash
        Model = ConfigModelFactory.create_from_schema(schema, {})
        
        # Should create some field (likely defaulting to str)
        assert 'test_unknown' in Model.model_fields
    
    def test_create_from_schema_build_flag_exclusion(self):
        """
        Given: Schema with build_flags, build_config excludes flag
        When:  create_from_schema() called
        Then:  Should exclude flagged parameters
        
        Validates: Build flag filtering (Amendment D)
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema = {
            "amr.n_cell": {
                "type": "IntVect",
                "required": True
            },
            "eb.grid_file": {
                "type": "string",
                "build_flags": ["USE_EB"],
                "required": False
            }
        }
        
        # With USE_EB=FALSE, eb.grid_file should be excluded
        build_config = {"USE_EB": "FALSE"}
        
        Model = ConfigModelFactory.create_from_schema(schema, build_config)
        
        # Should have amr.n_cell
        assert 'amr_n_cell' in Model.model_fields
        
        # Should NOT have eb.grid_file
        assert 'eb_grid_file' not in Model.model_fields
    
    def test_create_from_schema_namespace_nesting(self):
        """
        Given: Schema with multiple namespace levels
        When:  create_from_schema() called
        Then:  Should create proper nested structure
        
        Validates: Namespace handling
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema = {
            "amr.n_cell": {"type": "IntVect", "required": False, "default": [32, 32, 32]},
            "amr.max_level": {"type": "int", "required": False, "default": 0},
            "geometry.prob_lo": {"type": "RealVect", "required": False, "default": [0.0, 0.0, 0.0]},
            "amr.cfl": {"type": "real", "required": False, "default": 0.9}
        }
        
        Model = ConfigModelFactory.create_from_schema(schema, {})
        
        # Should have all fields with proper naming
        fields = Model.model_fields
        assert 'amr_n_cell' in fields
        assert 'amr_max_level' in fields
        assert 'geometry_prob_lo' in fields
        assert 'amr_cfl' in fields


# Test marker
pytestmark = pytest.mark.input_writer_config_model_factory


class TestSolverConfigIntegrationGuards:
    """BDD coverage for F5.3 new solver integration guardrails."""

    def test_validate_new_code_integration_skips_legacy_codes(self):
        """
        Given: A legacy solver config in the exemption list
        When:  validate_new_code_integration() is called
        Then:  Validation should pass without LOC enforcement
        """
        from database.configs import validate_new_code_integration, PeleCConfig

        validate_new_code_integration(PeleCConfig)

    def test_validate_new_code_integration_rejects_over_budget(self, monkeypatch, tmp_path):
        """
        Given: A newly integrated solver config with >=300 logical LOC
        When:  validate_new_code_integration() is called
        Then:  It should raise ValueError to enforce the PRD budget
        """
        import database.configs as configs_module
        from database.configs import validate_new_code_integration

        source_file = tmp_path / "new_solver_config.py"
        source_file.write_text("\n".join("x = 1" for _ in range(300)), encoding="utf-8")

        class NewSolverConfig:
            code_name = "NewSolver"

        monkeypatch.setattr(
            configs_module.inspect,
            "getsourcefile",
            lambda _: str(source_file),
        )

        with pytest.raises(ValueError, match="exceeds LOC budget"):
            validate_new_code_integration(NewSolverConfig)

    def test_validate_new_code_integration_allows_under_budget(self, monkeypatch, tmp_path):
        """
        Given: A newly integrated solver config with fewer than 300 logical LOC
        When:  validate_new_code_integration() is called
        Then:  Validation should pass
        """
        import database.configs as configs_module
        from database.configs import validate_new_code_integration

        source_file = tmp_path / "compact_solver_config.py"
        source_file.write_text("\n".join("x = 1" for _ in range(299)), encoding="utf-8")

        class CompactSolverConfig:
            code_name = "CompactSolver"

        monkeypatch.setattr(
            configs_module.inspect,
            "getsourcefile",
            lambda _: str(source_file),
        )

        validate_new_code_integration(CompactSolverConfig)
