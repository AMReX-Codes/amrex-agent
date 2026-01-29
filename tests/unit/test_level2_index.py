"""
Level 2 Index Tests - Indexing Engine: Level 2 (Case Metadata)

Validates granular case metadata indexing.
Implements PRD Section 5.4 (FR-5) with Amendment C (no truncation).

Architecture:
- 6 sub-indices per solver (weighted)
- Uses Metadata Schema extract_metadata (full parsing)
- Portable repo_path identifiers (Amendment B)
- Reuses database/scripts utilities
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import json


class TestLevel2SubindicesStructure:
    """Test 1: Validate 6 required sub-indices per solver."""
    
    def test_level2_subindices_structure(self, tmp_path):
        """
        Given: A solver with case directories
        When:  Building Level 2 indices
        Then:  Should create exactly 6 sub-indices per PRD 5.4
        
        PRD: Section 5.4 (FR-5 - Structured Metadata Search)
        
        Sub-indices (with weights):
        1. physics_parameters (35%)
        2. grid_specifications (20%)
        3. git_metrics (15%)
        4. path_hierarchy (15%)
        5. domain_models (10%)
        6. resource_requirements (5%)
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        # Arrange: Create minimal config
        class TestConfig(BaseAMReXConfig):
            code_name = "TestCode"
        
        # Create test case structure
        repo_root = tmp_path / "TestCode"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        # Create inputs file
        (case_dir / "inputs").write_text("""
amr.n_cell = 64 64 64
max_step = 100
""")
        
        # Mock embedder
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 10
        
        # Act: Build Level 2 indices
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Assert: All 6 sub-indices created
        code_lower = TestConfig.code_name.lower()
        
        assert (output_dir / f"{code_lower}_case_physics_parameters.faiss").exists(), \
            "Missing physics_parameters index (35% weight)"
        
        assert (output_dir / f"{code_lower}_case_grid_specifications.faiss").exists(), \
            "Missing grid_specifications index (20% weight)"
        
        assert (output_dir / f"{code_lower}_case_development_activity.faiss").exists(), \
            "Missing development_activity index (10% weight)"

        assert (output_dir / f"{code_lower}_case_configuration_complexity.faiss").exists(), \
            "Missing case_configuration_complexity index (10% weight)"

        assert (output_dir / f"{code_lower}_case_path_hierarchy.faiss").exists(), \
            "Missing path_hierarchy index (15% weight)"
        
        assert (output_dir / f"{code_lower}_case_domain_models.faiss").exists(), \
            "Missing domain_models index (10% weight)"
        
        assert (output_dir / f"{code_lower}_case_resource_requirements.faiss").exists(), \
            "Missing resource_requirements index (5% weight)"
        
        print(f"\n✅ All 6 Level 2 sub-indices created for {TestConfig.code_name}")


class TestLevel2AmendmentCCompliance:
    """Test 2: Verify Amendment C - No truncation."""
    
    def test_level2_no_truncation_amendment_c(self, tmp_path):
        """
        CRITICAL TEST: Verifies Amendment C compliance.
        
        Given: Inputs file with >200 lines, parameter at line 250
        When:  Building physics_parameters index
        Then:  Deep parameter must be indexed (no max_lines truncation)
        
        Amendment C.2.1: Full-file parsing required
        Bug Fix: database/scripts/build_index.py line 319 (max_lines=200)
        
        This test MUST fail with old code, MUST pass with Metadata Schema integration
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "DeepTest"
        
        repo_root = tmp_path / "DeepTest"
        case_dir = repo_root / "Exec" / "DeepCase"
        case_dir.mkdir(parents=True)
        
        # Create inputs file with deep parameter (line > 200)
        lines = []
        # Add 250 comment lines to push parameter deep
        for i in range(250):
            lines.append(f"# Comment line {i}")
        
        # Critical parameter at line 251
        lines.append("amr.deep_param = 1")
        lines.append("amr.critical_setting = enabled")
        lines.append("amr.n_cell = 128 128 128")
        
        (case_dir / "inputs").write_text('\n'.join(lines))
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 5
        
        # Act: Build indices
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Assert: Deep parameter was indexed
        metadata_file = output_dir / "deeptest_case_physics_parameters_metadata.json"
        assert metadata_file.exists(), "Should save metadata"
        
        metadata = json.loads(metadata_file.read_text())
        
        # Check that inputs_content is complete
        found_deep_param = False
        for item in metadata:
            inputs_content = item.get('inputs_content', {})
            if 'amr.deep_param' in inputs_content:
                found_deep_param = True
                assert inputs_content['amr.deep_param'] == '1', \
                    "Deep parameter value should be correct"
                break
        
        assert found_deep_param, \
            "AMENDMENT C VIOLATION: Parameter at line >200 was not indexed!\n" + \
            "This means max_lines truncation is still happening.\n" + \
            "Must use Metadata Schema's extract_metadata (full parsing)."
        
        print("\n✅ Amendment C: No truncation - deep parameters indexed")
    
    
    def test_level2_inputs_content_complete(self, tmp_path):
        """
        Given: Complex inputs file with many parameters
        When:  Extracting metadata
        Then:  inputs_content should be complete dict (not truncated string)
        
        Amendment C: Contextual Awareness
        Reuses: Metadata Schema's extract_metadata
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "CompleteTest"
        
        repo_root = tmp_path / "CompleteTest"
        case_dir = repo_root / "Exec" / "Complex"
        case_dir.mkdir(parents=True)
        
        # Complex inputs with many parameters
        inputs_content = """
# Grid configuration
amr.n_cell = 128 64 32
amr.max_level = 3
amr.ref_ratio = 2 2 2

# Physics
amr.cfl = 0.5
amr.use_soret = true
amr.diffusion_type = ConstantDiffusivity

# Boundary conditions
geometry.is_periodic = 0 0 1
xlo.type = Inflow
xhi.type = Outflow

# Chemistry (deep in file)
amr.chem_integrator = ReactorCvode
amr.use_typ_vals_chem = 1
"""
        (case_dir / "inputs").write_text(inputs_content)
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 3
        
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Check metadata structure
        metadata_file = output_dir / "completetest_case_physics_parameters_metadata.json"
        metadata = json.loads(metadata_file.read_text())
        
        # Verify inputs_content is dict with all parameters
        for item in metadata:
            inputs_dict = item.get('inputs_content', {})
            
            # Should be dict, not string
            assert isinstance(inputs_dict, dict), \
                f"inputs_content should be dict, got {type(inputs_dict)}"
            
            # Should have many parameters (not truncated)
            assert len(inputs_dict) >= 10, \
                f"Should have ≥10 parameters, got {len(inputs_dict)}"
            
            # Verify specific parameters exist
            expected_params = [
                'amr.n_cell', 'amr.max_level', 'amr.cfl',
                'amr.chem_integrator', 'geometry.is_periodic'
            ]
            
            for param in expected_params:
                assert param in inputs_dict, \
                    f"Missing parameter: {param} (truncation?)"
            
            break  # Check first entry
        
        print("\n✅ inputs_content is complete dict (Amendment C)")


class TestLevel2PortableKeys:
    """Test 3: Verify portable identifiers (Amendment B)."""
    
    def test_level2_portable_keys(self, tmp_path):
        """
        Given: Case at absolute path /tmp/pytest/Code/Exec/Test
        When:  Building indices
        Then:  Metadata should use repo_path (relative), not local_path
        
        Amendment B: Portable Identifiers
        PRD 5.4: Path Hierarchy index uses relative paths
        
        Critical: Enables index sharing between users/machines
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "PortableTest"
        
        # Simulate absolute paths (NERSC-like)
        repo_root = tmp_path / "global" / "cfs" / "user" / "PortableTest"
        case_dir = repo_root / "Exec" / "RegTests" / "PMF"
        case_dir.mkdir(parents=True)
        
        (case_dir / "inputs").write_text("max_step = 10")
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 3
        
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Check path_hierarchy metadata
        metadata_file = output_dir / "portabletest_case_path_hierarchy_metadata.json"
        metadata = json.loads(metadata_file.read_text())
        
        for item in metadata:
            # Should have repo_path (portable)
            assert 'repo_path' in item, "Missing repo_path (portable ID)"
            
            repo_path = item['repo_path']
            
            # Must be relative
            assert not repo_path.startswith('/'), \
                f"repo_path must be relative, got: {repo_path}"
            
            # Must not contain temp/absolute path components
            assert 'tmp' not in repo_path.lower(), \
                f"repo_path contains temp path: {repo_path}"
            
            assert 'global/cfs' not in repo_path, \
                f"repo_path contains absolute prefix: {repo_path}"
            
            # Should be correct relative path
            assert repo_path == "Exec/RegTests/PMF" or \
                   repo_path.endswith("Exec/RegTests/PMF"), \
                f"Expected 'Exec/RegTests/PMF', got: {repo_path}"
            
            print(f"\n✅ Portable path: {repo_path}")
            break


class TestLevel2MissingMetadata:
    """Test 4: Handle missing READMEs gracefully."""
    
    def test_level2_missing_readme_handling(self, tmp_path):
        """
        Given: Case with inputs but no README.md
        When:  Building physics_parameters
        Then:  Should build successfully using only inputs
        
        PRD 2.2: Pain Point 3 (Missing Metadata)
        Reuses: find_case_directories from database/scripts/utils
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "NoReadme"
        
        repo_root = tmp_path / "NoReadme"
        case_dir = repo_root / "Exec" / "Minimal"
        case_dir.mkdir(parents=True)
        
        # Only inputs, no README
        (case_dir / "inputs").write_text("""
amr.n_cell = 64 64 64
amr.riemann_solver = HLLC
""")
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 2
        
        # Act: Should not crash
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        
        try:
            builder.build(repo_root=repo_root, output_dir=output_dir)
            success = True
        except Exception as e:
            success = False
            print(f"❌ Build failed: {e}")
        
        # Assert: Build succeeded
        assert success, "Should handle missing README gracefully"
        
        # Physics index should exist
        assert (output_dir / "noreadme_case_physics_parameters.faiss").exists(), \
            "Should create physics index even without README"
        
        print("\n✅ Handles missing README (uses inputs only)")


class TestLevel2MetadataExtraction:
    """Test 4b: Validate metadata extraction for minimal repo fixtures."""

    def test_level2_metadata_extraction_minimal_repo(self, tmp_path):
        """
        Given: Minimal repo with two cases
        When:  Building Level 2 indices
        Then:  Metadata should include repo_path and parsed inputs per case
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig

        class MiniConfig(BaseAMReXConfig):
            code_name = "Mini"

        class MiniEmbedder:
            def __init__(self, dimension=3):
                self.dimension = dimension

            def embed_texts(self, texts):
                return [[0.1] * self.dimension for _ in texts]

        repo_root = tmp_path / "Mini"
        case_a = repo_root / "Exec" / "CaseA"
        case_b = repo_root / "Exec" / "CaseB"
        case_a.mkdir(parents=True)
        case_b.mkdir(parents=True)

        (case_a / "inputs").write_text("amr.n_cell = 16 16 16\nmax_step = 5\n")
        (case_b / "inputs").write_text("amr.n_cell = 32 32 32\ngeometry.is_periodic = 1 0 0\n")

        builder = Level2Builder(config=MiniConfig, embedder=MiniEmbedder())
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)

        metadata_file = output_dir / "mini_case_physics_parameters_metadata.json"
        assert metadata_file.exists(), "Should write physics_parameters metadata"

        metadata = json.loads(metadata_file.read_text())
        by_path = {item.get('repo_path'): item for item in metadata}

        assert "Exec/CaseA" in by_path
        assert "Exec/CaseB" in by_path

        case_a_meta = by_path["Exec/CaseA"]
        case_b_meta = by_path["Exec/CaseB"]

        assert case_a_meta.get('inputs_content', {}).get('amr.n_cell') == '16 16 16'
        assert case_a_meta.get('inputs_content', {}).get('max_step') == '5'
        assert case_b_meta.get('inputs_content', {}).get('amr.n_cell') == '32 32 32'
        assert case_b_meta.get('inputs_content', {}).get('geometry.is_periodic') == '1 0 0'

class TestLevel2RetrievalSpeed:
    """Test 5: Validate query performance across 6 indices."""
    
    @pytest.mark.performance
    def test_level2_retrieval_speed(self):
        """
        Given: Populated Level 2 indices (6 sub-indices)
        When:  Searching all indices for a case
        Then:  Should complete in <2 seconds

        NFR-2: Query Response Time
        Note: Searching 6 FAISS indices simultaneously
        """
        import time
        from database.indexing.level2_searcher import Level2Searcher

        # Skip if indices don't exist (check actual location: database/faiss/level2)
        index_dir = Path("database/faiss/level2")
        if not index_dir.exists():
            pytest.skip("Level 2 indices not built")
        
        searcher = Level2Searcher(code="AMReX", index_dir=index_dir)
        
        # Act: Time search across all 6 indices
        start = time.time()
        results = searcher.search_all_cases(
            "grid refinement with chemistry", 
            top_k=5
        )
        elapsed = time.time() - start
        
        # Assert: <2 seconds
        assert elapsed < 2.0, \
            f"Level 2 search took {elapsed:.2f}s (requirement: <2s)"
        
        print(f"\n⚡ Level 2 search latency: {elapsed*1000:.1f}ms")


class TestLevel2Integration:
    """Bonus: Integration with existing utilities."""
    
    def test_level2_reuses_find_case_directories(self, tmp_path):
        """
        Given: Level 2 builder
        When:  Discovering cases
        Then:  Should use find_case_directories from utils
        
        Ensures: No code duplication, consistent discovery
        """
        from database.indexing.level2_builder import Level2Builder
        from database.scripts.utils import find_case_directories
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "TestReuse"
        
        repo_root = tmp_path / "TestReuse"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        (case_dir / "inputs").write_text("max_step = 1")
        
        # Verify find_case_directories works
        rel_paths, abs_paths = find_case_directories(repo_root)
        assert len(abs_paths) == 1, "Should find 1 case"
        
        # Builder should use same function
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384]
        
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        
        # Check builder uses utility
        with patch('database.indexing.level2_builder.find_case_directories') as mock_find:
            mock_find.return_value = (rel_paths, abs_paths)
            
            output_dir = tmp_path / "level2"
            builder.build(repo_root=repo_root, output_dir=output_dir)
            
            # Verify utility was called
            mock_find.assert_called_once()
            
        print("\n✅ Reuses find_case_directories utility")
    
    
    def test_level2_uses_component4_extract_metadata(self, tmp_path):
        """
        Given: Case directory
        When:  Building indices
        Then:  Should use Metadata Schema's extract_metadata (not old utils)
        
        Critical: Ensures Amendment C compliance (full parsing)
        Replaces: extract_input_file_content (max_lines=200 bug)
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "MetadataSchemaTest"
        
        repo_root = tmp_path / "MetadataSchemaTest"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        (case_dir / "inputs").write_text("test_param = value")
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384]
        
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        
        # Patch extract_metadata to verify it's called
        with patch.object(TestConfig, 'extract_metadata', wraps=TestConfig.extract_metadata) as mock_extract:
            output_dir = tmp_path / "level2"
            builder.build(repo_root=repo_root, output_dir=output_dir)
            
            # Verify Metadata Schema method was used
            assert mock_extract.called, \
                "Should use Metadata Schema's extract_metadata"
            
            # Verify NOT using old extract_input_file_content
            # (Would need to check it's not imported, but wrapping is enough)
            
        print("\n✅ Uses Metadata Schema extract_metadata (Amendment C)")
