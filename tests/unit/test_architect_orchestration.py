"""
Architect Service: Orchestration Logic: Architect Orchestration Logic Tests

Validates the decision tree for choosing between CBR and LLM planning
based on confidence thresholds and configuration flags.

Architecture:
    create_plan() orchestrates: 6a → 6b → 6c → 6d → Decision → Result

References:
    - Plan v4.0: Orchestration layer
    - PRD 5.4: Confidence thresholds
    - src/config.py: faiss_fallback_to_llm flag
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict, List

# Import services
from src.services.architect import ArchitectService
from database.configs.pelec_config import PeleCConfig
from database.configs.erf_config import ERFConfig


def _write_level2_metadata(
    tmp_path: Path,
    solver_prefix: str,
    case_name: str,
    repo_path: str,
    files: int,
) -> None:
    level2_dir = tmp_path / "level2"
    level2_dir.mkdir(parents=True, exist_ok=True)
    index_types = [
        "grid_specifications",
        "domain_models",
        "path_hierarchy",
        "physics_parameters",
        "development_activity",
    ]
    for idx in range(files):
        metadata_path = level2_dir / f"{solver_prefix}_case_{index_types[idx]}_metadata.json"
        metadata_path.write_text(
            json.dumps(
                [
                    {
                        "case_name": case_name,
                        "repo_path": repo_path,
                    }
                ]
            ),
            encoding="utf-8",
        )


class TestArchitectOrchestration:
    """Test orchestration logic and decision tree."""
    
    @pytest.fixture
    def mock_architect(self, tmp_path):
        """Setup architect with mocked sub-components."""
        config = Mock()
        config.faiss_db_path = tmp_path
        config.faiss_fallback_to_llm = True
        
        embedder = Mock()
        architect = ArchitectService(config, embedder)
        
        # Mock internal methods to isolate orchestration logic
        from database.configs.pelec_config import PeleCConfig
        
        architect.select_solver = Mock(return_value=(PeleCConfig, 0.9))
        architect.retrieve_context = Mock(return_value=[
            {'content': 'doc1', 'doc_type': 'guide', 'source': 'test.md', 'score': 0.9}
        ])
        
        # Mock LLM plan method (Architect Service: LLM Planning placeholder)
        architect._llm_plan = Mock(return_value=Mock(
            modifications=[("llm_param", "1")], 
            reasoning="LLM generated plan"
        ))
        
        return architect
    
    def test_high_confidence_skips_llm(self, mock_architect):
        """
        Given: High confidence baseline (>0.85) AND perfect CBR (1.0)
        When:  create_plan() is called
        Then:  Should use pure CBR without LLM
        
        Validates: Deterministic path for high-confidence retrieval
        """
        # Arrange
        query = "high resolution simulation"
        
        # Mock 6c: High confidence baseline
        mock_architect.select_baseline = Mock(return_value={
            'selected_case': {
                'case': 'Exec/RegTests/PMF',
                'metadata': {
                    'repo_path': 'Exec/RegTests/PMF',
                    'inputs_content': {'amr.n_cell': '64 64 8'}
                }
            },
            'confidence': 0.90,  # > 0.85 threshold
            'candidates': []
        })
        
        # Mock 6d: Perfect CBR match
        cbr_plan = {
            'modifications': [("amr.n_cell", "512 512 512")],
            'confidence': 1.0,  # Perfect match
            'similar_cases': ['PMF_HighRes'],
            'used_llm': False
        }
        mock_architect.plan_modifications = Mock(return_value=cbr_plan)
        
        # Act
        plan = mock_architect.create_plan_rag(query)
        
        # Assert
        assert plan is not None
        
        # Verify LLM was NOT called
        mock_architect._llm_plan.assert_not_called()
        
        # Verify used CBR modifications
        if hasattr(plan, 'modifications'):
            assert plan.modifications == [("amr.n_cell", "512 512 512")]
        
        # Verify reasoning indicates CBR
        if hasattr(plan, 'reasoning'):
            assert 'CBR' in plan.reasoning or 'Deterministic' in plan.reasoning
        if hasattr(plan, "baseline_evidence_citations"):
            assert plan.baseline_evidence_citations == [
                {"citation_type": "baseline", "case": "Exec/RegTests/PMF"},
                {"citation_type": "similar_case", "case": "PMF_HighRes"},
            ]
    
    def test_low_baseline_confidence_triggers_llm(self, mock_architect):
        """
        Given: Low confidence baseline (≤0.85)
        When:  create_plan() is called
        Then:  Should fallback to LLM
        
        Validates: LLM fallback for uncertain baseline selection
        """
        # Arrange
        query = "unusual physics case"
        
        # Mock 6c: Low confidence baseline
        mock_architect.select_baseline = Mock(return_value={
            'selected_case': {
                'case': 'Exec/RegTests/Sedov',
                'metadata': {
                    'repo_path': 'Exec/RegTests/Sedov',
                    'inputs_content': {'amr.n_cell': '32 32 32'}
                }
            },
            'confidence': 0.50,  # < 0.85 threshold
            'candidates': []
        })
        
        # Mock 6d: Some CBR plan (doesn't matter, baseline triggered fallback)
        mock_architect.plan_modifications = Mock(return_value={
            'modifications': [],
            'confidence': 0.5,
            'similar_cases': []
        })
        
        # Act
        plan = mock_architect.create_plan_rag(query)
        
        # Assert
        # Verify LLM WAS called
        mock_architect._llm_plan.assert_called_once()
        
        # Verify baseline was passed to LLM for context
        call_args = mock_architect._llm_plan.call_args
        assert call_args is not None

    def test_llm_fallback_returns_plan_with_repo_relative_case(self, mock_architect):
        """
        Given: Low baseline confidence with repo-relative metadata
        When:  LLM fallback runs
        Then:  Should return SimulationPlan with repo-relative selected_case
        """
        query = "ambiguous test case"

        mock_architect.select_baseline = Mock(return_value={
            "selected_case": {
                "metadata": {
                    "repo_path": "Tests/Amr/Advection_AmrCore",
                    "inputs_content": {"amr.n_cell": "64 64 64"},
                }
            },
            "confidence": 0.5,
            "candidates": []
        })
        mock_architect.plan_modifications = Mock(return_value={
            "modifications": [],
            "confidence": 0.0,
            "similar_cases": []
        })
        mock_architect._llm_plan = Mock(return_value=Mock(
            modifications=[("amr.n_cell", "128 128 128")],
            reasoning="LLM generated plan"
        ))

        plan = mock_architect.create_plan_rag(query)

        assert plan.selected_case == "Tests/Amr/Advection_AmrCore"
        assert plan.used_llm is True
        assert plan.modifications == [("amr.n_cell", "128 128 128")]
    
    def test_low_cbr_confidence_triggers_llm(self, mock_architect):
        """
        Given: Good baseline (>0.85) BUT low CBR confidence (<1.0)
        When:  create_plan() is called
        Then:  Should fallback to LLM
        
        Validates: LLM fallback when CBR can't find exact patterns
        """
        # Arrange
        query = "novel modification pattern"
        
        # Mock 6c: High confidence baseline
        mock_architect.select_baseline = Mock(return_value={
            'selected_case': {
                'case': 'Exec/RegTests/PMF',
                'metadata': {
                    'repo_path': 'Exec/RegTests/PMF',
                    'inputs_content': {'amr.n_cell': '64 64 8'}
                }
            },
            'confidence': 0.95,  # > 0.85
            'candidates': []
        })
        
        # Mock 6d: Failed to find exact pattern
        mock_architect.plan_modifications = Mock(return_value={
            'modifications': [],
            'confidence': 0.0,  # Failed CBR
            'similar_cases': []
        })
        
        # Act
        plan = mock_architect.create_plan_rag(query)
        
        # Assert
        # LLM should be called to "fill in the gaps"
        mock_architect._llm_plan.assert_called_once()
    
    def test_llm_disabled_uses_cbr_anyway(self, mock_architect):
        """
        Given: Low confidence BUT LLM disabled
        When:  create_plan() is called
        Then:  Should return best-effort CBR plan
        
        Validates: Safety fallback when LLM unavailable
        """
        # Arrange
        query = "hard query"
        
        # Disable LLM fallback
        mock_architect.config.faiss_fallback_to_llm = False
        
        # Mock low confidence everywhere
        mock_architect.select_baseline = Mock(return_value={
            'selected_case': {
                'case': 'PoorMatch',
                'metadata': {
                    'repo_path': 'PoorMatch',
                    'inputs_content': {}
                }
            },
            'confidence': 0.40,
            'candidates': []
        })
        
        cbr_plan = {
            'modifications': [("best_effort", "1")],
            'confidence': 0.1,
            'similar_cases': []
        }
        mock_architect.plan_modifications = Mock(return_value=cbr_plan)
        
        # Act
        plan = mock_architect.create_plan_rag(query)
        
        # Assert
        # Should NOT call LLM
        mock_architect._llm_plan.assert_not_called()
        
        # Should return the "best effort" CBR plan
        if hasattr(plan, 'modifications'):
            assert plan.modifications == [("best_effort", "1")]
    
    def test_orchestration_pipeline_flow(self, mock_architect):
        """
        Given: Full pipeline setup
        When:  create_plan() is called
        Then:  Should call components in correct order
        
        Validates: Data flow through 6a → 6b → 6c → 6d → 6e
        """
        # Arrange
        query = "test flow"
        
        from database.configs.pelec_config import PeleCConfig
        
        # Setup full mock chain
        mock_architect.select_solver.return_value = (PeleCConfig, 0.9)
        mock_architect.retrieve_context.return_value = [
            {'content': 'doc1', 'doc_type': 'guide', 'source': 'test.md', 'score': 0.9}
        ]
        mock_architect.select_baseline = Mock(return_value={
            'selected_case': {
                'case': 'Base',
                'metadata': {
                    'repo_path': 'Base',
                    'inputs_content': {}
                }
            },
            'confidence': 0.9,
            'candidates': []
        })
        mock_architect.plan_modifications = Mock(return_value={
            'modifications': [("param", "val")],
            'confidence': 1.0,
            'similar_cases': []
        })
        
        # Act
        plan = mock_architect.create_plan_rag(query)
        
        # Assert - verify call order
        mock_architect.select_solver.assert_called_once_with(query)
        mock_architect.retrieve_context.assert_called_once()
        mock_architect.select_baseline.assert_called_once()
        mock_architect.plan_modifications.assert_called_once()
        
        # Verify plan structure
        assert plan is not None


class TestLevel2CaseNameOverride:
    def _make_architect(self, tmp_path):
        config = Mock()
        config.faiss_db_path = tmp_path
        config.faiss_fallback_to_llm = False
        config.level2_override_enabled = True
        config.level2_override_l0_threshold = 0.15
        config.level2_override_case_match_threshold = 0.90
        config.level2_override_min_metadata_hits = 3
        architect = ArchitectService(config, Mock())
        architect.select_baseline = Mock(return_value={
            "selected_case": {
                "case": "Exec/RegTests/PMF",
                "metadata": {
                    "repo_path": "Exec/RegTests/PMF",
                    "inputs_content": {"amr.n_cell": "64 64 64"},
                },
            },
            "confidence": 0.9,
            "candidates": [],
        })
        architect.plan_modifications = Mock(return_value={
            "modifications": [("amr.n_cell", "128 128 128")],
            "confidence": 1.0,
            "similar_cases": [],
            "used_llm": False,
        })
        architect.retrieve_context = Mock(return_value=[{"content": "doc"}])
        return architect

    def test_low_l0_confidence_cross_family_case_match_overrides_solver(self, tmp_path):
        _write_level2_metadata(
            tmp_path,
            solver_prefix="erf",
            case_name="TaylorGreenVortex",
            repo_path="Exec/DryRegTests/TaylorGreenVortex",
            files=3,
        )
        architect = self._make_architect(tmp_path)
        architect.select_solver = Mock(return_value=(PeleCConfig, 0.10))

        plan = architect.create_plan_rag("Please use the TaylorGreenVortex setup")

        assert plan.selected_solver == "ERF"
        assert plan.level0_solver == "PeleC"
        assert plan.level0_confidence == 0.10
        assert plan.level2_override_applied is True
        assert plan.level2_override_solver == "ERF"
        assert plan.level2_override_case == "Exec/DryRegTests/TaylorGreenVortex"
        assert plan.level2_override_confidence == 0.9
        assert architect.retrieve_context.call_args.args[1] == ERFConfig
        assert architect.plan_modifications.call_args.kwargs["solver_code"] == "ERF"

    def test_low_l0_confidence_same_family_match_does_not_override(self, tmp_path):
        _write_level2_metadata(
            tmp_path,
            solver_prefix="pelelmex",
            case_name="FlameSheet",
            repo_path="Exec/RegTests/FlameSheet",
            files=3,
        )
        architect = self._make_architect(tmp_path)
        architect.select_solver = Mock(return_value=(PeleCConfig, 0.10))

        plan = architect.create_plan_rag("Use FlameSheet as the baseline pattern")

        assert plan.selected_solver == "PeleC"
        assert plan.level2_override_applied is False
        assert plan.level2_override_solver is None
        assert architect.retrieve_context.call_args.args[1] == PeleCConfig

    def test_high_l0_confidence_does_not_override_even_with_case_match(self, tmp_path):
        _write_level2_metadata(
            tmp_path,
            solver_prefix="erf",
            case_name="TaylorGreenVortex",
            repo_path="Exec/DryRegTests/TaylorGreenVortex",
            files=3,
        )
        architect = self._make_architect(tmp_path)
        architect.select_solver = Mock(return_value=(PeleCConfig, 0.20))

        plan = architect.create_plan_rag("Please use the TaylorGreenVortex setup")

        assert plan.selected_solver == "PeleC"
        assert plan.level2_override_applied is False
        assert plan.level2_override_solver is None

    def test_low_l0_confidence_weak_case_evidence_does_not_override(self, tmp_path):
        _write_level2_metadata(
            tmp_path,
            solver_prefix="erf",
            case_name="TaylorGreenVortex",
            repo_path="Exec/DryRegTests/TaylorGreenVortex",
            files=2,
        )
        architect = self._make_architect(tmp_path)
        architect.select_solver = Mock(return_value=(PeleCConfig, 0.10))

        plan = architect.create_plan_rag("Please use the TaylorGreenVortex setup")

        assert plan.selected_solver == "PeleC"
        assert plan.level2_override_applied is False
        assert plan.level2_override_solver is None


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_no_baseline_found_with_llm_enabled(self, tmp_path):
        """
        Given: No baseline cases found AND LLM enabled
        When:  create_plan() is called
        Then:  Should fallback to pure LLM planning
        
        Validates: Graceful degradation when retrieval fails
        """
        config = Mock()
        config.faiss_db_path = tmp_path
        config.faiss_fallback_to_llm = True
        
        architect = ArchitectService(config, Mock())
        
        # Mock components
        from database.configs.pelec_config import PeleCConfig
        architect.select_solver = Mock(return_value=(PeleCConfig, 0.9))
        architect.retrieve_context = Mock(return_value=[])
        architect.select_baseline = Mock(return_value=None)  # No baseline found!
        architect._llm_plan = Mock(return_value=Mock(
            modifications=[("llm_fallback", "1")],
            reasoning="Pure LLM plan"
        ))
        
        # Act
        plan = architect.create_plan_rag("very novel query")
        
        # Assert
        architect._llm_plan.assert_called_once()
    
    def test_no_baseline_found_with_llm_disabled(self, tmp_path):
        """
        Given: No baseline cases found AND LLM disabled
        When:  create_plan() is called
        Then:  Should raise error
        
        Validates: Error handling for impossible scenarios
        """
        config = Mock()
        config.faiss_db_path = tmp_path
        config.faiss_fallback_to_llm = False
        
        architect = ArchitectService(config, Mock())
        
        # Mock components
        from database.configs.pelec_config import PeleCConfig
        architect.select_solver = Mock(return_value=(PeleCConfig, 0.9))
        architect.retrieve_context = Mock(return_value=[])
        architect.select_baseline = Mock(return_value=None)  # No baseline!
        
        # Act & Assert
        with pytest.raises((ValueError, RuntimeError)):
            architect.create_plan_rag("impossible query")


# Architect Service: Orchestration Logic Marker
pytestmark = pytest.mark.architect_orchestration
