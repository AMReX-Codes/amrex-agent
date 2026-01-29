"""
Input Writer: Config Model Factory Enhancement: Build Flag Error Messages

Validates that attempting to use filtered parameters produces
context-aware error messages that explain the missing build flags.

Architecture:
    Filtered param access → Check full schema → Explain requirement
    
References:
    - Amendment D.3: Context-Aware Validation
    - Architect Service: Agent feedback loop
"""

import pytest
from pydantic import ValidationError

from src.services.config_model_factory import ConfigModelFactory


@pytest.mark.skip(reason="TODO: Requires custom Pydantic BaseModel with __setattr__ override")
class TestContextAwareErrors:
    """Test error messages reference build flags."""
    
    @pytest.fixture
    def model_no_eb(self, schema_with_eb_dependency):
        """Pydantic model with EB disabled."""
        Model = ConfigModelFactory.create_from_schema(
            schema_with_eb_dependency,
            {"USE_EB": "FALSE"}
        )
        return Model(pelec_cfl=0.5)
    
    def test_filtered_param_error_mentions_build_flag(self, model_no_eb):
        """
        Given: Model with EB disabled
        When:  Attempting to set eb.sphere_radius
        Then:  Error message should mention USE_EB requirement
        
        Validates: Amendment D.3 - Clear error explanations
        """
        with pytest.raises((ValidationError, ValueError, AttributeError)) as exc:
            model_no_eb.eb_sphere_radius = 1.0
        
        error_msg = str(exc.value).lower()
        
        # Error should explain the problem
        assert "use_eb" in error_msg, \
            "Error must mention required build flag"
        
        assert any(keyword in error_msg for keyword in ["requires", "needs", "depends"]), \
            "Error should explain dependency"
    
    def test_error_suggests_gnumakefile(self, model_no_eb):
        """
        Given: Filtered parameter access
        When:  Error raised
        Then:  Should suggest where to enable flag (GNUmakefile)
        
        Validates: Actionable error messages
        """
        with pytest.raises((ValidationError, ValueError, AttributeError)) as exc:
            model_no_eb.eb_sphere_center = [1.0, 1.0, 1.0]
        
        error_msg = str(exc.value).lower()
        
        assert any(keyword in error_msg for keyword in ["gnumakefile", "build", "compile"]), \
            "Error should explain where to enable the flag"
    
    def test_good_error_vs_bad_error(self, model_no_eb):
        """
        Example of what we're preventing:
        
        ❌ BAD:  "Unknown parameter: eb.sphere_radius"
        ✅ GOOD: "Parameter 'eb.sphere_radius' requires USE_EB=TRUE in GNUmakefile"
        
        Validates: User experience improvement
        """
        with pytest.raises((ValidationError, ValueError, AttributeError)) as exc:
            model_no_eb.eb_sphere_radius = 1.0
        
        error_msg = str(exc.value)
        
        # Should NOT be generic
        assert "unknown" not in error_msg.lower(), \
            "Error should be specific, not generic 'unknown parameter'"
        
        # Should BE specific
        assert "eb.sphere_radius" in error_msg or "eb_sphere_radius" in error_msg, \
            "Error should name the specific parameter"


@pytest.mark.skip(reason="TODO: Requires custom Pydantic BaseModel with __setattr__ override")
class TestMultipleFilteredParams:
    """Test errors when multiple params are filtered."""
    
    def test_lists_all_required_flags(self, schema_with_complex_deps):
        """
        Given: Parameter requiring USE_EB AND DIM==3
        When:  Attempting to use with USE_EB only
        Then:  Error should list ALL missing requirements
        
        Validates: Complete dependency explanation
        """
        Model = ConfigModelFactory.create_from_schema(
            schema_with_complex_deps,
            {"USE_EB": "TRUE", "DIM": "2"}  # Missing DIM==3
        )
        
        instance = Model(pelec_cfl=0.5)
        
        with pytest.raises((ValidationError, ValueError, AttributeError)) as exc:
            instance.eb_sphere_radius = 1.0
        
        error_msg = str(exc.value)
        
        # Should mention the dimension requirement
        assert "dim" in error_msg.lower() or "3" in error_msg, \
            "Error should explain DIM requirement"
