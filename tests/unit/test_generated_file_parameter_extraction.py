"""
Input Writer: Schema Scraper Enhancement: Generated File Parameter Extraction

Validates that SchemaBuilder correctly extracts parameters from
solver-specific generated C++ files (e.g., PeleC's _cpp_parameters).

Architecture:
    Config-driven source discovery → No hardcoded paths
    
References:
    - Amendment D.1: Source Code Truth
    - Cases Service: Config-Driven Discovery: Config-driven architecture
    - PeleCConfig.schema_source_patterns
"""

import pytest
from pathlib import Path
from typing import Dict, Any

from database.scripts.build_schema import SchemaBuilder
from database.configs.pelec_config import PeleCConfig


class TestGeneratedFileExtraction:
    """Test extraction from solver-specific generated files."""
    
    @pytest.fixture
    def mock_pelec_repo(self, tmp_path) -> Path:
        """
        Create mock PeleC repository matching real structure.

        Real PeleC structure:
        PeleC/
        ├── Source/
        │   ├── PeleC.cpp
        │   └── Params/
        │       └── _cpp_parameters  (definition file, not directory)
        """
        repo = tmp_path / "PeleC"
        repo.mkdir()

        # Standard source file (manual)
        source_dir = repo / "Source"
        source_dir.mkdir()
        (source_dir / "PeleC.cpp").write_text("""
void PeleC::readParameters() {
    ParmParse pp("pelec");

    // Conservative default from code comments
    Real cfl = 0.8;
    pp.query("cfl", cfl);
}
""")

        # Generated parameter definition file (matches real PeleC)
        params_dir = source_dir / "Params"
        params_dir.mkdir()
        (params_dir / "_cpp_parameters").write_text("""
@namespace: pelec PeleC static

# Reference temperature (generated from mechanism)
ref_temp    Real    298.15

# Small temperature cutoff  
small_temp  Real    200.0

# CFL number (from stability analysis - overrides manual default)
cfl         Real    0.5
""")

        return repo

    
    @pytest.fixture
    def pelec_config(self) -> PeleCConfig:
        """PeleC config with extended source patterns."""
        return PeleCConfig()
    
    def test_config_includes_generated_patterns(self, pelec_config):
        """
        Given: PeleCConfig class
        When:  Inspecting schema_source_patterns
        Then:  Should include _cpp_parameters pattern
        
        Validates: Config-driven source discovery
        """
        patterns = pelec_config.schema_source_patterns
        
        assert any("_cpp_parameters" in p for p in patterns), \
            "PeleCConfig must include _cpp_parameters pattern"
    
    def test_extracts_generated_parameters(self, mock_pelec_repo, pelec_config):
        """
        Given: PeleC repo with _cpp_parameters/pelec_params.cpp
        When:  SchemaBuilder scans with PeleCConfig patterns
        Then:  Should extract ref_temp and small_temp from generated file
        
        Validates: Amendment D.1 - Capture generated parameters
        """
        builder = SchemaBuilder(mock_pelec_repo)
        builder.scan_source_code(pelec_config.schema_source_patterns)
        
        schema = builder.schema
        
        # Parameters from generated file
        assert "pelec.ref_temp" in schema
        assert schema["pelec.ref_temp"]["default"] == 298.15
        assert schema["pelec.ref_temp"]["type"] == "Real"
        
        assert "pelec.small_temp" in schema
        assert schema["pelec.small_temp"]["default"] == 200.0
    
    def test_generated_file_takes_precedence(self, mock_pelec_repo, pelec_config):
        """
        Given: Parameter 'cfl' defined in BOTH Source/ and _cpp_parameters/
        When:  SchemaBuilder resolves conflict
        Then:  Generated file value (0.5) takes precedence over manual (0.8)
        
        Validates: Amendment D - Source Code Truth principle
        """
        builder = SchemaBuilder(mock_pelec_repo)
        builder.scan_source_code(pelec_config.schema_source_patterns)
        
        schema = builder.schema
        
        # Generated value (0.5) should win over manual (0.8)
        assert schema["pelec.cfl"]["default"] == 0.5, \
            "Generated default must override manual code comments"
        
        # Should tag the source type
        assert schema["pelec.cfl"]["source_type"] == "generated"
    
    def test_source_type_tagging(self, mock_pelec_repo, pelec_config):
        """
        Given: Parameters from different source files
        When:  Schema is built
        Then:  Each parameter tagged with source_type (manual vs generated)
        
        Validates: Provenance tracking for debugging
        """
        builder = SchemaBuilder(mock_pelec_repo)
        builder.scan_source_code(pelec_config.schema_source_patterns)
        
        schema = builder.schema
        
        # Parameters from generated file
        assert schema["pelec.ref_temp"]["source_type"] == "generated"
        assert "_cpp_parameters" in schema["pelec.ref_temp"]["source_file"]
        
        # Would also check manual params if they existed without conflicts
    
    def test_handles_missing_generated_dir(self, tmp_path, pelec_config):
        """
        Given: PeleC repo WITHOUT _cpp_parameters (pre-build state)
        When:  SchemaBuilder scans
        Then:  Should not crash, extract only from Source/
        
        Validates: Graceful degradation
        """
        repo = tmp_path / "PeleC_minimal"
        repo.mkdir()
        
        source_dir = repo / "Source"
        source_dir.mkdir()
        (source_dir / "PeleC.cpp").write_text("""
void PeleC::readParameters() {
    ParmParse pp("pelec");
    Real cfl = 0.8;
    pp.query("cfl", cfl);
}
""")
        
        # No _cpp_parameters directory exists
        builder = SchemaBuilder(repo)
        builder.scan_source_code(pelec_config.schema_source_patterns)
        
        schema = builder.schema
        
        # Should still get manual parameter
        assert "pelec.cfl" in schema
        assert schema["pelec.cfl"]["source_type"] == "manual"


class TestCrossSolverGeneratedFiles:
    """Test that other solvers handle their specific patterns."""
    
    def test_amrwind_no_generated_files(self, tmp_path):
        """
        Given: AMR-Wind which doesn't use _cpp_parameters
        When:  Using IncfloConfig patterns
        Then:  Should only scan Source/ (no crash on missing _cpp_parameters)
        
        Validates: Config-driven flexibility
        """
        from database.configs.incflo_config import IncfloConfig
        
        repo = tmp_path / "amr-wind"
        repo.mkdir()
        
        source_dir = repo / "Source"
        source_dir.mkdir()
        (source_dir / "incflo.cpp").write_text("""
void incflo::ReadParameters() {
    ParmParse pp("incflo");
    Real cfl = 0.7;
    pp.query("cfl", cfl);
}
""")
        
        config = IncfloConfig()
        builder = SchemaBuilder(repo)
        builder.scan_source_code(config.schema_source_patterns)
        
        schema = builder.schema
        assert "incflo.cfl" in schema
        # Should not fail due to missing _cpp_parameters
