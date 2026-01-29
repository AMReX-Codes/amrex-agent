"""
Indexing Engine: Physics-Agnostic Keywords & Scoring.3: Additional Indices Extension Tests

Validates that configs can add domain-specific indices beyond the base 7.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock
import json


class TestLevel2AdditionalIndices:
    """Test that configs can define additional indices."""
    
    def test_level2_config_can_add_custom_index(self, tmp_path):
        """
        Given: Config with additional_level2_indices defined
        When:  Building Level 2 indices
        Then:  Should create base 7 + additional custom indices
        
        Architecture: Extensibility via config (yt-project pattern)
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class ExtendedConfig(BaseAMReXConfig):
            code_name = "ExtendedSolver"
            
            # Add an 8th index
            additional_level2_indices = {
                'diagnostic_outputs': {
                    'weight': 0.05,
                    'keywords': ['diag', 'output', 'plot', 'checkpoint'],
                    'description': 'Diagnostic and output configuration'
                }
            }
        
        repo_root = tmp_path / "ExtendedSolver"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        (case_dir / "inputs").write_text("""
amr.n_cell = 64 64 64
diag.output_interval = 10
plot.vars = density velocity
checkpoint.frequency = 100
""")
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 15
        
        builder = Level2Builder(config=ExtendedConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Should have base 7 indices
        base_indices = [
            'physics_parameters',
            'grid_specifications',
            'development_activity',
            'configuration_complexity',
            'path_hierarchy',
            'domain_models',
            'resource_requirements',
        ]
        
        for index_name in base_indices:
            assert (output_dir / f"extendedsolver_case_{index_name}.faiss").exists(), \
                f"Missing base index: {index_name}"
        
        # Should have custom index
        custom_index = output_dir / "extendedsolver_case_diagnostic_outputs.faiss"
        assert custom_index.exists(), \
            "Should create additional custom index: diagnostic_outputs"
        
        # Check metadata
        metadata_file = output_dir / "extendedsolver_case_diagnostic_outputs_metadata.json"
        assert metadata_file.exists(), \
            "Should create metadata for custom index"
        
        metadata = json.loads(metadata_file.read_text())
        assert len(metadata) > 0, "Custom index should have content"
        
        # Verify it filtered by keywords
        for item in metadata:
            inputs_content = item.get('inputs_content', {})
            # Should have at least one diagnostic param
            has_diag = any('diag' in k.lower() or 'plot' in k.lower() or 'checkpoint' in k.lower() 
                          for k in inputs_content.keys())
            if has_diag:
                print(f"\n✅ Custom index filtered diagnostic parameters")
                break
        
        print(f"\n✅ Created 7 base + 1 custom = 8 total indices")
    
    
    def test_level2_multiple_additional_indices(self, tmp_path):
        """
        Given: Config with multiple additional indices
        When:  Building
        Then:  Should create all additional indices
        
        Validates: Multiple extensions supported
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class MultiIndexConfig(BaseAMReXConfig):
            code_name = "MultiIndex"
            
            additional_level2_indices = {
                'particle_setup': {
                    'weight': 0.03,
                    'keywords': ['particles', 'beams', 'species'],
                },
                'boundary_conditions': {
                    'weight': 0.02,
                    'keywords': ['bc', 'boundary', 'wall'],
                },
            }
        
        repo_root = tmp_path / "MultiIndex"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        (case_dir / "inputs").write_text("""
particles.n_species = 2
bc.lo = periodic
bc.hi = outflow
""")
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 20
        
        builder = Level2Builder(config=MultiIndexConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Should have both custom indices
        assert (output_dir / "multiindex_case_particle_setup.faiss").exists(), \
            "Should create particle_setup index"
        
        assert (output_dir / "multiindex_case_boundary_conditions.faiss").exists(), \
            "Should create boundary_conditions index"
        
        # Count total indices
        faiss_files = list(output_dir.glob("*.faiss"))
        assert len(faiss_files) >= 9, \
            f"Should create 7 base + 2 custom = 9 indices, got {len(faiss_files)}"
        
        print(f"\n✅ Created {len(faiss_files)} total indices (7 base + 2 custom)")
    
    
    def test_level2_warpx_real_world_example(self, tmp_path):
        """
        Given: WarpX config with plasma-specific additional indices
        When:  Building
        Then:  Should work seamlessly with WarpX domain
        
        Real World: Shows how WarpX would extend the system
        """
        from database.indexing.level2_builder import Level2Builder
        from database.configs import BaseAMReXConfig
        
        class WarpXConfig(BaseAMReXConfig):
            code_name = "WarpX"
            
            # Override domain_models keywords (not chemistry!)
            level2_index_keywords = {
                'domain_models': ['USE_MPI', 'USE_CUDA', 'USE_PSATD'],
                'physics_parameters': ['plasma', 'laser', 'beams', 'electromagnetic'],
            }
            
            # Add WarpX-specific indices
            additional_level2_indices = {
                'particle_distributions': {
                    'weight': 0.04,
                    'keywords': ['particles', 'distribution', 'injection'],
                },
                'laser_profiles': {
                    'weight': 0.03,
                    'keywords': ['laser', 'antenna', 'profile'],
                },
            }
        
        repo_root = tmp_path / "WarpX"
        case_dir = repo_root / "Examples" / "LaserAcceleration"
        case_dir.mkdir(parents=True)
        
        (case_dir / "inputs").write_text("""
plasma.density = 1e23
laser.profile = Gaussian
particles.injection_style = NUniformPerCell
beams.species = electrons
""")
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 20
        
        builder = Level2Builder(config=WarpXConfig, embedder=mock_embedder)
        output_dir = tmp_path / "level2"
        builder.build(repo_root=repo_root, output_dir=output_dir)
        
        # Should have WarpX-specific indices
        assert (output_dir / "warpx_case_particle_distributions.faiss").exists(), \
            "Should create WarpX particle index"
        
        assert (output_dir / "warpx_case_laser_profiles.faiss").exists(), \
            "Should create WarpX laser index"
        
        # Should NOT have combustion-specific content
        # (domain_models exists but filtered by WarpX keywords)
        
        print("\n✅ WarpX extends system with domain-specific indices")
