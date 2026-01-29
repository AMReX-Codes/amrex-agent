"""
Input Writer: Schema Composition: Schema Composition Tests

Validates:
1. Merging AMReX base + Solver schemas
2. C++ type detection (int, Real, IntVect)
3. Build flag detection (#ifdef USE_EB)
4. Nested namespace handling

Reference: Development Plan v6.0, Amendment D
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, Any

# Import Input Writer: Schema Scraper classes
from database.scripts.build_schema import SchemaBuilder, SchemaComposer


class TestSchemaComposition:
    """Tests for merging multiple schemas into a single solver schema."""

    def test_amrex_solver_composition(self):
        """
        Given: amrex_schema.json + solver_schema.json
        When: SchemaComposer.compose() is called
        Then: Merged schema contains both sets, solver overrides base
        
        Validates: Amendment D - solver-specific overrides
        """
        # Arrange
        amrex_schema = {
            "amr.n_cell": {"type": "int", "required": True, "source": "amrex"},
            "amr.v": {"type": "int", "default": 1, "source": "amrex"}
        }
        solver_schema = {
            "amr.cfl": {"type": "Real", "required": True, "source": "solver"},
            # Override an AMReX param (unlikely in practice, but tests logic)
            "amr.v": {"type": "int", "default": 2, "source": "solver_override"}
        }

        composer = SchemaComposer()

        # Act
        # Note: compose takes a list of schemas. Last one has highest priority.
        merged = composer.compose([amrex_schema, solver_schema], solver_name="AMReX")

        # Assert
        assert "amr.n_cell" in merged, "AMReX base parameters should be included"
        assert "amr.cfl" in merged, "Solver-specific parameters should be included"
        
        # Verify override (Solver takes precedence over Base)
        assert merged["amr.v"]["source"] == "solver_override", \
            "Solver schema should override base schema for conflicting params"
        assert merged["amr.v"]["default"] == 2


class TestTypeDetection:
    """Tests for inferring types from C++ variable declarations."""

    def test_type_detection_from_parmparse(self, tmp_path):
        """
        Given: C++ code with typed ParmParse calls
        When: SchemaBuilder parses file
        Then: Schema marks param with correct type (IntVect, Real, int)
        
        Validates: Type inference from variable declarations
        """
        # Arrange
        cpp_content = """
void Setup() {
    ParmParse pp("amr");
    
    // Integer detection
    int max_level;
    pp.get("max_level", max_level);
    
    // Real detection
    Real cfl = 0.8;
    pp.query("cfl", cfl);
    
    // Vector detection
    IntVect n_cell;
    pp.get("n_cell", n_cell);
    
    // String detection
    std::string plot_file;
    pp.query("plot_file", plot_file);
}
"""
        cpp_file = tmp_path / "type_test.cpp"
        cpp_file.write_text(cpp_content)

        builder = SchemaBuilder(tmp_path)

        # Act
        builder._parse_file(cpp_file)

        # Assert
        schema = builder.schema
        
        assert "amr.max_level" in schema, "Should detect int parameter"
        assert schema["amr.max_level"]["type"] == "int"
        
        assert "amr.cfl" in schema, "Should detect Real parameter"
        assert schema["amr.cfl"]["type"] == "Real"
        
        assert "amr.n_cell" in schema, "Should detect IntVect parameter"
        assert schema["amr.n_cell"]["type"] == "IntVect"
        
        assert "amr.plot_file" in schema, "Should detect string parameter"
        assert schema["amr.plot_file"]["type"] in ["std::string", "string"]


class TestBuildFlagDetection:
    """Tests for #ifdef logic gates."""

    def test_build_flag_detection(self, tmp_path):
        """
        Given: C++ with #ifdef USE_EB around pp.query
        When: SchemaBuilder parses file
        Then: Schema marks param with build_flags: ["USE_EB"]
        
        Validates: Conditional compilation tracking
        """
        # Arrange
        cpp_content = """
void EBSetup() {
    ParmParse pp("eb2");
    
    #ifdef AMREX_USE_EB
    Real sphere_radius;
    pp.query("sphere_radius", sphere_radius);
    #endif
    
    int geom_type;
    pp.get("geom_type", geom_type); // Outside ifdef
}
"""
        cpp_file = tmp_path / "eb_test.cpp"
        cpp_file.write_text(cpp_content)

        builder = SchemaBuilder(tmp_path)

        # Act
        builder._parse_file(cpp_file)

        # Assert
        # Inside ifdef
        assert "eb2.sphere_radius" in builder.schema
        flags = builder.schema["eb2.sphere_radius"].get("build_flags", [])
        # Should normalize AMREX_USE_EB -> USE_EB
        assert "USE_EB" in flags or "AMREX_USE_EB" in flags, \
            "Parameters inside #ifdef should have build_flags"

        # Outside ifdef
        assert "eb2.geom_type" in builder.schema
        geom_flags = builder.schema["eb2.geom_type"].get("build_flags", [])
        assert len(geom_flags) == 0, \
            "Parameters outside #ifdef should not have build_flags"


class TestMultilevelNamespaces:
    """Tests for complex namespace parsing (e.g. refinement_criteria)."""

    def test_multilevel_namespace_parameters(self, tmp_path):
        """
        Given: C++ with nested ParmParse calls
        When: SchemaBuilder parses file
        Then: Schema creates nested structure flattened with dots
        
        Validates: Multilevel namespace handling (refinement_criteria.density.err_low)
        """
        # Arrange
        cpp_content = """
void Tagging() {
    ParmParse pp("refinement_criteria");
    
    // Nested string in constructor
    ParmParse pp_dens("refinement_criteria.density");
    Real err_low;
    pp_dens.query("err_low", err_low);
    
    // Dot notation in query
    Real err_high;
    pp.query("density.err_high", err_high);
}
"""
        cpp_file = tmp_path / "tagging.cpp"
        cpp_file.write_text(cpp_content)

        builder = SchemaBuilder(tmp_path)

        # Act
        builder._parse_file(cpp_file)

        # Assert
        # Check normalization of keys
        assert "refinement_criteria.density.err_low" in builder.schema, \
            "Should create flattened multilevel namespace"
        assert "refinement_criteria.density.err_high" in builder.schema, \
            "Should handle dot notation in query calls"


class TestIntegration:
    """Integration tests connecting Schema to Config Factory."""

    def test_composed_schema_integration(self):
        """
        Given: Composed schema (AMReX + AMReX)
        When: ConfigModelFactory.create_from_schema()
        Then: Factory creates model with both AMReX + solver fields
        
        Validates: End-to-end composition → model creation
        """
        from src.services.config_model_factory import ConfigModelFactory

        # Arrange
        composed_schema = {
            "amr.n_cell": {"type": "IntVect", "required": True},
            "amr.cfl": {"type": "Real", "required": False, "default": 0.8}
        }
        
        # Act
        ModelClass = ConfigModelFactory.create_from_schema(
            composed_schema,
            build_config={'DIM': '3'}
        )
        
        # Assert
        # Verify aliasing works (dot -> underscore)
        assert "amr_n_cell" in ModelClass.model_fields, \
            "AMReX parameters should be present"
        assert "amr_cfl" in ModelClass.model_fields, \
            "Solver parameters should be present"
        
        # Verify types mapped correctly
        n_cell_type = str(ModelClass.model_fields["amr_n_cell"].annotation).lower()
        assert "list" in n_cell_type, \
            "IntVect should map to List[int]"

    def test_multilevel_param_roundtrip(self):
        """
        Given: Nested param written then read
        When: Load -> Modify -> Write
        Then: Value preserved, structure intact
        
        Validates: Multilevel parameter roundtrip through pipeline
        """
        from src.services.config_model_factory import ConfigModelFactory
        from src.services.inputs_file_writer import InputsFileWriter

        # Arrange
        schema = {
            "refinement_criteria.density.err_low": {
                "type": "Real",
                "required": True
            }
        }
        ModelClass = ConfigModelFactory.create_from_schema(schema, {})
        
        # Act 1: Hydrate from dict
        input_data = {"refinement_criteria.density.err_low": 0.01}
        model = ConfigModelFactory.from_dict(ModelClass, input_data)
        
        # Assert model attribute (dots replaced by underscores)
        assert hasattr(model, "refinement_criteria_density_err_low"), \
            "Model should have flattened field name"
        assert model.refinement_criteria_density_err_low == 0.01
        
        # Act 2: Serialize
        writer = InputsFileWriter()
        output_text = writer.serialize(model)
        
        # Assert output format (dots preserved via alias)
        assert "refinement_criteria.density.err_low" in output_text, \
            "Serialization should preserve dot notation"


# Test marker
pytestmark = pytest.mark.input_writer_schema_composition
