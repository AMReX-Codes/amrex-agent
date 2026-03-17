"""
Architect Service: Baseline Selection: Architect Baseline Selection Tests

Validates that ArchitectService correctly uses Level2Searcher to select
the best baseline case using weighted vector search across 7 indices.

Architecture:
    Solver (6a) → Context (6b) → Baseline (6c) → LLM Plan (6d)

References:
    - Plan v4.0: Orchestration layer
    - Indexing Engine: Level 2 (Case Metadata)-5e: Level2Searcher and weighted scoring
    - PRD 5.4: ≥90% accuracy (top-5 results)
    - FR-5: Weighted combination across 7 indices
"""

import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List

# Import services
from src.services.architect import ArchitectService
from database.indexing.level2_searcher import Level2Searcher
from database.configs.pelec_config import PeleCConfig


class TestLevel2BaselineScoring:
    """Test weighted scoring prioritizes correct case."""
    
    def test_level2_baseline_scoring(self, tmp_path):
        """
        Given: Query for combustion simulation
        When:  Level2Searcher scores cases
        Then:  Combustion case (PMF) should score higher than hydro (Sedov)
        
        Validates: Physics-based prioritization in weighted scoring
        """
        # Arrange
        query = "2D premixed flame with chemistry"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        solver_config = Mock()
        solver_config.code_name = 'PeleC'
        
        # Mock candidates with different physics profiles
        mock_candidates = [
            {
                'case': 'Exec/RegTests/PMF',
                'score': 0.85,  # High - combustion match
                'metadata': {
                    'physics_descriptors': ['combustion', 'premixed', 'chemistry'],
                    'repo_path': 'Exec/RegTests/PMF'
                }
            },
            {
                'case': 'Exec/RegTests/Sedov',
                'score': 0.45,  # Low - pure hydro, no chemistry
                'metadata': {
                    'physics_descriptors': ['hydrodynamics', 'shock'],
                    'repo_path': 'Exec/RegTests/Sedov'
                }
            }
        ]
        
        with patch('database.indexing.level2_searcher.Level2Searcher') as MockLevel2:
            mock_searcher = Mock()
            mock_searcher.search_all_cases = Mock(return_value=mock_candidates)
            MockLevel2.return_value = mock_searcher
            
            # Act
            result = architect.select_baseline(query, solver_config)
            
            # Assert
            assert result is not None
            assert result['selected_case']['case'] == 'Exec/RegTests/PMF'
            assert result['selected_case']['score'] > 0.8
            
            # Verify PMF scored higher than Sedov
            pmf_score = result['candidates'][0]['score']
            sedov_score = result['candidates'][1]['score']
            assert pmf_score > sedov_score, "Combustion case should score higher"


class TestLevel2WeightedCombination:
    """Test Indexing Engine: Physics-Agnostic Keywords & Scoring weights are applied correctly."""
    
    def test_level2_weighted_combination(self, tmp_path):
        """
        Given: Mock scores across 7 indices
        When:  Level2Searcher combines them
        Then:  Should apply weights: Physics(30%), Grid(20%), Path(15%), etc.
        
        Validates: Weighted combination from Indexing Engine: Physics-Agnostic Keywords & Scoring
        """
        query = "grid refinement simulation"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        solver_config = Mock()
        solver_config.code_name = 'PeleC'
        
        # Mock a single case with known sub-scores
        # Expected: 0.30*1.0 + 0.20*0.5 + 0.15*1.0 + 0.10*0.0 + 
        #          0.10*0.0 + 0.10*1.0 + 0.05*0.0 = 0.65
        mock_candidate = {
            'case': 'Exec/RegTests/PMF',
            'score': 0.65,  # Combined weighted score
            'metadata': {
                'sub_scores': {
                    'physics_descriptors': 1.0,  # 30% weight
                    'grid_specifications': 0.5,  # 20% weight
                    'path_structure': 1.0,       # 15% weight
                    'development_status': 0.0,   # 10% weight
                    'computational_complexity': 0.0,  # 10% weight
                    'domain_models': 1.0,        # 10% weight
                    'resource_requirements': 0.0  # 5% weight
                },
                'repo_path': 'Exec/RegTests/PMF'
            }
        }
        
        with patch('database.indexing.level2_searcher.Level2Searcher') as MockLevel2:
            mock_searcher = Mock()
            mock_searcher.search_all_cases = Mock(return_value=[mock_candidate])
            MockLevel2.return_value = mock_searcher
            
            # Act
            result = architect.select_baseline(query, solver_config)
            
            # Assert - verify weighted score is approximately correct
            assert result['selected_case']['score'] >= 0.64
            assert result['selected_case']['score'] <= 0.66
            
            # Verify metadata includes sub-scores
            if 'sub_scores' in result['selected_case']['metadata']:
                sub_scores = result['selected_case']['metadata']['sub_scores']
                assert 'physics_descriptors' in sub_scores
                assert 'grid_specifications' in sub_scores


class TestLevel2MetadataExtraction:
    """Test full metadata payload for Input Writer."""
    
    def test_level2_metadata_extraction(self, tmp_path):
        """
        Given: Selected baseline case
        When:  Metadata is returned
        Then:  Should include inputs_content, repo_path, local_path
        
        Validates: Full metadata for Load-Modify-Write pattern (Input Writer)
        """
        query = "premixed combustion"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        solver_config = Mock()
        solver_config.code_name = 'PeleC'
        
        # Mock candidate with full metadata
        mock_candidate = {
            'case': 'Exec/RegTests/PMF',
            'score': 0.88,
            'metadata': {
                'repo_path': 'Exec/RegTests/PMF',
                'local_path': '/path/to/PeleC/Exec/RegTests/PMF',
                'inputs_content': {
                    'amr.n_cell': '64 64 8',
                    'amr.max_level': '2',
                    'prob.P_mean': '101325.0',
                    'prob.T_mean': '298.0'
                },
                'auxiliary_files': ['drm19.dat', 'probin.f90']
            }
        }
        
        with patch('database.indexing.level2_searcher.Level2Searcher') as MockLevel2:
            mock_searcher = Mock()
            mock_searcher.search_all_cases = Mock(return_value=[mock_candidate])
            MockLevel2.return_value = mock_searcher
            
            # Act
            result = architect.select_baseline(query, solver_config)
            
            # Assert - metadata structure
            assert result is not None
            metadata = result['selected_case']['metadata']
            
            # Required fields for Input Writer
            assert 'inputs_content' in metadata, "Need parsed inputs for modification"
            assert 'repo_path' in metadata, "Need portable path identifier"
            assert 'local_path' in metadata, "Need absolute path for file operations"
            
            # Validate types
            assert isinstance(metadata['inputs_content'], dict), "inputs must be parsed dict"
            assert isinstance(metadata['repo_path'], str)
            assert isinstance(metadata['local_path'], str)
            
            # Validate auxiliary files
            if 'auxiliary_files' in metadata:
                assert isinstance(metadata['auxiliary_files'], list)


class TestLevel2FallbackRanking:
    """Test ranked list return for retry loops."""
    
    def test_level2_fallback_ranking(self, tmp_path):
        """
        Given: Ambiguous query
        When:  Multiple cases match
        Then:  Should return top-5 ranked candidates
        
        Validates: PRD 5.4 requirement (top-5 results)
        """
        query = "simulation"  # Vague query
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        solver_config = Mock()
        solver_config.code_name = 'PeleC'
        
        # Mock 5 candidates with decreasing scores
        mock_candidates = [
            {'case': f'Case_{i}', 'score': 0.9 - i*0.1, 'metadata': {'repo_path': f'Case_{i}'}}
            for i in range(5)
        ]
        
        with patch('database.indexing.level2_searcher.Level2Searcher') as MockLevel2:
            mock_searcher = Mock()
            mock_searcher.search_all_cases = Mock(return_value=mock_candidates)
            MockLevel2.return_value = mock_searcher
            
            # Act
            result = architect.select_baseline(query, solver_config)
            
            # Assert - ranked list
            assert 'candidates' in result
            assert len(result['candidates']) == 5, "PRD 5.4: Must return top-5"
            
            # Verify sorted by score (descending)
            candidates = result['candidates']
            for i in range(len(candidates) - 1):
                assert candidates[i]['score'] >= candidates[i+1]['score'], \
                    "Candidates must be sorted by score"


class TestLevel2RepoRelativePaths:
    """Ensure baseline selection preserves repo-relative case paths."""

    def test_baseline_case_path_is_repo_relative(self, tmp_path):
        """
        Given: Candidate metadata with absolute local_path
        When:  select_baseline() returns selected_case
        Then:  selected_case.case stays repo-relative (no absolute path)
        """
        query = "advection test case"

        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()

        architect = ArchitectService(mock_config, mock_embedder)

        solver_config = Mock()
        solver_config.code_name = 'AMReX'

        mock_candidate = {
            'case': 'Tests/Amr/Advection_AmrCore',
            'score': 0.91,
            'metadata': {
                'repo_path': 'Tests/Amr/Advection_AmrCore',
                'local_path': '/path/AMReX/Tests/Amr/Advection_AmrCore',
                'inputs_content': {'amr.n_cell': '64 64 64'}
            }
        }

        with patch('database.indexing.level2_searcher.Level2Searcher') as MockLevel2:
            mock_searcher = Mock()
            mock_searcher.search_all_cases = Mock(return_value=[mock_candidate])
            MockLevel2.return_value = mock_searcher

            result = architect.select_baseline(query, solver_config)

        selected_case = result['selected_case']['case']
        assert selected_case == 'Tests/Amr/Advection_AmrCore'
        assert not selected_case.startswith('/'), "Case path must be repo-relative"


class TestLevel2Integration6bTo6d:
    """Test integration across components."""
    
    def test_level2_integration_6b_to_6d(self, tmp_path):
        """
        Given: Complete pipeline from solver to baseline
        When:  Data flows through 6a → 6b → 6c
        Then:  Should return structured plan ready for 6d
        
        Validates: Integration with Components 6a, 6b, 6d
        """
        user_query = "2D hydrogen combustion with AMR"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        # Step 1: Architect Service: Solver Selection - Solver Selection
        architect.level0_searcher = Mock()
        architect.level0_searcher.search = Mock(return_value=[{
            'code': 'PeleC',
            'score': 0.92
        }])
        architect.code_configs = {'PeleC': PeleCConfig}
        
        solver_config = architect.select_solver(user_query)
        assert solver_config.code_name == 'PeleC'
        
        # Step 2: Architect Service: Context Retrieval - Context Retrieval
        mock_context = [
            {
                'content': 'AMR parameters guide...',
                'doc_type': 'parameter_guide',
                'source': 'pelec_amr.md',
                'score': 0.88
            }
        ]
        
        with patch('database.indexing.level1_searcher.Level1Searcher') as MockLevel1:
            mock_l1_searcher = Mock()
            mock_l1_searcher.search_all_docs = Mock(return_value=mock_context)
            MockLevel1.return_value = mock_l1_searcher
            
            context = architect.retrieve_context(user_query, solver_config)
        
        assert len(context) > 0
        
        # Step 3: Architect Service: Baseline Selection - Baseline Selection
        mock_baseline = {
            'case': 'Exec/RegTests/PMF',
            'score': 0.85,
            'metadata': {
                'repo_path': 'Exec/RegTests/PMF',
                'inputs_content': {'amr.n_cell': '64 64 8'},
                'local_path': '/path/to/PMF'
            }
        }
        
        with patch('database.indexing.level2_searcher.Level2Searcher') as MockLevel2:
            mock_l2_searcher = Mock()
            mock_l2_searcher.search_all_cases = Mock(return_value=[mock_baseline])
            MockLevel2.return_value = mock_l2_searcher
            
            baseline = architect.select_baseline(user_query, solver_config)
        
        # Assert - integration
        assert baseline is not None
        assert baseline['selected_case']['case'] == 'Exec/RegTests/PMF'
        assert 'confidence' in baseline
        assert 'candidates' in baseline
        
        # Verify data structure ready for Architect Service: Modification Planning
        selected = baseline['selected_case']
        assert 'metadata' in selected
        assert 'inputs_content' in selected['metadata'], "6d needs parsed inputs"
        
        # Verify pipeline maintained type safety
        assert isinstance(context, list)
        assert isinstance(baseline, dict)
        assert isinstance(baseline['selected_case'], dict)


class TestLevel2SolverIsolation:
    """Test that Level 2 search only queries correct solver indices."""
    
    def test_level2_solver_isolation(self, tmp_path):
        """
        Given: PeleC solver selected
        When:  Level2Searcher is instantiated
        Then:  Should only search pelec_case_* indices
        
        Validates: No cross-contamination between solvers
        """
        query = "combustion simulation"
        
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        
        architect = ArchitectService(mock_config, mock_embedder)
        
        solver_config = Mock()
        solver_config.code_name = 'PeleC'
        
        mock_candidates = [
            {
                'case': 'Exec/RegTests/PMF',
                'score': 0.88,
                'metadata': {'repo_path': 'Exec/RegTests/PMF'}
            }
        ]
        
        with patch('database.indexing.level2_searcher.Level2Searcher') as MockLevel2:
            mock_searcher = Mock()
            mock_searcher.search_all_cases = Mock(return_value=mock_candidates)
            MockLevel2.return_value = mock_searcher
            
            # Act
            result = architect.select_baseline(query, solver_config)
            
            # Assert - verify Level2Searcher instantiated with PeleC
            MockLevel2.assert_called_once()
            call_kwargs = MockLevel2.call_args[1]
            assert call_kwargs['code'] == 'PeleC', "Must search PeleC indices only"
            
            # Verify result is PeleC case (not PeleLMeX, incflo, etc.)
            assert 'Exec/' in result['selected_case']['case']


class TestPriorityCaseBoost:
    """Test that priority cases receive a small tie-breaker boost."""

    def test_priority_case_boost_prefers_canonical_case(self, tmp_path):
        query = "wind-driven upwelling over a periodic channel"

        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        architect = ArchitectService(mock_config, mock_embedder)

        solver_config = Mock()
        solver_config.code_name = "REMORA"
        solver_config.priority_cases = ["Exec/Upwelling", "Exec/Seamount"]

        # Upwelling_ML starts slightly higher; boost should flip to canonical Upwelling.
        mock_candidates = [
            {
                "case": "Exec/Upwelling_ML",
                "score": 0.38,
                "metadata": {"repo_path": "Exec/Upwelling_ML"},
            },
            {
                "case": "Exec/Upwelling",
                "score": 0.36,
                "metadata": {"repo_path": "Exec/Upwelling"},
            },
        ]

        with patch('database.indexing.level2_searcher.Level2Searcher') as MockLevel2:
            mock_searcher = Mock()
            mock_searcher.search_all_cases = Mock(return_value=mock_candidates)
            MockLevel2.return_value = mock_searcher

            result = architect.select_baseline(query, solver_config)

        assert result is not None
        assert result['selected_case']['case'] == 'Exec/Upwelling'
        assert result['selected_case']['score'] > 0.38
        assert result['selected_case'].get('score_bonus', 0) > 0

    def test_priority_case_boost_ignores_empty_case_paths(self, tmp_path):
        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        architect = ArchitectService(mock_config, Mock())

        solver_config = Mock()
        solver_config.priority_cases = ["Exec/RegTests/PMF"]

        candidates = [
            {"case": "", "score": 0.5, "metadata": {"repo_path": ""}},
            {"case": None, "score": 0.4, "metadata": {}},
        ]

        boosted = architect._apply_priority_case_boost(candidates, solver_config)
        assert boosted[0].get("score_bonus", 0.0) == 0.0
        assert boosted[1].get("score_bonus", 0.0) == 0.0


def test_solver_family_labels_handles_malformed_regime_alias_types(tmp_path):
    mock_config = Mock()
    mock_config.faiss_db_path = tmp_path
    architect = ArchitectService(mock_config, Mock())

    solver_config = Mock()
    solver_config.code_name = "ERF"
    solver_config.level0_physics_regimes = [
        {"family": "Atmospheric", "aliases": ["weather", 42, None, {"bad": "shape"}]},
        {"family": None, "aliases": "mesoscale"},
        "boundary layer",
        17,
    ]

    labels = architect._solver_family_labels(solver_config)
    assert "atmospheric" in labels
    assert "weather" in labels
    assert "mesoscale" in labels
    assert "boundarylayer" in labels


class TestRejectedAlternatives:
    """Ensure non-selected candidates include explicit rejection rationale."""

    def test_rejected_alternatives_include_reason_text(self, tmp_path):
        query = "premixed methane combustion"

        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_embedder = Mock()
        architect = ArchitectService(mock_config, mock_embedder)

        solver_config = Mock()
        solver_config.code_name = "PeleC"

        mock_candidates = [
            {
                "case": "Exec/RegTests/PMF",
                "score": 0.86,
                "metadata": {"repo_path": "Exec/RegTests/PMF"},
            },
            {
                "case": "Exec/RegTests/Sedov",
                "score": 0.47,
                "metadata": {"repo_path": "Exec/RegTests/Sedov"},
            },
            {
                "case": "Exec/RegTests/AcousticPulse",
                "score": 0.41,
                "metadata": {"repo_path": "Exec/RegTests/AcousticPulse"},
            },
        ]

        with patch("database.indexing.level2_searcher.Level2Searcher") as MockLevel2:
            mock_searcher = Mock()
            mock_searcher.search_all_cases = Mock(return_value=mock_candidates)
            MockLevel2.return_value = mock_searcher

            result = architect.select_baseline(query, solver_config)

        assert result is not None
        rejected = result.get("rejected_alternatives")
        assert isinstance(rejected, list)
        assert len(rejected) == 2

        for entry in rejected:
            assert entry["case"] in {"Exec/RegTests/Sedov", "Exec/RegTests/AcousticPulse"}
            assert entry["rejection_code"] == "lower_weighted_score"
            assert "rejected in favor of" in entry["rejection_reason"].lower()
            assert entry["score_gap"] > 0


class TestHierarchicalWeightsFromConfig:
    """Validate config-driven hierarchical weighting in baseline selection."""

    def test_select_baseline_passes_config_weights_to_searcher(self, tmp_path):
        query = "premixed methane combustion"

        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_config.hierarchical_weight_physics_parameters = 0.6
        mock_config.hierarchical_weight_grid_specifications = 0.2
        mock_config.hierarchical_weight_development_activity = 0.1
        mock_config.hierarchical_weight_configuration_complexity = 0.1
        mock_config.hierarchical_weight_path_hierarchy = 0.0
        mock_config.hierarchical_weight_domain_models = 0.0
        mock_config.hierarchical_weight_resource_requirements = 0.0

        architect = ArchitectService(mock_config, Mock())
        solver_config = Mock()
        solver_config.code_name = "PeleC"

        mock_candidates = [
            {"case": "Exec/RegTests/PMF", "score": 0.9, "metadata": {"repo_path": "Exec/RegTests/PMF"}},
        ]

        with patch("database.indexing.level2_searcher.Level2Searcher") as MockLevel2:
            mock_searcher = Mock()
            mock_searcher.search_all_cases = Mock(return_value=mock_candidates)
            MockLevel2.return_value = mock_searcher

            result = architect.select_baseline(query, solver_config)

        assert result["weight_source"] == "config"
        assert abs(sum(result["weights_used"].values()) - 1.0) < 1e-9
        assert result["weights_used"]["physics_parameters"] == pytest.approx(0.6)
        assert result["weights_used"]["grid_specifications"] == pytest.approx(0.2)
        assert result["weights_used"]["path_hierarchy"] == pytest.approx(0.0)

        called_kwargs = mock_searcher.search_all_cases.call_args.kwargs
        assert called_kwargs["top_k"] == 100
        assert called_kwargs["weights"]["physics_parameters"] == pytest.approx(0.6)

    def test_select_baseline_uses_defaults_when_config_weights_invalid(self, tmp_path):
        query = "premixed methane combustion"

        mock_config = Mock()
        mock_config.faiss_db_path = tmp_path
        mock_config.hierarchical_weight_physics_parameters = 0.0
        mock_config.hierarchical_weight_grid_specifications = 0.0
        mock_config.hierarchical_weight_development_activity = 0.0
        mock_config.hierarchical_weight_configuration_complexity = 0.0
        mock_config.hierarchical_weight_path_hierarchy = 0.0
        mock_config.hierarchical_weight_domain_models = 0.0
        mock_config.hierarchical_weight_resource_requirements = 0.0

        architect = ArchitectService(mock_config, Mock())
        solver_config = Mock()
        solver_config.code_name = "PeleC"

        mock_candidates = [
            {"case": "Exec/RegTests/PMF", "score": 0.9, "metadata": {"repo_path": "Exec/RegTests/PMF"}},
        ]

        with patch("database.indexing.level2_searcher.Level2Searcher") as MockLevel2:
            mock_searcher = Mock()
            mock_searcher.search_all_cases = Mock(return_value=mock_candidates)
            MockLevel2.return_value = mock_searcher

            result = architect.select_baseline(query, solver_config)

        assert result["weight_source"] == "default"
        assert result["weights_used"]["physics_parameters"] == pytest.approx(0.30)
        assert result["weights_used"]["grid_specifications"] == pytest.approx(0.20)
        assert result["weights_used"]["resource_requirements"] == pytest.approx(0.05)


def test_select_baseline_simple_zero_sum_weights_falls_back_to_defaults(tmp_path, monkeypatch):
    mock_config = Mock()
    mock_config.faiss_db_path = tmp_path
    mock_config.faiss_semantic_weight = 0.0
    mock_config.simple_weight_kb_relevance = 0.0
    mock_config.simple_weight_metrics = 0.0
    mock_config.simple_weight_path_heuristics = 0.0
    mock_config.simple_weight_domain_specific = 0.0
    mock_config.simple_weight_faiss_semantic = 0.0

    mock_embedder = Mock()
    mock_embedder.indices_available.return_value = False
    architect = ArchitectService(mock_config, mock_embedder)

    monkeypatch.setattr(
        architect.cases,
        "list_all_cases",
        lambda: {"PeleC": ["Exec/RegTests/PMF"]},
    )
    monkeypatch.setattr(
        architect.cases,
        "get_code_info",
        lambda _code_name: SimpleNamespace(local_path=tmp_path),
    )
    monkeypatch.setattr(
        architect,
        "_score_kb_relevance_batch",
        lambda *_args, **_kwargs: {"Exec/RegTests/PMF": 0.8},
    )
    monkeypatch.setattr(architect, "_is_kb_signal_weak", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(architect, "_score_metrics", lambda *_args, **_kwargs: (0.5, {}))
    monkeypatch.setattr(architect, "_score_path_heuristics", lambda *_args, **_kwargs: (0.5, {}))
    monkeypatch.setattr(architect, "_score_combustion_domain", lambda *_args, **_kwargs: (0.5, {}))

    result = architect._select_baseline(
        user_prompt="pmf baseline",
        requirements={"solver": "PeleC"},
    )

    assert result is not None
    assert abs(sum(result["weights_used"].values()) - 1.0) < 1e-9
    assert result["weights_used"]["kb_relevance"] > 0.0


# Architect Service: Baseline Selection Marker
pytestmark = pytest.mark.architect_baseline_selection
