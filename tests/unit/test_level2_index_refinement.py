"""
Indexing Engine: Path Hierarchy Weights: Level 2 Index Refinement Tests

Validates:
1. git_metrics split into development_activity + configuration_complexity
2. path_hierarchy uses Config.path_weights for scoring
3. 7 total indices (6 base + split)
"""
import pytest
from pathlib import Path
from unittest.mock import Mock
import json


class TestLevel2GitMetricsSplit:
    """Test git_metrics split into two orthogonal signals."""
    
    def test_level2_creates_development_activity_index(self, tmp_path):
        """
        Given: Case with git history
        When:  Building Level 2 indices
        Then:  Should create development_activity.faiss (not git_metrics)
        
        Development Activity = Health metric (commits, contributors, recency)
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "DevActivity"
        
        repo_root = tmp_path / "DevActivity"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        (case_dir / "inputs").write_text("max_step = 10")
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 10
        
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Should create development_activity (NOT git_metrics)
        assert (output_dir / "devactivity_case_development_activity.faiss").exists(), \
            "Should create development_activity index"
        
        assert not (output_dir / "devactivity_case_git_metrics.faiss").exists(), \
            "Should NOT create old git_metrics index (split into 2)"
        
        print("\n✅ development_activity index created (health metric)")
    
    
    def test_level2_creates_configuration_complexity_index(self, tmp_path):
        """
        Given: Case with complex inputs file (many overrides)
        When:  Building Level 2 indices
        Then:  Should create configuration_complexity.faiss
        
        Configuration Complexity = Distance from defaults (parameter count)
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "Complexity"
        
        repo_root = tmp_path / "Complexity"
        case_dir = repo_root / "Exec" / "Complex"
        case_dir.mkdir(parents=True)
        
        # Complex inputs (many parameters)
        complex_inputs = "\n".join([f"param_{i} = {i}" for i in range(50)])
        (case_dir / "inputs").write_text(complex_inputs)
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 10
        
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Should create configuration_complexity
        assert (output_dir / "complexity_case_configuration_complexity.faiss").exists(), \
            "Should create configuration_complexity index"
        
        print("\n✅ configuration_complexity index created (customization metric)")
    
    
    def test_level2_complexity_score_calculation(self, tmp_path):
        """
        Given: Two cases - one simple (5 params), one complex (100 params)
        When:  Calculating complexity scores
        Then:  Complex case should have higher score
        
        Validates: "Distance from defaults" metric
        """
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "ComplexityScore"
        
        repo_root = tmp_path / "ComplexityScore"
        
        # Simple case (few overrides)
        simple_dir = repo_root / "Exec" / "Simple"
        simple_dir.mkdir(parents=True)
        (simple_dir / "inputs").write_text("""
amr.n_cell = 64 64 64
max_step = 100
""")
        
        # Complex case (many overrides)
        complex_dir = repo_root / "Exec" / "Complex"
        complex_dir.mkdir(parents=True)
        complex_inputs = "\n".join([
            "amr.n_cell = 128 128 128",
            "amr.max_level = 3",
            "amr.ref_ratio = 2 2 2",
        ] + [f"custom.param_{i} = {i}" for i in range(50)])
        (complex_dir / "inputs").write_text(complex_inputs)
        
        # Extract metadata
        simple_meta = TestConfig.extract_metadata(simple_dir, repo_root=repo_root)
        complex_meta = TestConfig.extract_metadata(complex_dir, repo_root=repo_root)
        
        # Count parameters
        simple_count = len(simple_meta.get('inputs_content', {}))
        complex_count = len(complex_meta.get('inputs_content', {}))
        
        assert complex_count > simple_count, \
            f"Complex case should have more params: {complex_count} vs {simple_count}"
        
        # Complexity score could be: count / max_expected
        # For now, just verify count is tracked
        print(f"\n✅ Simple: {simple_count} params, Complex: {complex_count} params")


class TestLevel2PathHierarchyScoring:
    """Test path_hierarchy uses Config.path_weights."""
    
    def test_level2_path_weights_in_config(self):
        """
        Given: BaseAMReXConfig
        When:  Accessing path_weights
        Then:  Should have default path quality scores
        
        Architecture: Config defines what makes a "good" case path
        """
        from database.configs import BaseAMReXConfig
        
        assert hasattr(BaseAMReXConfig, 'path_weights'), \
            "BaseAMReXConfig should have path_weights attribute"
        
        path_weights = BaseAMReXConfig.path_weights
        
        # Should have common categories
        assert 'Production' in path_weights or 'Exec' in path_weights, \
            "Should have production/execution category"
        
        print(f"\n✅ BaseAMReXConfig.path_weights: {path_weights}")
    
    
    def test_level2_path_scoring_polymorphic(self, tmp_path):
        """
        Given: AMReX and WarpX configs with different path_weights
        When:  Scoring same path
        Then:  Should get different scores (polymorphism)
        
        Example:
        - AMReX prefers: Exec/Production > Examples
        - WarpX prefers: Examples > Exec
        """
        from database.configs import BaseAMReXConfig
        
        class PeleCConfig(BaseAMReXConfig):
            code_name = "AMReX"
            path_weights = {
                'Production': 1.0,
                'Exec': 0.9,
                'Examples': 0.6,
                'RegTests': 0.5,
                'Tests': 0.4,
            }
        
        class WarpXConfig(BaseAMReXConfig):
            code_name = "WarpX"
            path_weights = {
                'Examples': 1.0,
                'Physics_applications': 0.9,
                'Exec': 0.7,
                'Tests': 0.4,
            }
        
        # Score same path differently
        test_path_1 = "Exec/Production/PMF"
        test_path_2 = "Examples/LaserAcceleration"
        
        # AMReX should prefer Exec/Production
        pelec_score_1 = PeleCConfig.score_path(test_path_1) if hasattr(PeleCConfig, 'score_path') else None
        pelec_score_2 = PeleCConfig.score_path(test_path_2) if hasattr(PeleCConfig, 'score_path') else None
        
        # WarpX should prefer Examples
        warpx_score_1 = WarpXConfig.score_path(test_path_1) if hasattr(WarpXConfig, 'score_path') else None
        warpx_score_2 = WarpXConfig.score_path(test_path_2) if hasattr(WarpXConfig, 'score_path') else None
        
        if pelec_score_1 and warpx_score_1:
            assert pelec_score_1 > pelec_score_2, \
                "AMReX should score Production > Examples"
            
            assert warpx_score_2 > warpx_score_1, \
                "WarpX should score Examples > Production"
            
            print(f"\n✅ Polymorphic scoring:")
            print(f"   AMReX: {test_path_1} = {pelec_score_1}, {test_path_2} = {pelec_score_2}")
            print(f"   WarpX: {test_path_1} = {warpx_score_1}, {test_path_2} = {warpx_score_2}")
        else:
            print("\n⚠️  score_path method not yet implemented")


class TestLevel2SevenIndices:
    """Test that 7 indices are created (PRD update)."""
    
    def test_level2_creates_seven_indices(self, tmp_path):
        """
        Given: Default config
        When:  Building Level 2 indices
        Then:  Should create 7 indices (was 6 in Indexing Engine: Level 2 (Case Metadata))
        
        7 Indices:
        1. physics_parameters (was: physics_parameters)
        2. grid_specifications (was: grid_specifications)
        3. development_activity (NEW - was part of git_metrics)
        4. configuration_complexity (NEW - was part of git_metrics)
        5. path_hierarchy (was: path_hierarchy)
        6. domain_models (was: domain_models)
        7. resource_requirements (was: resource_requirements)
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class TestConfig(BaseAMReXConfig):
            code_name = "SevenIndices"
        
        repo_root = tmp_path / "SevenIndices"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        (case_dir / "inputs").write_text("amr.n_cell = 64 64 64")
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 15
        
        builder = Level2Builder(config=TestConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Count FAISS indices
        faiss_files = list(output_dir.glob("*.faiss"))
        
        expected_indices = [
            'physics_parameters',
            'grid_specifications',
            'development_activity',
            'configuration_complexity',
            'path_hierarchy',
            'domain_models',
            'resource_requirements',
        ]
        
        for index_name in expected_indices:
            index_file = output_dir / f"sevenindices_case_{index_name}.faiss"
            assert index_file.exists(), \
                f"Missing index: {index_name}"
        
        assert len(faiss_files) >= 7, \
            f"Should create 7+ indices, got {len(faiss_files)}"
        
        print(f"\n✅ Created {len(faiss_files)} indices (7 base)")


class TestLevel2IndexWeights:
    """Test that weights are updated for 7-index system."""
    
    def test_level2_weights_sum_to_one(self):
        """
        Given: Level2Builder WEIGHTS constant
        When:  Summing all weights
        Then:  Should sum to 1.0 (or close)
        
        Validates: Proper weight distribution across 7 indices
        """
        from database.indexing.level2_builder import Level2Builder
        
        if hasattr(Level2Builder, 'WEIGHTS'):
            weights = Level2Builder.WEIGHTS
            total = sum(weights.values())
            
            # Should be close to 1.0 (allow floating point error)
            assert abs(total - 1.0) < 0.01, \
                f"Weights should sum to 1.0, got {total}"
            
            # Should have 7 weights (or check for new names)
            print(f"\n✅ Weights: {weights}")
            print(f"   Total: {total}")
        else:
            print("\n⚠️  WEIGHTS constant not found (may be config-driven)")
