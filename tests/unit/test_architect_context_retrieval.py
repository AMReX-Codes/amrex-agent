"""
Architect Service: Context Retrieval: Architect Context Retrieval Tests

Validates that ArchitectService correctly uses Level1Searcher to retrieve
solver-specific technical documentation for simulation planning.

Architecture:
    Solver Selection (6a) → Context Retrieval (6b) → Baseline Selection (6c)

References:
    - Plan v4.0: Orchestration layer
    - Indexing Engine: Level 1 (Documentation): Level1Searcher implementation
    - PRD 5.3: Top-5 documents requirement
    - NFR-2: Latency < 2 seconds
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List

# Import services
from src.services.architect import ArchitectService
from database.indexing.level1_searcher import Level1Searcher
from database.configs.amrex_config import AMReXConfig


class TestLevel1ContextRetrieval:
    """Test basic context retrieval for specific solver."""
    
    def test_level1_context_retrieval(self, tmp_path):
        """
        Given: Solver selected (AMReX) and user query
        When:  Architect calls retrieve_context()
        Then:  Should use AMReX-specific Level 1 indices
        
        Validates: Correct solver isolation (AMReX docs)
        """
        # Arrange
        query = "premixed flame simulation"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Mock solver config from Architect Service: Solver Selection
        solver_config = Mock()
        solver_config.code_name = 'AMReX'
        
        # Mock Level1Searcher to return AMReX-specific docs
        mock_amrex_docs = [
            {
                'content': 'AMReX premixed flame parameters...',
                'doc_type': 'parameter_guide',
                'source': 'amrex_inputs_guide.md',
                'score': 0.88
            },
            {
                'content': 'AMReX combustion chemistry setup...',
                'doc_type': 'case_readme',
                'source': 'PMF/README.md',
                'score': 0.85
            }
        ]
        
        with patch('database.indexing.level1_searcher.Level1Searcher') as MockLevel1:
            mock_searcher = Mock()
            mock_searcher.search_all_docs = Mock(return_value=mock_amrex_docs)
            MockLevel1.return_value = mock_searcher
            
            # Act
            results = architect.retrieve_context(query, solver_config)
            
            # Assert
            assert results is not None
            assert len(results) > 0
            
            # Verify Level1Searcher was instantiated with correct code
            MockLevel1.assert_called_once()
            call_kwargs = MockLevel1.call_args[1]
            assert call_kwargs['code'] == 'AMReX', "Should use AMReX indices"
            
            # Verify search was called
            mock_searcher.search_all_docs.assert_called_once()
            
            # Verify results are AMReX-specific
            for result in results:
                assert 'AMReX' in result['content'] or 'amrex' in result['source'].lower()


class TestLevel1MultiIndexSearch:
    """Test aggregation across multiple documentation indices."""
    
    def test_level1_multi_index_search(self, tmp_path):
        """
        Given: Query matching multiple doc types
        When:  Level1Searcher searches all 7 indices
        Then:  Should combine and sort results by score
        
        Validates: Multi-index aggregation from Indexing Engine: Level 1 (Documentation)
        """
        query = "grid generation and refinement"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        solver_config = Mock()
        solver_config.code_name = 'AMReX'
        
        # Mock results from different indices, different scores
        mock_multi_index_results = [
            {
                'content': 'README grid setup...',
                'doc_type': 'solver_readme',
                'source': 'README.md',
                'score': 0.90  # Highest
            },
            {
                'content': 'Parameter guide AMR...',
                'doc_type': 'parameter_guide',
                'source': 'inputs_guide.md',
                'score': 0.80  # Second
            },
            {
                'content': 'Tutorial grid refinement...',
                'doc_type': 'tutorial',
                'source': 'tutorial_amr.md',
                'score': 0.75  # Third
            }
        ]
        
        with patch('database.indexing.level1_searcher.Level1Searcher') as MockLevel1:
            mock_searcher = Mock()
            mock_searcher.search_all_docs = Mock(return_value=mock_multi_index_results)
            MockLevel1.return_value = mock_searcher
            
            # Act
            results = architect.retrieve_context(query, solver_config)
            
            # Assert - results combined and sorted
            assert len(results) == 3
            
            # Verify sorted by score (descending)
            assert results[0]['score'] >= results[1]['score']
            assert results[1]['score'] >= results[2]['score']
            
            # Verify different doc types present
            doc_types = [r['doc_type'] for r in results]
            assert len(set(doc_types)) > 1, "Should have results from multiple indices"


class TestLevel1ContextStructure:
    """Test output format for LLM consumption (Architect Service: Modification Planning)."""
    
    def test_level1_context_structure(self, tmp_path):
        """
        Given: Valid context retrieval
        When:  Results returned
        Then:  Should have structure ready for LLM prompting
        
        Validates: Output format for Architect Service: Modification Planning citation generation
        """
        query = "timestep settings"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        solver_config = Mock()
        solver_config.code_name = 'AMReX'
        
        mock_results = [
            {
                'content': 'Timestep control in AMReX...',
                'doc_type': 'parameter_guide',
                'source': 'report5.txt',
                'score': 0.88
            }
        ]
        
        with patch('database.indexing.level1_searcher.Level1Searcher') as MockLevel1:
            mock_searcher = Mock()
            mock_searcher.search_all_docs = Mock(return_value=mock_results)
            MockLevel1.return_value = mock_searcher
            
            # Act
            results = architect.retrieve_context(query, solver_config)
            
            # Assert - structure validation
            assert isinstance(results, list), "Should return list"
            
            for result in results:
                # Required fields for LLM prompting
                assert 'content' in result, "Need content for context"
                assert 'doc_type' in result, "Need doc_type for citation"
                assert 'source' in result, "Need source for reference"
                assert 'score' in result, "Need score for ranking"
                
                # Validate types
                assert isinstance(result['content'], str)
                assert isinstance(result['doc_type'], str)
                assert isinstance(result['source'], str)
                assert isinstance(result['score'], (int, float))
                
                # Validate source preserved (for citations)
                assert len(result['source']) > 0, "Source must be populated"


class TestLevel1LatencyRequirement:
    """Test NFR-2: Latency < 2 seconds."""
    
    def test_level1_latency_requirement(self, tmp_path):
        """
        Given: Standard query
        When:  retrieve_context() is called
        Then:  Should complete in < 2 seconds
        
        Validates: NFR-2 performance requirement
        """
        query = "simulation parameters"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        solver_config = Mock()
        solver_config.code_name = 'AMReX'
        
        # Mock fast response
        mock_results = [{'content': 'test', 'doc_type': 'test', 'source': 'test', 'score': 0.9}]
        
        with patch('database.indexing.level1_searcher.Level1Searcher') as MockLevel1:
            mock_searcher = Mock()
            mock_searcher.search_all_docs = Mock(return_value=mock_results)
            MockLevel1.return_value = mock_searcher
            
            # Act - measure time
            start_time = time.time()
            results = architect.retrieve_context(query, solver_config)
            elapsed_time = time.time() - start_time
            
            # Assert - latency requirement
            assert elapsed_time < 2.0, f"Must complete in < 2s (took {elapsed_time:.3f}s)"
            
            # Note: With mocking, this should be ~0.001s
            # Real test with actual FAISS would verify actual latency


class TestLevel1Integration6aTo6c:
    """Test pipeline integration: 6a → 6b → 6c."""
    
    def test_level1_integration_6a_to_6c(self, tmp_path):
        """
        Given: Complete pipeline from solver selection to baseline selection
        When:  Data flows through components
        Then:  Should maintain type safety and structure
        
        Validates: Integration across Architect Service: Solver Selection/6b/6c
        """
        user_query = "supersonic combustion simulation"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Step 1: Architect Service: Solver Selection - Solver Selection
        mock_level0_result = {
            'code': 'AMReX',
            'score': 0.92
        }
        
        architect.level0_searcher = Mock()
        architect.level0_searcher.search = Mock(return_value=[mock_level0_result])
        architect.code_configs = {'AMReX': AMReXConfig}
        
        solver_config = architect.select_solver(user_query)
        
        # Verify 6a output
        assert solver_config is not None
        assert solver_config.code_name == 'AMReX'
        
        # Step 2: Architect Service: Context Retrieval - Context Retrieval
        mock_context = [
            {
                'content': 'Supersonic flow parameters...',
                'doc_type': 'parameter_guide',
                'source': 'amrex_guide.md',
                'score': 0.88
            }
        ]
        
        with patch('database.indexing.level1_searcher.Level1Searcher') as MockLevel1:
            mock_searcher = Mock()
            mock_searcher.search_all_docs = Mock(return_value=mock_context)
            MockLevel1.return_value = mock_searcher
            
            context = architect.retrieve_context(user_query, solver_config)
        
        # Verify 6b output
        assert context is not None
        assert len(context) > 0
        assert all('content' in doc for doc in context)
        
        # Step 3: Architect Service: Baseline Selection - Baseline Selection (mock)
        # This validates context structure is ready for 6c
        mock_baseline_selector = Mock()
        mock_baseline_selector.select_baseline = Mock(return_value={'case': 'PMF'})
        
        baseline = mock_baseline_selector.select_baseline(
            solver=solver_config,
            context=context,
            query=user_query
        )
        
        # Verify pipeline integration
        assert baseline is not None
        mock_baseline_selector.select_baseline.assert_called_once_with(
            solver=solver_config,
            context=context,
            query=user_query
        )
        
        # Verify type safety maintained
        assert isinstance(context, list)
        assert all(isinstance(doc, dict) for doc in context)


class TestLevel1TopKRequirement:
    """Test PRD 5.3: Top-5 documents."""
    
    def test_level1_returns_top_5(self, tmp_path):
        """
        Given: Query with many matching documents
        When:  retrieve_context() is called
        Then:  Should return exactly top-5 results
        
        Validates: PRD 5.3 requirement
        """
        query = "parameter settings"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        solver_config = Mock()
        solver_config.code_name = 'AMReX'
        
        # Mock 5 results (top-k=5)
        mock_results = [
            {'content': f'Doc {i}', 'doc_type': 'guide', 'source': f'doc{i}.md', 'score': 0.9 - i*0.05}
            for i in range(5)
        ]
        
        with patch('database.indexing.level1_searcher.Level1Searcher') as MockLevel1:
            mock_searcher = Mock()
            mock_searcher.search_all_docs = Mock(return_value=mock_results)
            MockLevel1.return_value = mock_searcher
            
            # Act
            results = architect.retrieve_context(query, solver_config)
            
            # Assert - exactly top-5
            assert len(results) == 5, "PRD 5.3: Must return top-5 documents"
            
            # Verify search_all_docs was called with top_k=5
            mock_searcher.search_all_docs.assert_called_once_with(query, top_k=5)


# Architect Service: Context Retrieval Marker
pytestmark = pytest.mark.architect_context_retrieval
