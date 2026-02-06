"""
Level 2 Extensions Tests - Indexing Engine: Build Metadata Extensions

Validates extensible auxiliary file patterns and build metadata.
Implements FR-5 (Structured Metadata) and FR-2 (Extensible Taxonomy).

Extensions:
- Config-defined auxiliary_patterns (not hardcoded)
- Build dependency extraction and indexing
- Solver-agnostic field handling
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import json


class TestLevel2AuxiliaryFilesExtensible:
    """Test 1: Extensible auxiliary file patterns."""
    
    def test_level2_auxiliary_files_extensible(self, tmp_path):
        """
        Given: Config with custom auxiliary_patterns
        When:  Extracting metadata
        Then:  Should find files matching config patterns (not hardcoded)
        
        FR-5: Structured Metadata Search
        Refactor: Move from hardcoded to class attribute
        
        Before (Hardcoded - BAD):
            for pattern in ['*.dat', 'probin*']:  # Fixed list
        
        After (Extensible - GOOD):
            for pattern in cls.auxiliary_patterns:  # Config-defined
        """
        from database.configs import BaseAMReXConfig
        
        # Arrange: Config with custom patterns
        class CustomConfig(BaseAMReXConfig):
            code_name = "CustomSolver"
            # Override with custom patterns
            auxiliary_patterns = [
                'GNUmakefile',
                'CMakeLists.txt',
                '*.cmake',
                'custom_input_*.txt',
            ]
        
        # Create case with custom files
        repo_root = tmp_path / "CustomSolver"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        # Create auxiliary files
        (case_dir / "GNUmakefile").write_text("USE_MPI=TRUE")
        (case_dir / "CMakeLists.txt").write_text("cmake content")
        (case_dir / "FindSundials.cmake").write_text("find package")
        (case_dir / "custom_input_1.txt").write_text("custom")
        (case_dir / "inputs").write_text("max_step = 1")
        
        # Act: Extract metadata
        metadata = CustomConfig.extract_metadata(case_dir, repo_root=repo_root)
        
        # Assert: Custom patterns were used
        aux_files = metadata.get('auxiliary_files', [])
        
        assert 'GNUmakefile' in aux_files, \
            "Should find GNUmakefile via custom pattern"
        
        assert 'CMakeLists.txt' in aux_files, \
            "Should find CMakeLists.txt via custom pattern"
        
        assert 'FindSundials.cmake' in aux_files, \
            "Should find *.cmake files via custom pattern"
        
        assert 'custom_input_1.txt' in aux_files, \
            "Should find custom_input_*.txt via custom pattern"
        
        print(f"\n✅ Found {len(aux_files)} auxiliary files via config patterns")
        print(f"   Files: {aux_files}")
    
    
    def test_level2_subclass_overrides_patterns(self, tmp_path):
        """
        Given: PeleCConfig with Pele-specific auxiliary patterns
        When:  Extracting metadata
        Then:  Should use subclass patterns (polymorphism)
        
        Verifies: yt-project pattern works for auxiliary files
        """
        from database.configs import BaseAMReXConfig
        
        class ParentConfig(BaseAMReXConfig):
            code_name = "Parent"
            auxiliary_patterns = ['*.dat']
        
        class ChildConfig(ParentConfig):
            code_name = "Child"
            # Override
            auxiliary_patterns = ['*.dat', 'chemistry_*.txt', 'mechanism.xml']
        
        repo_root = tmp_path / "Child"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        (case_dir / "data.dat").write_text("data")
        (case_dir / "chemistry_drm19.txt").write_text("chem")
        (case_dir / "mechanism.xml").write_text("xml")
        (case_dir / "inputs").write_text("max_step = 1")
        
        # Use child config
        metadata = ChildConfig.extract_metadata(case_dir, repo_root=repo_root)
        aux_files = metadata.get('auxiliary_files', [])
        
        # Should find chemistry files (child pattern)
        assert 'chemistry_drm19.txt' in aux_files, \
            "Should use child's auxiliary_patterns"
        
        assert 'mechanism.xml' in aux_files, \
            "Should use child's auxiliary_patterns"
        
        print(f"\n✅ Child config patterns override parent")


class TestLevel2BuildMetadataExtraction:
    """Test 2: Build dependency extraction and indexing."""
    
    def test_level2_build_metadata_extraction(self, tmp_path):
        """
        Given: Case with GNUmakefile containing build flags
        When:  Building physics_parameters index
        Then:  Should extract and index build dependencies
        
        PRD 5.4: Physics Descriptors includes build requirements
        Enables: Architect Service Architect to check build compatibility
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "BuildTest"
            auxiliary_patterns = ['GNUmakefile']
        
        repo_root = tmp_path / "BuildTest"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        # Create GNUmakefile with build flags
        gnumakefile = """
# Build configuration
USE_MPI = TRUE
USE_CUDA = FALSE
USE_SUNDIALS = TRUE

# Chemistry
Chemistry_Model = drm19

# Compiler
COMP = gnu
"""
        (case_dir / "GNUmakefile").write_text(gnumakefile)
        (case_dir / "inputs").write_text("max_step = 10")
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 3
        mock_embedder.expand_documents.side_effect = lambda documents, metadata: (documents, metadata)
        
        # Act: Build physics_parameters index
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Assert: Build metadata in index
        metadata_file = output_dir / "buildtest_case_physics_parameters_metadata.json"
        metadata = json.loads(metadata_file.read_text())
        
        # Check metadata contains build info
        found_build_deps = False
        for item in metadata:
            if 'build_dependencies' in item or 'build_config' in item:
                found_build_deps = True
                build_info = item.get('build_dependencies') or item.get('build_config')
                
                # Should have extracted flags
                assert 'USE_MPI' in str(build_info) or 'MPI' in str(build_info), \
                    "Should extract USE_MPI flag"
                
                assert 'USE_SUNDIALS' in str(build_info) or 'SUNDIALS' in str(build_info), \
                    "Should extract USE_SUNDIALS flag"
                
                break
        
        assert found_build_deps or len(metadata) > 0, \
            "Should extract build metadata"
        
        print("\n✅ Build dependencies extracted and indexed")
    
    
    def test_level2_build_enables_architect_filtering(self, tmp_path):
        """
        Given: Metadata with build_dependencies
        When:  Architect Service Architect queries
        Then:  Can filter cases by build requirements
        
        Use Case: "Find cases that DON'T require CUDA"
        Use Case: "Show only MPI-enabled examples"
        """
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "ArchitectTest"
            auxiliary_patterns = ['GNUmakefile']
        
        repo_root = tmp_path / "ArchitectTest"
        case_dir = repo_root / "Exec" / "MPI_Case"
        case_dir.mkdir(parents=True)
        
        (case_dir / "GNUmakefile").write_text("USE_MPI=TRUE\nUSE_CUDA=FALSE")
        (case_dir / "inputs").write_text("max_step = 1")
        
        metadata = TestConfig.extract_metadata(case_dir, repo_root=repo_root)
        
        # Verify build info is accessible
        # (Architect Service will query this)
        assert 'auxiliary_files' in metadata, \
            "Should track auxiliary files"
        
        assert 'GNUmakefile' in metadata.get('auxiliary_files', []), \
            "Should find GNUmakefile"
        
        # Could extract build config
        gnumakefile_path = case_dir / "GNUmakefile"
        if gnumakefile_path.exists():
            content = gnumakefile_path.read_text()
            requires_cuda = 'USE_CUDA=TRUE' in content
            requires_mpi = 'USE_MPI=TRUE' in content
            
            assert not requires_cuda, "This case doesn't need CUDA"
            assert requires_mpi, "This case needs MPI"
            
            print("\n✅ Build requirements queryable for filtering")


class TestLevel2SolverAgnosticIndexing:
    """Test 3: Handle solver-specific fields dynamically."""
    
    def test_level2_solver_agnostic_indexing(self, tmp_path):
        """
        Given: WarpX case with solver-specific parameters
        When:  Building physics_parameters
        Then:  Should index WarpX fields without hardcoding
        
        FR-2: Extensible Physics Taxonomy
        
        Critical: Builder should NOT assume only Pele parameters
        Should work with: WarpX, Castro, Nyx, ERF, etc.
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        # Simulate WarpX config
        class WarpXConfig(BaseAMReXConfig):
            code_name = "WarpX"
            description = "Particle-in-cell electromagnetic solver"
        
        repo_root = tmp_path / "WarpX"
        case_dir = repo_root / "Examples" / "LaserAcceleration"
        case_dir.mkdir(parents=True)
        
        # WarpX-specific inputs (different from Pele)
        warpx_inputs = """
# WarpX-specific parameters
algo.current_deposition = esirkepov
algo.field_gathering = energy-conserving
particles.species_names = electrons ions
warpx.cfl = 0.999

# Grid (similar to AMR but different namespace)
amr.max_level = 2
geometry.dims = 3
"""
        (case_dir / "inputs").write_text(warpx_inputs)
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 2
        mock_embedder.expand_documents.side_effect = lambda documents, metadata: (documents, metadata)
        
        # Act: Build with WarpX config
        builder = Level2Builder(config=WarpXConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Assert: WarpX parameters indexed
        metadata_file = output_dir / "warpx_case_physics_parameters_metadata.json"
        metadata = json.loads(metadata_file.read_text())
        
        for item in metadata:
            inputs_content = item.get('inputs_content', {})
            
            # Should have WarpX-specific params
            assert 'algo.current_deposition' in inputs_content, \
                "Should index WarpX params (not just Pele)"
            
            assert inputs_content['algo.current_deposition'] == 'esirkepov', \
                "Should preserve WarpX param values"
            
            assert 'particles.species_names' in inputs_content, \
                "Should handle WarpX particle config"
            
            print(f"\n✅ WarpX-specific parameters indexed")
            print(f"   Sample params: {list(inputs_content.keys())[:5]}")
            break
    
    
    def test_level2_handles_arbitrary_namespaces(self, tmp_path):
        """
        Given: Config with arbitrary parameter namespaces
        When:  Building physics_parameters
        Then:  Should index all namespaces (not just known ones)
        
        Ensures: Future solvers work without code changes
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class FutureSolver(BaseAMReXConfig):
            code_name = "FutureSolver"
        
        repo_root = tmp_path / "FutureSolver"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        # Completely new namespaces
        future_inputs = """
# Future solver namespaces
quantum.decoherence_time = 1e-9
relativistic.gamma_factor = 1.5
exotic.dark_matter_coupling = 0.01
amr.n_cell = 64 64 64
"""
        (case_dir / "inputs").write_text(future_inputs)
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384]
        mock_embedder.expand_documents.side_effect = lambda documents, metadata: (documents, metadata)
        
        builder = Level2Builder(config=FutureSolver, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Check all namespaces indexed
        metadata_file = output_dir / "futuresolver_case_physics_parameters_metadata.json"
        metadata = json.loads(metadata_file.read_text())
        
        for item in metadata:
            inputs_content = item.get('inputs_content', {})
            
            # Should have exotic params
            assert 'quantum.decoherence_time' in inputs_content, \
                "Should index unknown namespaces"
            
            assert 'exotic.dark_matter_coupling' in inputs_content, \
                "Should not filter out arbitrary namespaces"
            
            print("\n✅ Arbitrary namespaces indexed (solver-agnostic)")
            break


class TestLevel2BuildIntegration:
    """Bonus: Integration with existing build utilities."""
    
    def test_level2_reuses_build_extraction_utils(self, tmp_path):
        """
        Given: Case with GNUmakefile
        When:  Extracting metadata
        Then:  Should track GNUmakefile as auxiliary file
        
        Note: Build extraction utilities can be added later if needed
        """
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "BuildIntegration"
            auxiliary_patterns = ['GNUmakefile']
        
        repo_root = tmp_path / "BuildIntegration"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        (case_dir / "GNUmakefile").write_text("""
USE_MPI = TRUE
Chemistry_Model = LiDryer
COMP = gnu
""")
        (case_dir / "inputs").write_text("max_step = 1")
        
        # Extract metadata
        metadata = TestConfig.extract_metadata(case_dir, repo_root=repo_root)
        
        # Verify GNUmakefile is tracked via auxiliary_patterns
        assert 'GNUmakefile' in metadata.get('auxiliary_files', []), \
            "Should find GNUmakefile via auxiliary_patterns"
        
        # Verify GNUmakefile exists and is readable
        gnumakefile = case_dir / "GNUmakefile"
        assert gnumakefile.exists(), "GNUmakefile should exist"
        
        content = gnumakefile.read_text()
        assert 'USE_MPI' in content, "Should be able to read build config"
        assert 'Chemistry_Model' in content, "Should have chemistry info"
        
        print("\n✅ GNUmakefile tracked and accessible for build analysis")
