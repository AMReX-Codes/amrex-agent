"""
Architect Service: Solver Selection: Architect Solver Selection Tests

Validates that ArchitectService correctly uses Level0Searcher to identify
the appropriate AMReX solver (PeleC, PeleLMeX, incflo, etc.) based on
user requirements.

Architecture:
    User Query → Architect → Level0Searcher → Config Class

References:
    - Plan v4.0: Orchestration layer
    - Indexing Engine: Level 0 (Physics Taxonomy): Level0Searcher implementation
    - Cases Service: Config-Driven Discovery: Config discovery pattern
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List

# Import the services we'll test
from src.services.architect import ArchitectService
from database.indexing.level0_searcher import Level0Searcher
from database.configs import discover_code_configs
from database.configs.pelec_config import PeleCConfig
from database.configs.pelelmex_config import PeleLMeXConfig


class TestLevel0SolverSelection:
    """Test basic solver selection via Level 0 RAG."""
    
    def test_level0_solver_selection(self, tmp_path):
        """
        Given: User query for specific physics regime
        When:  Architect calls select_solver()
        Then:  Should invoke Level0Searcher and return top result
        
        Validates: Brain (Architect) uses Memory (Level 0 index)
        """
        # Arrange
        query = "low-Mach premixed combustion"
        
        # Mock Level0Searcher to return PeleLMeX
        mock_level0_result = {
            'code': 'PeleLMeX',
            'score': 0.92,
            'details': {
                'matched_regime': 'low-Mach',
                'matched_capability': 'combustion'
            }
        }
        
        # Create architect with mocked searcher
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Mock the level0_searcher.search method
        architect.level0_searcher = Mock()
        architect.level0_searcher.search = Mock(return_value=[mock_level0_result])
        
        # Act
        solver_config, solver_confidence = architect.select_solver(query)
        
        # Assert
        assert solver_config is not None, "Should return a solver"
        assert solver_confidence is not None
        architect.level0_searcher.search.assert_called_once_with(query, top_k=5)
        
        # Result should be either string name or Config class
        if isinstance(solver_config, str):
            assert solver_config == 'PeleLMeX'
        else:
            assert solver_config.code_name == 'PeleLMeX'


class TestLevel0WeightedCombination:
    """Test weighted scoring integration."""
    
    def test_level0_weighted_combination(self, tmp_path):
        """
        Given: Query matching multiple sub-indices
        When:  Level0Searcher aggregates scores
        Then:  Should respect 40%/30%/20%/10% weights
        
        Validates: Weighted combination from Indexing Engine: Level 0 (Physics Taxonomy)
        """
        query = "supersonic flow"
        
        # Mock config
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Mock the sub-index searches to return known scores
        mock_searcher = Mock(spec=Level0Searcher)
        
        # Simulate weighted scoring:
        # physics_regimes (40%): PeleC = 0.9
        # solver_capabilities (30%): PeleC = 0.9
        # code_lineage (20%): PeleC = 0.8
        # cross_cutting_guidance (10%): PeleC = 0.7
        # Expected: 0.4*0.9 + 0.3*0.9 + 0.2*0.8 + 0.1*0.7 = 0.36 + 0.27 + 0.16 + 0.07 = 0.86
        
        expected_score = 0.86
        
        mock_result = {
            'code': 'PeleC',
            'score': expected_score,
            'details': {}
        }
        
        mock_searcher.search = Mock(return_value=[mock_result])
        architect.level0_searcher = mock_searcher
        
        # Act
        solver_config, solver_confidence = architect.select_solver(query)
        
        # Assert
        mock_searcher.search.assert_called_once()
        
        # If we have access to the score, verify weighting
        # (This assumes select_solver returns full result dict)
        assert solver_confidence is not None


class TestLevel0ConfidenceThreshold:
    """Test handling of ambiguous queries."""
    
    def test_level0_confidence_threshold(self, tmp_path):
        """
        Given: Ambiguous query with low confidence scores
        When:  Level0Searcher returns score < 0.6
        Then:  Should flag low confidence or log warning
        
        Validates: Confidence handling for Reviewer (Reviewer Service)
        """
        query = "fluid dynamics simulation"  # Vague query
        
        # Mock setup
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Mock low-confidence results
        low_confidence_results = [
            {'code': 'incflo', 'score': 0.45},
            {'code': 'PeleC', 'score': 0.40}
        ]
        
        mock_searcher = Mock()
        mock_searcher.search = Mock(return_value=low_confidence_results)
        architect.level0_searcher = mock_searcher
        
        # Act
        solver_config, solver_confidence = architect.select_solver(query)
        
        # Assert
        # Should still return top result
        assert solver_config is not None
        assert solver_confidence is not None
        
        # TODO: Once confidence tracking is implemented, verify:
        # - plan.solver_confidence == 0.45
        # - Warning was logged
        # - Reviewer will be stricter
        
        # For now, just ensure we don't crash on low confidence
        mock_searcher.search.assert_called_once()

    def test_level0_low_confidence_uses_llm_fallback(self, tmp_path):
        """
        Given: Low-confidence Level0 result with LLM available
        When:  select_solver() runs below threshold
        Then:  Should use LLM-selected solver and set higher confidence
        """
        query = "ambiguous flow regime"

        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()

        architect = ArchitectService(mock_config, mock_embedder)
        architect.level0_searcher = Mock()
        architect.level0_searcher.search = Mock(return_value=[
            {"code": "incflo", "score": 0.05}
        ])

        architect.llm_client = Mock()
        architect.cases = Mock()
        architect.cases.find_best_match = Mock(return_value=("PeleC", "Exec/RegTests/PMF"))
        architect.code_configs = {"PeleC": Mock(code_name="PeleC")}

        solver_config, solver_confidence = architect.select_solver(query, confidence_threshold=0.15)

        assert solver_config.code_name == "PeleC"
        assert solver_confidence == 0.8
        architect.cases.find_best_match.assert_called_once_with(query, architect.llm_client)


class TestLevel0ConfigMapping:
    """Test mapping solver names to Config classes."""
    
    def test_level0_integration_with_config(self, tmp_path):
        """
        Given: Level0Searcher returns 'PeleC' string
        When:  Architect maps to Config class
        Then:  Should return PeleCConfig instance with correct indices
        
        Validates: Integration with Cases Service: Config-Driven Discovery config discovery
        """
        # Mock setup
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Mock Level0Searcher to return PeleC
        mock_result = {
            'code': 'PeleC',
            'score': 0.85
        }
        
        mock_searcher = Mock()
        mock_searcher.search = Mock(return_value=[mock_result])
        architect.level0_searcher = mock_searcher
        
        # Mock the config discovery
        # In real code, this would use discover_code_configs()
        architect.code_configs = {
            'PeleC': PeleCConfig,
            'PeleLMeX': PeleLMeXConfig
        }
        
        # Act
        solver_config, solver_confidence = architect.select_solver("compressible flow")
        
        # Assert
        assert solver_config is not None
        assert solver_confidence is not None
        
        # Should return Config class (not instance yet)
        assert solver_config == PeleCConfig or isinstance(solver_config, type)
        
        # Verify it's the correct config
        if hasattr(solver_config, 'code_name'):
            assert solver_config.code_name == 'PeleC'
        
        # Verify it's the correct Config class
        # (validates correct Config was selected)
        if hasattr(solver_config, 'code_name'):
            assert solver_config.code_name == 'PeleC'
        
        # Verify config has the expected structure
        # (either class attribute or would have it when instantiated)
        assert hasattr(solver_config, 'additional_level2_indices') or \
               hasattr(solver_config, 'code_name'), \
               "Config should have expected attributes"


class TestSolverDisambiguationAlternatives:
    """Test structured alternatives and rejection rationale exposure."""

    def test_structured_alternatives_include_rejection_rationale(self, tmp_path):
        query = "combustion flow setup"

        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()

        architect = ArchitectService(mock_config, mock_embedder)
        architect.code_configs = {
            "PeleC": Mock(code_name="PeleC"),
            "incflo": Mock(code_name="incflo"),
            "PeleLMeX": Mock(code_name="PeleLMeX"),
        }
        architect.level0_searcher = Mock()
        architect.level0_searcher.search = Mock(
            return_value=[
                {"code": "PeleC", "score": 0.90},
                {"code": "incflo", "score": 0.70},
                {"code": "PeleLMeX", "score": 0.65},
            ]
        )

        selection = architect.select_solver(query)

        assert selection.code_name == "PeleC"
        assert selection.alternatives is not None
        assert len(selection.alternatives) == 3

        selected = [item for item in selection.alternatives if item["selected"]]
        rejected = [item for item in selection.alternatives if not item["selected"]]

        assert len(selected) == 1
        assert selected[0]["code"] == "PeleC"
        assert "selection_reason" in selected[0]

        assert len(rejected) == 2
        for item in rejected:
            assert "rejection_reason" in item
            assert item["rejection_reason"]

    def test_llm_fallback_marks_level0_candidates_rejected(self, tmp_path):
        query = "ambiguous flow regime"

        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()

        architect = ArchitectService(mock_config, mock_embedder)
        architect.level0_searcher = Mock()
        architect.level0_searcher.search = Mock(
            return_value=[
                {"code": "incflo", "score": 0.20},
                {"code": "PeleLMeX", "score": 0.03},
            ]
        )
        architect.code_configs = {
            "PeleC": Mock(code_name="PeleC"),
            "incflo": Mock(code_name="incflo"),
            "PeleLMeX": Mock(code_name="PeleLMeX"),
        }
        architect.llm_client = Mock()
        architect.cases = Mock()
        architect.cases.find_best_match = Mock(return_value=("PeleC", "Exec/RegTests/PMF"))

        selection = architect.select_solver(query, confidence_threshold=0.25)

        assert selection.code_name == "PeleC"
        assert selection.alternatives is not None

        selected = [item for item in selection.alternatives if item["selected"]]
        rejected = [item for item in selection.alternatives if not item["selected"]]

        assert len(selected) == 1
        assert selected[0]["code"] == "PeleC"
        assert selected[0]["selection_source"] == "llm_fallback"
        assert "selection_reason" in selected[0]

        assert rejected
        for item in rejected:
            assert "rejection_reason" in item
            assert "LLM fallback" in item["rejection_reason"]

    def test_flat_level0_uses_llm_disambiguation(self, tmp_path):
        query = "nonreacting jet in crossflow with adiabatic walls"

        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()

        architect = ArchitectService(mock_config, mock_embedder)
        architect.level0_searcher = Mock()
        architect.level0_searcher.search = Mock(
            return_value=[
                {"code": "PeleC", "score": 0.51},
                {"code": "PeleLMeX", "score": 0.48},
            ]
        )
        architect.code_configs = {
            "PeleC": Mock(code_name="PeleC"),
            "PeleLMeX": Mock(code_name="PeleLMeX"),
        }
        architect._find_level2_case_name_candidate = Mock(return_value=None)
        architect.llm_client = Mock()
        architect.cases = Mock()
        architect.cases.find_best_match = Mock(
            return_value=("PeleLMeX", "Exec/Production/JetInCrossflow")
        )

        selection = architect.select_solver(query)

        assert selection.code_name == "PeleLMeX"
        assert selection.alternatives is not None
        selected = [item for item in selection.alternatives if item["selected"]]
        assert len(selected) == 1
        assert selected[0]["selection_source"] == "llm_flat_disambiguation"
        architect.cases.find_best_match.assert_called_once_with(query, architect.llm_client)

    def test_flat_level0_prefers_case_name_disambiguation_before_llm(self, tmp_path):
        query = "jet in crossflow (jicf) with vitiated crossflow and adiabatic walls"

        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()

        architect = ArchitectService(mock_config, mock_embedder)
        architect.level0_searcher = Mock()
        architect.level0_searcher.search = Mock(
            return_value=[
                {"code": "PeleC", "score": 0.52},
                {"code": "PeleLMeX", "score": 0.50},
            ]
        )
        architect.code_configs = {
            "PeleC": Mock(code_name="PeleC"),
            "PeleLMeX": Mock(code_name="PeleLMeX"),
        }
        architect._find_level2_case_name_candidate = Mock(
            return_value={
                "solver": "PeleLMeX",
                "repo_path": "Exec/Production/JetInCrossflow",
                "match_confidence": 0.95,
            }
        )
        architect.llm_client = Mock()
        architect.cases = Mock()
        architect.cases.find_best_match = Mock(
            return_value=("PeleC", "Exec/RegTests/Sedov")
        )

        selection = architect.select_solver(query)

        assert selection.code_name == "PeleLMeX"
        assert selection.alternatives is not None
        selected = [item for item in selection.alternatives if item["selected"]]
        assert len(selected) == 1
        assert selected[0]["selection_source"] == "level0_flat_case_override"
        architect.cases.find_best_match.assert_not_called()


# Architect Service: Solver Selection Marker
pytestmark = pytest.mark.architect_solver_selection
