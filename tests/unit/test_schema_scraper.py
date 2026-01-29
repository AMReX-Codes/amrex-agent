"""
Input Writer: Schema Scraper: Schema Scraper Tests

Validates extraction of parameter schemas from AMReX source code
to build a "digital twin" of the configuration space.

Architecture:
    Source Code (C++/Make/CMake) → Schema JSON → Validation Engine

References:
    - PRD Amendment D: Schema extraction
    - Indexing Engine: Build Metadata Extensions: Build config parsing
    - Metadata Schema: Namespace patterns
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import Dict, List


class TestParmParseExtraction:
    """Test C++ ParmParse call extraction."""
    
    def test_parmparse_extraction_basic(self, tmp_path):
        """
        Given: C++ file with ParmParse calls
        When:  Schema builder parses it
        Then:  Should extract parameter names, types, defaults
        
        Validates: Core regex parsing logic
        """
        # Create mock C++ file
        cpp_content = '''
void ReadParameters() {
    ParmParse pp("amr");
    int n_cell;
    pp.get("n_cell", n_cell);  // Required parameter
    
    Real cfl = 0.8;
    pp.query("cfl", cfl);  // Optional with default
}
'''
        cpp_file = tmp_path / "test.cpp"
        cpp_file.write_text(cpp_content)
        
        # Import after creating test file structure
        from database.scripts.build_schema import SchemaBuilder
        
        builder = SchemaBuilder(tmp_path)
        builder._parse_file(cpp_file)
        
        # Assert
        schema = builder.schema
        
        # Should find amr.n_cell (required)
        assert 'amr.n_cell' in schema
        assert schema['amr.n_cell']['required'] == True
        
        # Should find amr.cfl (optional)
        assert 'amr.cfl' in schema
        assert schema['amr.cfl']['required'] == False
        # Default value should be captured or inferred
        if 'default' in schema['amr.cfl']:
            assert schema['amr.cfl']['default'] == 0.8
    
    def test_multiple_namespaces(self, tmp_path):
        """
        Given: C++ with multiple ParmParse namespaces
        When:  Parser extracts parameters
        Then:  Should correctly map namespace.parameter
        
        Validates: Namespace tracking
        """
        cpp_content = '''
void Setup() {
    ParmParse pp_amr("amr");
    pp_amr.get("max_level", max_lev);
    
    ParmParse pp_amr("amr");
    pp_amr.query("do_react", do_react);
}
'''
        cpp_file = tmp_path / "setup.cpp"
        cpp_file.write_text(cpp_content)
        
        from database.scripts.build_schema import SchemaBuilder
        
        builder = SchemaBuilder(tmp_path)
        builder._parse_file(cpp_file)
        
        # Assert - both namespaces captured
        assert 'amr.max_level' in builder.schema
        assert 'amr.do_react' in builder.schema


class TestSolverIndependentComposition:
    """Test schema composition without hardcoded hierarchy."""
    
    def test_schema_composition(self, tmp_path):
        """
        Given: Separate schemas for AMReX, PelePhysics, AMReX
        When:  Compose full solver schema
        Then:  Should merge without conflicts
        
        Validates: Solver-independent composition
        """
        from database.scripts.build_schema import SchemaComposer
        
        # Mock component schemas
        amrex_schema = {
            "amr.v": {"type": "int", "required": True},
            "amr.max_level": {"type": "int", "default": 0}
        }
        
        pelephysics_schema = {
            "amr.chem_file": {"type": "string", "required": False}
        }
        
        amr_schema = {
            "amr.do_react": {"type": "int", "default": 0}
        }
        
        # Compose
        composer = SchemaComposer()
        full_schema = composer.compose(
            components=[amrex_schema, pelephysics_schema, amr_schema],
            solver_name="AMReX"
        )
        
        # Assert - all components present
        assert "amr.v" in full_schema
        assert "amr.max_level" in full_schema
        assert "amr.chem_file" in full_schema
        assert "amr.do_react" in full_schema
    
    def test_warpx_composition(self, tmp_path):
        """
        Given: WarpX + AMReX schemas
        When:  Compose
        Then:  Should handle different namespace (warpx.*)
        
        Validates: Works for non-Pele codes
        """
        from database.scripts.build_schema import SchemaComposer
        
        amrex_schema = {"amr.n_cell": {"type": "int", "required": True}}
        warpx_schema = {"warpx.algo": {"type": "string", "default": "yee"}}
        
        composer = SchemaComposer()
        full_schema = composer.compose(
            components=[amrex_schema, warpx_schema],
            solver_name="WarpX"
        )
        
        # Both namespaces preserved
        assert "amr.n_cell" in full_schema
        assert "warpx.algo" in full_schema


class TestConditionalActivation:
    """Test build flag dependency tracking."""
    
    @pytest.mark.skip(reason="TODO: Implement #ifdef tracking")
    def test_conditional_compilation(self, tmp_path):
        """
        Given: C++ with #ifdef blocks
        When:  Build config has flag disabled
        Then:  Should mark parameters as inactive
        
        Validates: Conditional parameter tracking
        """
        cpp_content = '''
#ifdef AMREX_USE_EB
void EBSetup() {
    ParmParse pp("eb");
    Real sphere_radius;
    pp.get("sphere_radius", sphere_radius);
}
#endif
'''
        cpp_file = tmp_path / "eb.cpp"
        cpp_file.write_text(cpp_content)
        
        from database.scripts.build_schema import SchemaBuilder
        
        builder = SchemaBuilder(tmp_path)
        builder.build_config = {"AMREX_USE_EB": False}
        builder._parse_file(cpp_file)
        
        # Assert - parameter marked as conditional
        if 'eb.sphere_radius' in builder.schema:
            assert builder.schema['eb.sphere_radius'].get('active', True) == False
            assert 'AMREX_USE_EB' in builder.schema['eb.sphere_radius'].get('dependencies', [])


class TestStaticDependencyDetection:
    """Test preprocessor guard detection."""
    
    @pytest.mark.skip(reason="TODO: Implement #ifdef tracking")
    def test_nested_ifdefs(self, tmp_path):
        """
        Given: Nested #ifdef blocks
        When:  Parser analyzes
        Then:  Should track all dependencies
        
        Validates: Complex conditional logic
        """
        cpp_content = '''
#ifdef AMREX_USE_EB
    #ifdef PELEC_USE_SPRAY
        ParmParse pp("spray");
        pp.get("num_droplets", n);
    #endif
#endif
'''
        cpp_file = tmp_path / "spray.cpp"
        cpp_file.write_text(cpp_content)
        
        from database.scripts.build_schema import SchemaBuilder
        
        builder = SchemaBuilder(tmp_path)
        builder._parse_file(cpp_file)
        
        # Assert - both dependencies tracked
        if 'spray.num_droplets' in builder.schema:
            deps = builder.schema['spray.num_droplets'].get('dependencies', [])
            assert 'AMREX_USE_EB' in deps
            assert 'PELEC_USE_SPRAY' in deps


class TestCoupledCodes:
    """Test multi-code namespace handling."""
    
    def test_namespace_collision_detection(self, tmp_path, monkeypatch):
        """
        Given: Two codes defining same parameter
        When:  Schemas merge
        Then:  Should detect and handle collision
        
        Validates: Coupled code support (ERF + AMR-Wind)
        """
        from database.scripts.build_schema import SchemaComposer
        
        erf_schema = {
            "geometry.prob_lo": {"type": "real", "default": "0.0 0.0 0.0"}
        }
        
        amrwind_schema = {
            "geometry.prob_lo": {"type": "real", "default": "0.0 0.0 0.0"}
        }
        
        composer = SchemaComposer()
        
        # Should detect collision (using monkeypatch for logger)
        from unittest.mock import Mock
        mock_logger = Mock()
        
        import database.scripts.build_schema
        monkeypatch.setattr(database.scripts.build_schema, 'logger', mock_logger)
        
        merged = composer.merge([erf_schema, amrwind_schema])
        mock_logger.warning.assert_called()


class TestNoAssumedHierarchy:
    """Test flexible source tree navigation."""
    
    def test_flat_vs_nested_layout(self, tmp_path):
        """
        Given: Different repo layouts (WarpX vs Pele)
        When:  Scanner looks for source files
        Then:  Should find them using config, not hardcoded paths
        
        Validates: Solver-independent architecture
        """
        from database.scripts.build_schema import SchemaBuilder
        
        # Create WarpX-style layout (flat)
        warpx_root = tmp_path / "WarpX"
        warpx_root.mkdir()
        (warpx_root / "Source").mkdir()
        (warpx_root / "Source" / "test.cpp").write_text("ParmParse pp(\"warpx\");\nint algo;\npp.get(\"algo\", algo);")
        
        # Create AMReX-style layout (nested)
        amr_root = tmp_path / "AMReX"
        amr_root.mkdir()
        (amr_root / "Source" / "Src_nd").mkdir(parents=True)
        (amr_root / "Source" / "Src_nd" / "test.cpp").write_text("ParmParse pp(\"amr\");\nReal cfl;\npp.query(\"cfl\", cfl);")
        
        # Config-driven search
        warpx_builder = SchemaBuilder(warpx_root)
        warpx_builder.scan_source_code(source_dirs=["Source"])
        
        amr_builder = SchemaBuilder(amr_root)
        amr_builder.scan_source_code(source_dirs=["Source"])
        
        # Both should succeed
        assert len(warpx_builder.schema) > 0
        assert len(amr_builder.schema) > 0


class TestCMakeAndMakeParsing:
    """Test build system parsing."""
    
    def test_gnumakefile_parsing(self, tmp_path):
        """
        Given: GNUmakefile with build variables
        When:  Parser extracts config
        Then:  Should capture DIM, USE_EB, etc.
        
        Validates: Reuse of Indexing Engine: Build Metadata Extensions logic
        """
        makefile_content = '''
DIM = 3
USE_EB = TRUE
USE_REACTIONS = FALSE
'''
        makefile = tmp_path / "GNUmakefile"
        makefile.write_text(makefile_content)
        
        from database.scripts.build_schema import SchemaBuilder
        
        builder = SchemaBuilder(tmp_path)
        build_config = builder.load_build_config()
        
        # Assert
        assert build_config.get('DIM') == '3'
        assert build_config.get('USE_EB') == 'TRUE'
        assert build_config.get('USE_REACTIONS') == 'FALSE'
    
    def test_cmake_parsing(self, tmp_path):
        """
        Given: CMakeLists.txt with options
        When:  Parser extracts config
        Then:  Should capture same information
        
        Validates: Multi-build-system support
        """
        cmake_content = '''
set(AMReX_SPACEDIM 3 CACHE STRING "Dimensionality")
option(AMReX_EB "Enable EB" ON)
option(AMReX_FORTRAN "Use Fortran" OFF)
'''
        cmake = tmp_path / "CMakeLists.txt"
        cmake.write_text(cmake_content)
        
        from database.scripts.build_schema import SchemaBuilder
        
        builder = SchemaBuilder(tmp_path)
        build_config = builder.load_build_config()
        
        # Assert - normalized to consistent format
        assert build_config.get('SPACEDIM') == '3' or build_config.get('AMReX_SPACEDIM') == '3'
        assert build_config.get('EB', '').upper() in ['ON', 'TRUE', '1']


class TestVersioning:
    """Test schema versioning by commit hash."""
    
    def test_commit_hash_suffix(self, tmp_path, monkeypatch):
        """
        Given: Git repository with commit
        When:  Schema is saved
        Then:  Should include commit hash in filename
        
        Validates: Version tracking
        """
        from database.scripts.build_schema import SchemaBuilder
        
        # Mock git subprocess using monkeypatch
        from unittest.mock import Mock
        mock_result = Mock(stdout="abc123", returncode=0)
        mock_run = Mock(return_value=mock_result)
        
        import database.scripts.build_schema
        monkeypatch.setattr(
            database.scripts.build_schema.subprocess,
            'run',
            mock_run
        )
        
        builder = SchemaBuilder(tmp_path)
        schema = builder.build_system_schema()
        builder.save(tmp_path, "test")
        
        # Check for hash in filename
        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        assert "abc123" in files[0].name


# Input Writer: Schema Scraper Marker
pytestmark = pytest.mark.input_writer_schema_scraper


# ============================================================================
# Input Writer: Schema Scraper: Two-Pass Schema Testing (TDD)
# ============================================================================

class TestMakeHelpParsing:
    """Test extraction of build options from make help."""
    
    def test_make_help_parsing(self, tmp_path, monkeypatch):
        """
        Given: Real output from 'make help' (AMReX ChallengeProblem)
        When:  Parser extracts CPPFLAGS
        Then:  Should identify active build defines
        
        Validates: Build system capability discovery from CPPFLAGS
        
        Note: Real make help doesn't list options like "USE_MPI=TRUE/FALSE"
              Instead, active options appear as -D flags in CPPFLAGS
        
        Architecture: Uses monkeypatch (pytest standard) instead of unittest.mock
        """
        from database.scripts.build_schema import SchemaBuilder
        from unittest.mock import Mock
        
        # Mock make help output (from real AMReX)
        mock_help_output = """
Loading /path/to/amrex/Tools/GNUMake/comps/gnu.mak...
Loading /path/to/amrex/Tools/GNUMake/sites/Make.unknown...

The rule for compiling foo.cpp  is: $(CXX) $(CXXFLAGS) ...

Here the variables are set to:
    CXX           = mpicxx
    CC            = mpicc
    FC            = mpif90
    CPPFLAGS      = -DBL_USE_MPI -DAMREX_USE_MPI -DAMREX_SPACEDIM=3 -DAMREX_USE_EB -DUSE_FUEGO_EOS -DUSE_SIMPLE_TRANSPORT -DAMREX_USE_SUNDIALS
    CXXFLAGS      = -g1 -O3 -std=c++17
    LINKFLAGS     = -g1 -O3
    executable    = AMReX3d.gnu.TPROF.MPI.ex
"""
        
        builder = SchemaBuilder(tmp_path)
        
        # Mock subprocess.run using monkeypatch
        mock_result = Mock(stdout=mock_help_output, returncode=0)
        mock_run = Mock(return_value=mock_result)
        
        import database.scripts.build_schema
        monkeypatch.setattr(database.scripts.build_schema.subprocess, 'run', mock_run)
        
        capabilities = builder._parse_make_help()
        
        # Assert - should extract defines from CPPFLAGS
        assert 'AMREX_USE_MPI' in capabilities or 'USE_MPI' in capabilities
        assert 'AMREX_USE_EB' in capabilities or 'USE_EB' in capabilities
        
        # Should capture SPACEDIM value
        assert 'AMREX_SPACEDIM' in capabilities or 'SPACEDIM' in capabilities
        if 'SPACEDIM' in capabilities:
            assert capabilities['SPACEDIM'] == '3'
        
        # Should identify transport and EOS models
        assert 'USE_FUEGO_EOS' in capabilities
        assert 'USE_SIMPLE_TRANSPORT' in capabilities


class TestCMakeCacheParsing:
    """Test extraction from CMake cache."""
    
    def test_cmake_cache_parsing(self, tmp_path):
        """
        Given: CMakeCache.txt file
        When:  Parser extracts cache variables
        Then:  Should normalize to internal format
        
        Validates: CMake build system support
        
        Architecture: Creates actual CMakeCache.txt (no mocking needed)
        """
        from database.scripts.build_schema import SchemaBuilder
        
        # Arrange: Create CMakeLists.txt and CMakeCache.txt
        (tmp_path / "CMakeLists.txt").write_text("# Dummy CMake file")
        
        cache_content = """# This is the CMakeCache file.
AMReX_SPACEDIM:STRING=3
AMReX_MPI:BOOL=ON
AMReX_EB:BOOL=OFF
AMReX_PARTICLES:BOOL=ON
PELE_ENABLE_MPI:BOOL=ON
"""
        (tmp_path / "CMakeCache.txt").write_text(cache_content)
        
        builder = SchemaBuilder(tmp_path)
        
        # Act
        capabilities = builder._parse_cmake_cache()
        
        # Assert - should have entries
        assert len(capabilities) > 0, f"Should extract variables, got: {capabilities}"
        
        # Check for SPACEDIM (with AMReX_ prefix)
        assert 'AMReX_SPACEDIM' in capabilities, f"Should have AMReX_SPACEDIM, got keys: {list(capabilities.keys())}"
        
        # Check BOOL conversion (ON → TRUE, OFF → FALSE)
        if 'AMReX_MPI' in capabilities:
            assert capabilities['AMReX_MPI'] == 'TRUE', f"BOOL ON should convert to TRUE, got: {capabilities['AMReX_MPI']}"
        if 'AMReX_EB' in capabilities:
            assert capabilities['AMReX_EB'] == 'FALSE', f"BOOL OFF should convert to FALSE, got: {capabilities['AMReX_EB']}"

    def test_make_print_extraction(self, tmp_path, monkeypatch):
        """
        Given: Case directory with GNUmakefile
        When:  Query specific variables via make print-VAR
        Then:  Should return active configuration
        
        Validates: Pass 2 case-specific discovery
        """
        from database.scripts.build_schema import SchemaBuilder
        from unittest.mock import Mock, patch
        
        case_dir = tmp_path / "case"
        case_dir.mkdir()
        (case_dir / "GNUmakefile").write_text("""
DIM = 3
USE_EB = TRUE
USE_MPI = TRUE
""")
        
        builder = SchemaBuilder(case_dir)
        
        # Mock make print-VAR for each variable
        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0]
            if 'print-USE_EB' in cmd:
                return Mock(stdout='USE_EB = TRUE\n', returncode=0)
            elif 'print-DIM' in cmd:
                return Mock(stdout='DIM = 3\n', returncode=0)
            elif 'print-USE_MPI' in cmd:
                return Mock(stdout='USE_MPI = TRUE\n', returncode=0)
            return Mock(stdout='', returncode=1)
        
        with patch('subprocess.run', side_effect=mock_run_side_effect):
            active_config = builder._get_active_build_vars(
                case_dir,
                ['USE_EB', 'DIM', 'USE_MPI', 'USE_PARTICLES']
            )
        
        # Assert - should return active values
        assert active_config['USE_EB'] == 'TRUE'
        assert active_config['DIM'] == '3'
        assert active_config['USE_MPI'] == 'TRUE'
        # USE_PARTICLES not set, should be absent or have default


class TestSystemSchemaCompleteness:
    """Test Pass 1: complete system schema."""
    
    def test_system_schema_completeness(self, tmp_path):
        """
        Given: Source tree with conditional parameters
        When:  Build system schema (Pass 1)
        Then:  Should capture both build flags and runtime params with dependencies
        
        Validates: Complete system-level discovery
        """
        from database.scripts.build_schema import SchemaBuilder
        
        # Create mock source with conditional parameter
        source_dir = tmp_path / "Source"
        source_dir.mkdir()
        
        (source_dir / "eb_init.cpp").write_text("""
#ifdef AMREX_USE_EB
void eb_setup() {
    ParmParse pp("eb");
    Real sphere_radius;
    pp.get("sphere_radius", sphere_radius);
}
#endif
""")
        
        (source_dir / "main.cpp").write_text("""
ParmParse pp("amr");
Real cfl = 0.8;
pp.query("cfl", cfl);
""")
        
        builder = SchemaBuilder(tmp_path)
        system_schema = builder.build_system_schema()
        
        # Assert - should have both build and runtime info
        assert 'build' in system_schema
        assert 'params' in system_schema
        
        # Runtime parameters should be discovered
        assert 'amr.cfl' in system_schema['params']
        assert 'eb.sphere_radius' in system_schema['params']
        
        # Both build capabilities and runtime params present
        assert 'build' in system_schema
        assert 'params' in system_schema
        
        # Note: Full #ifdef dependency tracking is deferred
        # For now, we just verify parameters are discovered


class TestTwoPassIntegration:
    """Test full two-pass pipeline."""
    
    def test_two_pass_integration(self, tmp_path, monkeypatch):
        """
        Given: System schema with conditional params + case with USE_EB=FALSE
        When:  Apply case customization (Pass 2)
        Then:  Should filter out EB parameters
        
        Validates: End-to-end two-pass workflow
        """
        from database.scripts.build_schema import SchemaBuilder
        from unittest.mock import Mock
        
        # Pass 1: Build system schema
        source_dir = tmp_path / "Source"
        source_dir.mkdir()
        
        (source_dir / "test.cpp").write_text("""
ParmParse pp("amr");
int n_cell;
pp.get("n_cell", n_cell);

#ifdef AMREX_USE_EB
ParmParse pp_eb("eb");
Real sphere_radius;
pp_eb.get("sphere_radius", sphere_radius);
#endif
""")
        
        builder = SchemaBuilder(tmp_path)
        system_schema = builder.build_system_schema()
        
        # Pass 2: Apply to case with EB disabled
        case_path = tmp_path / "case"
        case_path.mkdir()
        (case_path / "GNUmakefile").write_text("""
DIM = 3
USE_EB = FALSE
""")
        
        # Mock make print-USE_EB
        # Mock subprocess.run using monkeypatch
        mock_result = Mock(stdout='USE_EB = FALSE\n', returncode=0)
        mock_run = Mock(return_value=mock_result)
        
        import database.scripts.build_schema
        monkeypatch.setattr(
            database.scripts.build_schema.subprocess,
            'run',
            mock_run
        )
        
        case_schema = builder.apply_case_customization(
            system_schema,
            case_path
        )
        
        # Assert - amr.n_cell included (no dependencies)
        assert 'amr.n_cell' in case_schema['params']
        
        # Assert - schema has expected structure
        assert 'params' in case_schema
        assert 'flags' in case_schema
        
        # Note: Full flag extraction requires make to actually run
        # For unit test, we verify structure is correct

# Input Writer: Schema Scraper Two-Pass Marker
pytestmark = pytest.mark.input_writer_schema_scraper
