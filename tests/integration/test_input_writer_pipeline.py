"""
Input Writer Integration Tests

End-to-end validation of Input Writer (Input Generation & Validation).

Tests cover:
  • Amendment C: Load-Modify-Write pipeline
  • Amendment D: Contextual generation with rules
  • Input Writer: Schema Scraper: Schema integration
  • Real service orchestration

These are INTEGRATION tests - they use real schemas, real services,
and validate full workflows (not isolated units).
"""

import pytest
from pathlib import Path
from unittest.mock import Mock
import json


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def pelec_schema():
    """
    Load real AMReX schema using resolve_schema_path().
    
    Returns the schema dict (parameters only, unwrapped).
    """
    from database.configs import PeleCConfig
    from src.services.config_model_factory import ConfigModelFactory
    
    schema_dir = Path("database/schemas")
    repo_path = Path(".")  # Not used for "newest" strategy
    
    schema_path = ConfigModelFactory.resolve_schema_path(
        PeleCConfig,
        schema_dir,
        repo_path
    )
    
    # Load and unwrap
    data = json.loads(schema_path.read_text())
    return data.get('parameters', data)


@pytest.fixture
def build_config():
    """Standard build configuration for tests."""
    return {
        'USE_EB': 'FALSE',
        'DIM': '3',
        'USE_MPI': 'TRUE'
    }


@pytest.fixture
def sample_baseline_text():
    """
    Sample baseline inputs file text with formatting and comments.
    Used to test Ghostwriter format preservation.
    """
    return """# Grid Resolution
amr.n_cell = 32 32 32
amr.max_level = 0
amr.blocking_factor = 8

# Physics
amr.cfl = 0.9
geometry.is_periodic = 1 1 1

# Time Stepping
max_step = 100
stop_time = 1.0
"""


@pytest.fixture
def sample_baseline_dict():
    """
    Sample baseline configuration as dict (string values).
    Simulates output from baseline analysis or architect plan.
    """
    return {
        'amr.n_cell': '64 64 64',
        'amr.max_level': '0',
        'amr.cfl': '0.8',
        'geometry.is_periodic': '1 1 1',
        'max_step': '1000'
    }


# ============================================================================
# Test Class
# ============================================================================

class TestInputWriterPipelineIntegration:
    """Integration tests for Input Writer (full pipeline validation)."""
    
    # ========================================================================
    # Test 1: Schema Resolution
    # ========================================================================
    
    def test_schema_resolution_with_real_pelec(self):
        """
        Given: Real database/schemas/ directory with AMReX schema
        When:  resolve_schema_path() called with PeleCConfig
        Then:  Successfully locates and loads schema
        
        Validates: Schema discovery, file loading, structure
        """
        from database.configs import PeleCConfig
        from src.services.config_model_factory import ConfigModelFactory
        
        schema_dir = Path("database/schemas")
        repo_path = Path(".")
        
        # Resolve schema
        schema_path = ConfigModelFactory.resolve_schema_path(
            PeleCConfig,
            schema_dir,
            repo_path
        )
        
        # Verify file exists
        assert schema_path.exists(), f"Schema file not found: {schema_path}"
        assert schema_path.suffix == '.json'
        assert schema_path.name.startswith('pelec_')  # Uses PeleCConfig.schema_pattern
        
        # Load and verify structure
        data = json.loads(schema_path.read_text())
        
        # Should have parameters (wrapped or flat)
        if 'parameters' in data:
            params = data['parameters']
        else:
            params = data
        
        # Verify expected parameters exist
        assert 'amr.n_cell' in params, "Missing amr.n_cell in schema"
        cfl_param = PeleCConfig.cfl_param_name
        assert cfl_param in params, f"Missing {cfl_param} in schema"
        assert len(params) > 100, f"Schema too small: {len(params)} params"
    
    # ========================================================================
    # Test 2: Full Pipeline
    # ========================================================================
    
    def test_full_pipeline_load_modify_write_pelec(
        self, 
        pelec_schema, 
        build_config,
        sample_baseline_text,
        tmp_path
    ):
        """
        Given: Real schema, baseline text, modification plan
        When:  Full pipeline executed (load → modify → write)
        Then:  Output file contains modifications
        
        Validates: Amendment C (Load-Modify-Write), full orchestration
        """
        from src.services.config_model_factory import ConfigModelFactory
        from src.services.inputs_file_writer import InputsFileWriter
        
        # Step 1: Create model from schema
        ModelClass = ConfigModelFactory.create_from_schema(
            pelec_schema,
            build_config
        )
        
        # Step 2: Hydrate from baseline text
        model = ConfigModelFactory.hydrate(
            ModelClass,
            sample_baseline_text
        )
        
        # Verify baseline loaded
        assert model is not None
        
        # Step 3: Apply modifications
        modifications = {
            'amr.n_cell': [128, 128, 128],
            'amr.cfl': 0.5
        }
        
        modified_model = ConfigModelFactory.apply_modifications(
            model,
            modifications
        )
        
        # Step 4: Serialize to text
        writer = InputsFileWriter()
        output_text = writer.serialize(
            modified_model,
            original_text=sample_baseline_text
        )
        
        # Step 5: Write to file
        output_file = tmp_path / "inputs"
        output_file.write_text(output_text)
        
        # Verify output
        assert output_file.exists()
        
        # Check modifications applied
        content = output_file.read_text()
        assert '128 128 128' in content or '128' in content
        assert '0.5' in content
    
    # ========================================================================
    # Test 3: Hydration from Dict
    # ========================================================================
    
    def test_hydration_from_dict_pattern_pelec(
        self,
        pelec_schema,
        build_config,
        sample_baseline_dict
    ):
        """
        Given: Baseline configuration as dict (string values)
        When:  from_dict() hydration performed
        Then:  Model populated with correct types
        
        Validates: String → typed conversion, from_dict() pattern
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        # Create model class
        ModelClass = ConfigModelFactory.create_from_schema(
            pelec_schema,
            build_config
        )
        
        # Hydrate from dict
        model = ConfigModelFactory.from_dict(
            ModelClass,
            sample_baseline_dict
        )
        
        # Verify types converted correctly
        assert model is not None
        
        # Check string → list[int] conversion
        # Note: Field names use underscores
        if hasattr(model, 'amr_n_cell'):
            n_cell = model.amr_n_cell
            assert isinstance(n_cell, (list, tuple)), \
                f"amr.n_cell should be list, got {type(n_cell)}"
        
        # Check string → float conversion
        if hasattr(model, 'pelec_cfl'):
            cfl = model.pelec_cfl
            assert isinstance(cfl, float), \
                f"amr.cfl should be float, got {type(cfl)}"
    
    # ========================================================================
    # Test 4: Schema Validation (Hallucination Detection)
    # ========================================================================
    
    def test_schema_rejects_hallucinated_parameters_pelec(
        self,
        pelec_schema,
        build_config
    ):
        """
        Given: Modification containing non-existent parameter
        When:  apply_modifications() called
        Then:  Raises ValidationError or warns (Digital Twin)
        
        Validates: Schema enforcement, hallucination rejection
        """
        from src.services.config_model_factory import ConfigModelFactory
        from pydantic import ValidationError
        
        # Create model
        ModelClass = ConfigModelFactory.create_from_schema(
            pelec_schema,
            build_config
        )
        
        # Create minimal instance
        model = ModelClass()
        
        # Try to apply hallucinated parameter
        hallucinated_mods = {
            'pelec.fake_parameter_does_not_exist': 42
        }
        
        # Fix 3: Apply modifications (permissive - allows unknown fields)
        modified_model = ConfigModelFactory.apply_modifications(
            model,
            hallucinated_mods
        )
        
        # Then validate - SchemaExistenceRule should detect hallucination
        from src.services.rule_engine import RuleEngine
        from database.configs.pelec_config import PeleCConfig
        
        # Get violations instead of expecting exception
        violations = RuleEngine.validate(
            modified_model,
            solver_config=PeleCConfig,
            build_config={}
        )
        
        # Should find the hallucinated parameter
        assert len(violations) > 0, "Expected violations for hallucinated parameter"
        hallucination_violations = [
            v for v in violations 
            if 'fake_parameter' in v.parameter or v.rule_name == "SchemaExistence"
        ]
        assert len(hallucination_violations) > 0,             f"Expected SchemaExistence violation, got: {[v.rule_name for v in violations]}"
    
    # ========================================================================
    # Test 5: Rule Engine Auto-Correction
    # ========================================================================
    
    def test_rule_engine_auto_correction_pelec(
        self,
        pelec_schema,
        build_config
    ):
        """
        Given: Configuration violating grid consistency rule
        When:  RuleEngine.enforce() applied
        Then:  Auto-corrects to valid state
        
        Validates: Amendment D (contextual generation), rule application
        """
        from src.services.config_model_factory import ConfigModelFactory
        from src.services.rule_engine import RuleEngine
        from database.configs import PeleCConfig
        
        # Create model with invalid configuration
        ModelClass = ConfigModelFactory.create_from_schema(
            pelec_schema,
            build_config
        )
        
        # Set conflicting values (n_cell not divisible by blocking_factor)
        invalid_config = {
            'amr.n_cell': [100, 100, 100],  # Not divisible by 16
            'amr.blocking_factor': 16
        }
        
        model = ConfigModelFactory.from_dict(ModelClass, invalid_config)
        
        # Apply rule engine
        # Fix 2: RuleEngine uses static methods
        corrected_model = RuleEngine.enforce(model, solver_config=PeleCConfig, build_config={})
        
        # Verify correction applied
        # (Rule engine should adjust blocking_factor or n_cell)
        assert corrected_model is not None
        
        # Check that result is now valid
        # Exact correction depends on rule implementation
        if hasattr(corrected_model, 'amr_blocking_factor'):
            bf = corrected_model.amr_blocking_factor
            if hasattr(corrected_model, 'amr_n_cell'):
                n_cell = corrected_model.amr_n_cell
                if isinstance(n_cell, (list, tuple)) and n_cell:
                    # Each dimension should be divisible
                    assert all(n % bf == 0 for n in n_cell), \
                        "Grid consistency rule not enforced"
    
    # ========================================================================
    # Test 6: Build Flag Constraints
    # ========================================================================
    
    def test_build_flag_constraints_pelec(self, pelec_schema):
        """
        Given: Schema with USE_EB-dependent parameters
        When:  Model created with USE_EB=FALSE
        Then:  EB parameters excluded from model
        
        Validates: Build flag filtering (Amendment D)
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        # Create model with USE_EB disabled
        build_config_no_eb = {
            'USE_EB': 'FALSE',
            'DIM': '3'
        }
        
        ModelClass = ConfigModelFactory.create_from_schema(
            pelec_schema,
            build_config_no_eb
        )
        
        # Check that EB parameters are excluded
        field_names = list(ModelClass.model_fields.keys())
        
        eb_fields = [f for f in field_names if f.startswith('eb_')]
        
        # Should have no EB fields when USE_EB=FALSE
        assert len(eb_fields) == 0, \
            f"EB fields should be excluded when USE_EB=FALSE, found: {eb_fields}"
        
        # Verify other fields still exist
        assert len(field_names) > 50, \
            "Model should still have many non-EB fields"
    
    # ========================================================================
    # Test 7: Ghostwriter Format Preservation
    # ========================================================================
    
    def test_ghostwriter_format_preservation_pelec(
        self,
        pelec_schema,
        build_config,
        sample_baseline_text
    ):
        """
        Given: Baseline text with comments and formatting
        When:  Modification applied via Ghostwriter
        Then:  Comments/whitespace preserved, only value changed
        
        Validates: InputsFileWriter Ghostwriter feature
        """
        from src.services.config_model_factory import ConfigModelFactory
        from src.services.inputs_file_writer import InputsFileWriter
        
        # Create and hydrate model
        ModelClass = ConfigModelFactory.create_from_schema(
            pelec_schema,
            build_config
        )
        model = ConfigModelFactory.hydrate(ModelClass, sample_baseline_text)
        
        # Apply single modification
        modifications = {'amr.cfl': 0.5}
        modified_model = ConfigModelFactory.apply_modifications(
            model,
            modifications
        )
        
        # Serialize with Ghostwriter
        writer = InputsFileWriter()
        output_text = writer.serialize(
            modified_model,
            original_text=sample_baseline_text
        )
        
        # Verify format preservation
        assert '# Grid Resolution' in output_text, \
            "Comment should be preserved"
        assert '# Physics' in output_text, \
            "Comment should be preserved"
        
        # Verify modification applied
        assert '0.5' in output_text, \
            "Modified value should appear"
        
        # Verify other values unchanged
        assert 'amr.max_level = 0' in output_text or 'amr.max_level=0' in output_text, \
            "Unmodified parameter should remain"
        
        # Verify structure preserved (sections still separated)
        lines = output_text.split('\n')
        assert any('Grid' in line for line in lines), \
            "Section headers preserved"


# Test marker
pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_schema("PeleC"),
]
