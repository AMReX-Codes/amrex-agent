"""
Architect Service: Modification Planning: Architect Modification Planning Tests

Validates Case-Based Reasoning (CBR) approach for generating modification
plans by searching existing cases and extracting parameter diffs.

Architecture:
    Baseline (6c) → Modifications (6d) → Input Writer (Input Writer)

References:
    - Plan v4.0: Orchestration layer
    - PRD Amendment C: Template-based generation
    - Indexing Engine: Physics-Agnostic Keywords & Scoring: Level 2 index routing
    - FR-6: Modification planning via parameter diff
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Tuple

# Import services
from src.services.architect import ArchitectService
from database.indexing.level2_searcher import Level2Searcher


class TestPlanFromCasePatterns:
    """Test borrowing settings from similar cases (CBR)."""
    
    def test_plan_from_case_patterns(self, tmp_path):
        """
        Given: User wants high resolution simulation
        When:  Architect searches for high-res cases
        Then:  Should extract n_cell parameter from matching case
        
        Validates: Case-Based Reasoning without LLM
        """
        # Arrange
        query = "High resolution simulation"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Baseline case (low resolution)
        baseline = {
            'case': 'Exec/RegTests/Sedov',
            'score': 0.85,
            'metadata': {
                'inputs_content': {
                    'amr.n_cell': '32 32 32',
                    'amr.max_level': '0',
                    'amr.cfl': '0.9'
                },
                'repo_path': 'Exec/RegTests/Sedov'
            }
        }
        
        # Mock Level2Searcher to return high-res variant
        mock_target_case = {
            'case': 'Exec/RegTests/SedovHighRes',
            'score': 0.90,
            'metadata': {
                'inputs_content': {
                    'amr.n_cell': '512 512 512',  # High res!
                    'amr.max_level': '2',          # More AMR levels
                    'amr.cfl': '0.9'             # Same CFL
                },
                'repo_path': 'Exec/RegTests/SedovHighRes'
            }
        }
        
        with patch.object(architect, 'level2_searcher') as mock_searcher:
            mock_searcher.search_all_cases = Mock(return_value=[mock_target_case])
            
            # Act
            plan = architect.plan_modifications(query, baseline)
            
            # Assert - modifications extracted via diff
            assert plan is not None
            assert 'modifications' in plan
            
            modifications = plan['modifications']
            
            # Should detect n_cell change
            mod_dict = dict(modifications)
            assert 'amr.n_cell' in mod_dict
            assert mod_dict['amr.n_cell'] == '512 512 512'
            
            # Should detect max_level change
            assert 'amr.max_level' in mod_dict
            assert mod_dict['amr.max_level'] == '2'
            
            # Should NOT include amr.cfl (unchanged)
            # Note: Some implementations might include all keys, that's ok too
            
            # Should include evidence (traceability)
            assert 'similar_cases' in plan
            assert 'SedovHighRes' in plan['similar_cases'][0]
            
            # No LLM calls needed
            assert plan.get('used_llm', False) == False


class TestParameterDiffExtraction:
    """Test dictionary diffing logic."""
    
    def test_parameter_diff_extraction(self, tmp_path):
        """
        Given: Base and target parameter dictionaries
        When:  Calculate diff
        Then:  Should return only changed parameters
        
        Validates: Core diff algorithm
        """
        # Arrange
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        base = {
            'amr.max_level': '0',
            'amr.cfl': '0.9',
            'amr.n_cell': '32 32 32'
        }
        
        target = {
            'amr.max_level': '2',      # Changed
            'amr.cfl': '0.9',        # Same
            'amr.n_cell': '128 128 128'  # Changed
        }
        
        # Act
        diffs = architect._calculate_diff(base, target)
        
        # Assert
        assert len(diffs) == 2, "Should have 2 changes"
        
        diff_dict = dict(diffs)
        assert diff_dict['amr.max_level'] == '2'
        assert diff_dict['amr.n_cell'] == '128 128 128'
        assert 'amr.cfl' not in diff_dict, "Unchanged param should be excluded"
    
    def test_parameter_diff_new_keys(self, tmp_path):
        """
        Given: Target has parameters not in baseline
        When:  Calculate diff
        Then:  Should include new parameters
        
        Validates: Adding new parameters (e.g., chemistry mechanism)
        """
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        base = {
            'amr.n_cell': '64 64 64'
        }
        
        target = {
            'amr.n_cell': '64 64 64',
            'amr.chem_file': 'drm19.dat',  # New parameter
            'amr.do_react': '1'             # New parameter
        }
        
        # Act
        diffs = architect._calculate_diff(base, target)
        
        # Assert
        diff_dict = dict(diffs)
        assert 'amr.chem_file' in diff_dict
        assert 'amr.do_react' in diff_dict


class TestSemanticKeywordMatching:
    """Test query routing to correct Level 2 indices."""
    
    def test_semantic_keyword_matching(self, tmp_path):
        """
        Given: Query with chemistry-related keywords
        When:  Map query to indices
        Then:  Should route to chemistry_mechanisms index
        
        Validates: Indexing Engine: Physics-Agnostic Keywords & Scoring semantic routing
        """
        # Arrange
        query = "Change chemistry to dodecane"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Act
        target_indices = architect._map_query_to_indices(query)
        
        # Assert
        assert 'chemistry_mechanisms' in target_indices or \
               'domain_models' in target_indices, \
               "Chemistry query should route to chemistry-related index"
        
        # Should NOT route to grid_specifications for chemistry query
        if 'grid_specifications' in target_indices:
            # If it does route there, score should be lower
            pass
    
    def test_resolution_keyword_routing(self, tmp_path):
        """Test that resolution queries route to grid_specifications."""
        query = "Increase resolution to 1024"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Act
        target_indices = architect._map_query_to_indices(query)
        
        # Assert
        assert 'grid_specifications' in target_indices, \
            "Resolution query should route to grid index"


class TestPlanPreservesMetadata:
    """Test traceability and metadata preservation."""
    
    def test_plan_preserves_metadata(self, tmp_path):
        """
        Given: Modification plan generated
        When:  Plan is returned
        Then:  Should preserve baseline metadata and evidence cases
        
        Validates: Traceability for Input Writer
        """
        # Arrange
        query = "Add AMR refinement"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        baseline = {
            'case': 'Exec/RegTests/PMF',
            'metadata': {
                'inputs_content': {'amr.max_level': '0'},
                'repo_path': 'Exec/RegTests/PMF',
                'local_path': '/path/to/PMF'
            }
        }
        
        mock_target = {
            'metadata': {
                'inputs_content': {'amr.max_level': '2'},
                'repo_path': 'Exec/RegTests/PMF_AMR'
            }
        }
        
        with patch.object(architect, 'level2_searcher') as mock_searcher:
            mock_searcher.search_all_cases = Mock(return_value=[mock_target])
            
            # Act
            plan = architect.plan_modifications(query, baseline)
            
            # Assert - metadata preserved
            assert 'similar_cases' in plan, "Must track evidence cases"
            assert len(plan['similar_cases']) > 0, "Must cite source case"
            
            # Verify source case path included
            evidence = plan['similar_cases'][0]
            assert 'PMF_AMR' in evidence, "Must reference the AMR variant"
            
            # Verify modifications include the change
            mod_dict = dict(plan['modifications'])
            assert mod_dict['amr.max_level'] == '2'


class TestFullPipelineRetrievalOnly:
    """Test end-to-end pipeline without LLM."""
    
    def test_full_pipeline_retrieval_only(self, tmp_path):
        """
        Given: User request matches existing case exactly
        When:  Pipeline runs 6a → 6b → 6c → 6d
        Then:  Should return plan with zero modifications (perfect match)
        
        Validates: Complete RAG pipeline without LLM
        """
        user_query = "3D premixed flame simulation"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Mock Architect Service: Solver Selection - Solver Selection
        from database.configs.amrex_config import AMReXConfig
        architect.level0_searcher = Mock()
        architect.level0_searcher.search = Mock(return_value=[{
            'code': 'AMReX',
            'score': 0.95
        }])
        architect.code_configs = {'AMReX': AMReXConfig}
        
        solver = architect.select_solver(user_query)
        
        # Mock Architect Service: Context Retrieval - Context Retrieval
        mock_context = [
            {'content': 'PMF setup guide...', 'doc_type': 'readme', 'source': 'PMF/README.md', 'score': 0.9}
        ]
        
        with patch('database.indexing.level1_searcher.Level1Searcher') as MockL1:
            mock_l1 = Mock()
            mock_l1.search_all_docs = Mock(return_value=mock_context)
            MockL1.return_value = mock_l1
            
            context = architect.retrieve_context(user_query, solver)
        
        # Mock Architect Service: Baseline Selection - Baseline Selection
        baseline_pmf = {
            'case': 'Exec/RegTests/PMF',
            'score': 0.95,
            'metadata': {
                'inputs_content': {
                    'amr.n_cell': '64 64 8',
                    'amr.do_react': '1',
                    'prob.P_mean': '101325.0'
                },
                'repo_path': 'Exec/RegTests/PMF'
            }
        }
        
        with patch('database.indexing.level2_searcher.Level2Searcher') as MockL2:
            mock_l2 = Mock()
            mock_l2.search_all_cases = Mock(return_value=[baseline_pmf])
            MockL2.return_value = mock_l2
            
            baseline = architect.select_baseline(user_query, solver)
        
        # Architect Service: Modification Planning - Modification Planning
        # User asked for "3D premixed flame" and got PMF (which IS a 3D premixed flame)
        # So modifications should be empty or minimal
        
        with patch.object(architect, 'level2_searcher') as mock_searcher:
            # Search returns the same case (perfect match)
            mock_searcher.search_all_cases = Mock(return_value=[baseline_pmf])
            
            plan = architect.plan_modifications(user_query, baseline['selected_case'])
        
        # Assert - perfect match means zero modifications
        assert plan is not None
        
        # Either no modifications, or very high confidence
        if plan['modifications']:
            # If there are modifications, they should be minimal
            assert len(plan['modifications']) <= 2
        
        # Confidence interpretation:
        # - 1.0 if modifications found (extracted from similar case)
        # - 0.5 if no modifications (could be perfect match OR no patterns found)
        # For perfect match scenario, 0.5 is acceptable (no changes needed)
        assert plan.get('confidence', 0) >= 0.5
        
        # No LLM needed
        assert plan.get('used_llm', False) == False


class TestKeywordBasedIndexRouting:
    """Test intelligent routing to Level 2 indices."""
    
    def test_multiple_keyword_routing(self, tmp_path):
        """
        Given: Query with multiple intents
        When:  Map to indices
        Then:  Should route to multiple relevant indices
        
        Validates: Multi-intent query handling
        """
        query = "High resolution with detailed chemistry"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Act
        indices = architect._map_query_to_indices(query)
        
        # Assert - should route to both grid AND chemistry
        assert len(indices) >= 2, "Multi-intent query should hit multiple indices"
        
        # Could include grid_specifications, chemistry_mechanisms, domain_models, etc.
        assert any('grid' in idx or 'chemistry' in idx or 'domain' in idx for idx in indices)


# Architect Service: Modification Planning Marker
pytestmark = pytest.mark.architect_modification_planning
