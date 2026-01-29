"""
Input Writer: Config Model Factory Enhancement: Build Config Field Filtering

Validates that ConfigModelFactory correctly filters parameters
based on active build flags (e.g., USE_EB, DIM).

Architecture:
    Single schema JSON → Multiple build variants
    7a (extract) → 7b (filter) → Runtime model
    
References:
    - Amendment D.3: Integration with Input Writer
    - Indexing Engine: Build Metadata Extensions: Build flag parsing
"""

import pytest
from typing import Dict, Any, Type
from pydantic import BaseModel, ValidationError

from src.services.config_model_factory import ConfigModelFactory


class TestBasicBuildFlagFiltering:
    """Test fundamental build flag filtering logic."""
    
    @pytest.fixture
    def schema_with_eb_dependency(self) -> Dict[str, Any]:
        """
        Schema with EB-dependent parameters.
        
        Simulates AMReX schema where some parameters require USE_EB=TRUE.
        """
        return {
            "amr.cfl": {
                "type": "Real",
                "default": 0.5,
                "required": False,
                "build_flags": [],  # Always available
            },
            "eb.sphere_radius": {
                "type": "Real",
                "default": 1.0,
                "required": False,
                "build_flags": ["USE_EB"],  # Only if EB enabled
            },
            "eb.sphere_center": {
                "type": "Vector<Real>",
                "default": [0.0, 0.0, 0.0],
                "required": False,
                "build_flags": ["USE_EB"],
            },
        }
    
    def test_eb_enabled_includes_parameters(self, schema_with_eb_dependency):
        """
        Given: Build config with USE_EB=TRUE
        When:  Creating model from schema
        Then:  EB parameters should be included in model fields
        
        Validates: Build flag matching logic
        """
        build_config = {"USE_EB": "TRUE"}
        
        Model = ConfigModelFactory.create_from_schema(
            schema_with_eb_dependency,
            build_config
        )
        
        # EB params should be in the model
        assert "eb_sphere_radius" in Model.model_fields
        assert "eb_sphere_center" in Model.model_fields
        
        # Can instantiate with EB params
        instance = Model(
            amr_cfl=0.5,
            eb_sphere_radius=2.0,
            eb_sphere_center=[1.0, 1.0, 1.0]
        )
        assert instance.eb_sphere_radius == 2.0
    
    def test_eb_disabled_excludes_parameters(self, schema_with_eb_dependency):
        """
        Given: Build config with USE_EB=FALSE
        When:  Creating model from schema
        Then:  EB parameters should be excluded from model fields
        
        Validates: Amendment D.3 - Prevents hallucinated parameters
        """
        build_config = {"USE_EB": "FALSE"}
        
        Model = ConfigModelFactory.create_from_schema(
            schema_with_eb_dependency,
            build_config
        )
        
        # EB params should NOT be in the model
        assert "eb_sphere_radius" not in Model.model_fields
        assert "eb_sphere_center" not in Model.model_fields
        
        # Base params still work
        instance = Model(amr_cfl=0.5)
        assert instance.amr_cfl == 0.5
    
    def test_no_build_config_includes_all(self, schema_with_eb_dependency):
        """
        Given: No build config provided (empty dict)
        When:  Creating model
        Then:  Should include ALL parameters (permissive mode)
        
        Validates: Backward compatibility
        """
        build_config = {}
        
        Model = ConfigModelFactory.create_from_schema(
            schema_with_eb_dependency,
            build_config
        )
        
        # In permissive mode, all params available
        assert "amr_cfl" in Model.model_fields
        assert "eb_sphere_radius" in Model.model_fields


class TestComplexDependencies:
    """Test advanced dependency expressions."""
    
    @pytest.fixture
    def schema_with_complex_deps(self) -> Dict[str, Any]:
        """Schema with multi-condition dependencies."""
        return {
            "amr.cfl": {
                "type": "Real",
                "default": 0.5,
                "build_flags": [],
            },
            "eb.sphere_radius": {
                "type": "Real",
                "default": 1.0,
                "build_flags": ["USE_EB"],
                "dependencies": ["DIM==3"],  # Requires BOTH USE_EB AND 3D
            },
            "prob.num_bubbles": {
                "type": "int",
                "default": 1,
                "build_flags": ["USE_EB"],
                "dependencies": ["!USE_PARTICLES"],  # EB yes, particles no
            },
        }
    
    def test_nested_and_dependencies(self, schema_with_complex_deps):
        """
        Given: Parameter with multiple AND conditions (USE_EB AND DIM==3)
        When:  Build config satisfies both
        Then:  Parameter included
        When:  Build config satisfies only one
        Then:  Parameter excluded
        
        Validates: Complex dependency logic
        """
        # Both satisfied → Include
        Model1 = ConfigModelFactory.create_from_schema(
            schema_with_complex_deps,
            {"USE_EB": "TRUE", "DIM": "3"}
        )
        assert "eb_sphere_radius" in Model1.model_fields
        
        # Only USE_EB satisfied → Exclude
        Model2 = ConfigModelFactory.create_from_schema(
            schema_with_complex_deps,
            {"USE_EB": "TRUE", "DIM": "2"}
        )
        assert "eb_sphere_radius" not in Model2.model_fields, \
            "Parameter requires BOTH USE_EB and DIM==3"
    
    def test_negation_dependencies(self, schema_with_complex_deps):
        """
        Given: Parameter with negation (!USE_PARTICLES)
        When:  Particles disabled
        Then:  Parameter included
        When:  Particles enabled
        Then:  Parameter excluded
        
        Validates: Negation operator support
        """
        # Particles disabled → Include
        Model1 = ConfigModelFactory.create_from_schema(
            schema_with_complex_deps,
            {"USE_EB": "TRUE", "USE_PARTICLES": "FALSE"}
        )
        assert "prob_num_bubbles" in Model1.model_fields
        
        # Particles enabled → Exclude
        Model2 = ConfigModelFactory.create_from_schema(
            schema_with_complex_deps,
            {"USE_EB": "TRUE", "USE_PARTICLES": "TRUE"}
        )
        assert "prob_num_bubbles" not in Model2.model_fields


@pytest.mark.skip(reason="Model caching is optimization, not core Input Writer")
class TestModelCaching:
    """Test performance optimization through model caching."""
    
    def test_same_build_config_returns_cached_model(self, schema_with_eb_dependency):
        """
        Given: Multiple calls with identical build config
        When:  Creating models
        Then:  Should return same cached model instance
        
        Validates: Performance optimization
        """
        build_config = {"USE_EB": "TRUE"}
        
        Model1 = ConfigModelFactory.create_from_schema(
            schema_with_eb_dependency,
            build_config
        )
        
        Model2 = ConfigModelFactory.create_from_schema(
            schema_with_eb_dependency,
            build_config
        )
        
        # Same build config → Same model class
        assert Model1 is Model2, "Should reuse cached model"
    
    def test_different_build_config_creates_new_model(self, schema_with_eb_dependency):
        """
        Given: Calls with different build configs
        When:  Creating models
        Then:  Should create distinct model classes
        
        Validates: Cache invalidation on config change
        """
        Model_EB = ConfigModelFactory.create_from_schema(
            schema_with_eb_dependency,
            {"USE_EB": "TRUE"}
        )
        
        Model_NoEB = ConfigModelFactory.create_from_schema(
            schema_with_eb_dependency,
            {"USE_EB": "FALSE"}
        )
        
        # Different configs → Different models
        assert Model_EB is not Model_NoEB
        assert "eb_sphere_radius" in Model_EB.model_fields
        assert "eb_sphere_radius" not in Model_NoEB.model_fields
