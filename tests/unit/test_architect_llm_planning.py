"""
Architect Service: LLM Planning: Architect LLM Planning Tests

Validates the generative fallback logic for simulation planning
using LLM with strict schema validation and anti-hallucination checks.

Architecture:
    Low Confidence (6e) → LLM Planning (6f) → Validated Modifications

References:
    - Plan v4.0: Architect Service: LLM Planning
    - PRD Amendment C: Template-based generation
    - Metadata Schema: inputs_content schema
    - pyAMReX: Namespace standards
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Tuple

# Import services
from src.services.architect import ArchitectService


class TestLLMPlanJSONOnly:
    """Test JSON-only enforcement (no conversational drift)."""
    
    def test_llm_plan_json_only(self, tmp_path):
        """
        Given: LLM prompt for modifications
        When:  LLM responds with clean JSON
        Then:  Should parse successfully without markdown stripping
        
        Validates: Tool-oriented prompting (JSON only)
        """
        # Arrange
        config = Mock()
        config.faiss_db_path = tmp_path
        config.llm_temperature = 0.2
        
        embedder = Mock()
        architect = ArchitectService(config, embedder)
        
        # Mock LLM client
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps({
            "modifications": [
                {"parameter": "amr.n_cell", "value": "128 128 128"}
            ],
            "reasoning": "Increased resolution for finer detail"
        })
        mock_llm.chat = Mock(return_value=mock_response)
        architect.llm = mock_llm
        
        # Baseline with valid schema
        baseline_case = {
            'metadata': {
                'inputs_content': {
                    'amr.n_cell': '64 64 64',
                    'amr.max_level': '0'
                }
            }
        }
        
        # Act
        result = architect._llm_plan(
            prompt="Increase resolution",
            solver="AMReX",
            documentation=[],
            cases=[baseline_case]
        )
        
        # Assert
        assert result is not None
        assert len(result.modifications) == 1
        assert result.modifications[0] == ("amr.n_cell", "128 128 128")
        assert "resolution" in result.reasoning.lower()
        
        # Verify temperature setting
        call_args = mock_llm.chat.call_args
        assert call_args[1]['temperature'] == 0.2
    
    def test_strips_markdown_code_blocks(self, tmp_path):
        """
        Given: LLM response wrapped in markdown
        When:  Parser cleans the response
        Then:  Should extract pure JSON
        
        Validates: Robust parsing for common LLM formatting
        """
        config = Mock()
        config.faiss_db_path = tmp_path
        
        architect = ArchitectService(config, Mock())
        
        # Mock LLM with markdown formatting
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''```json
{
    "modifications": [{"parameter": "amr.max_level", "value": "2"}],
    "reasoning": "Added AMR"
}
```'''
        mock_llm.chat = Mock(return_value=mock_response)
        architect.llm = mock_llm
        
        baseline_case = {
            'metadata': {
                'inputs_content': {'amr.max_level': '0'}
            }
        }
        
        # Act
        result = architect._llm_plan(
            prompt="Add AMR",
            solver="AMReX",
            documentation=[],
            cases=[baseline_case]
        )
        
        # Assert - should parse successfully despite markdown
        assert result is not None
        assert len(result.modifications) == 1


class TestValidatesMetadataSchema:
    """Test anti-hallucination via metadata schema validation."""
    
    def test_filters_hallucinated_parameters(self, tmp_path):
        """
        Given: LLM suggests non-existent parameter
        When:  Validation against baseline inputs_content
        Then:  Should filter out invalid parameters
        
        Validates: Metadata Schema schema protection
        """
        config = Mock()
        config.faiss_db_path = tmp_path
        
        architect = ArchitectService(config, Mock())
        
        # Mock LLM suggesting invalid parameter
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps({
            "modifications": [
                {"parameter": "amr.n_cell", "value": "128 128 128"},  # Valid
                {"parameter": "amr.magic_parameter", "value": "42"}   # Invalid!
            ],
            "reasoning": "Test"
        })
        mock_llm.chat = Mock(return_value=mock_response)
        architect.llm = mock_llm
        
        # Baseline with limited schema
        baseline_case = {
            'metadata': {
                'inputs_content': {
                    'amr.n_cell': '64 64 64',
                    'amr.max_level': '0'
                }
            }
        }
        
        # Act
        result = architect._llm_plan(
            prompt="Test",
            solver="AMReX",
            documentation=[],
            cases=[baseline_case]
        )
        
        # Assert - only valid parameter should remain
        assert len(result.modifications) == 1
        assert result.modifications[0][0] == "amr.n_cell"
    
    def test_allows_known_auxiliary_parameters(self, tmp_path):
        """
        Given: LLM suggests chemistry parameters (not in baseline)
        When:  Parameter is in known auxiliary list
        Then:  Should allow the parameter
        
        Validates: Extensibility for adding new features
        """
        config = Mock()
        config.faiss_db_path = tmp_path
        
        architect = ArchitectService(config, Mock())
        
        # Mock LLM suggesting chemistry (baseline is pure hydro)
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps({
            "modifications": [
                {"parameter": "pelec.chem_file", "value": "drm19.dat"},
                {"parameter": "pelec.do_react", "value": "1"}
            ],
            "reasoning": "Adding chemistry"
        })
        mock_llm.chat = Mock(return_value=mock_response)
        architect.llm = mock_llm
        
        # Baseline WITHOUT chemistry
        baseline_case = {
            'metadata': {
                'inputs_content': {
                    'amr.n_cell': '64 64 64'
                }
            }
        }
        
        # Act
        result = architect._llm_plan(
            prompt="Add chemistry",
            solver="PeleC",
            documentation=[],
            cases=[baseline_case]
        )
        
        # Assert - auxiliary params should be allowed
        assert len(result.modifications) == 2
        assert any(p[0] == "pelec.chem_file" for p in result.modifications)


class TestFollowsPyAMReXPatterns:
    """Test AMReX namespace enforcement (pyAMReX standards)."""
    
    def test_enforces_namespace_prefixes(self, tmp_path):
        """
        Given: Parameter names without namespaces
        When:  Validation checks
        Then:  Should reject or warn about missing namespaces
        
        Validates: pyAMReX namespace standards
        """
        config = Mock()
        config.faiss_db_path = tmp_path
        
        architect = ArchitectService(config, Mock())
        
        # Mock LLM with missing namespace
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps({
            "modifications": [
                {"parameter": "n_cell", "value": "128 128 128"}  # Missing 'amr.' prefix!
            ],
            "reasoning": "Test"
        })
        mock_llm.chat = Mock(return_value=mock_response)
        architect.llm = mock_llm
        
        baseline_case = {
            'metadata': {
                'inputs_content': {
                    'amr.n_cell': '64 64 64'
                }
            }
        }
        
        # Act
        result = architect._llm_plan(
            prompt="Test",
            solver="AMReX",
            documentation=[],
            cases=[baseline_case]
        )
        
        # Assert - should filter out namespace-less parameter
        assert len(result.modifications) == 0


class TestExtensibleToPydantic:
    """Test preparation for Input Writer Pydantic migration."""
    
    def test_output_structure_pydantic_ready(self, tmp_path):
        """
        Given: LLM output modifications
        When:  Structure is examined
        Then:  Should be compatible with Pydantic model hydration
        
        Validates: Future Input Writer compatibility
        """
        config = Mock()
        config.faiss_db_path = tmp_path
        
        architect = ArchitectService(config, Mock())
        
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps({
            "modifications": [
                {"parameter": "amr.n_cell", "value": "128 128 128"},
                {"parameter": "amr.max_level", "value": "2"}
            ],
            "reasoning": "Test"
        })
        mock_llm.chat = Mock(return_value=mock_response)
        architect.llm = mock_llm
        
        baseline_case = {
            'metadata': {
                'inputs_content': {
                    'amr.n_cell': '64 64 64',
                    'amr.max_level': '0'
                }
            }
        }
        
        # Act
        result = architect._llm_plan(
            prompt="Test",
            solver="AMReX",
            documentation=[],
            cases=[baseline_case]
        )
        
        # Assert - structure ready for Pydantic
        assert isinstance(result.modifications, list)
        for param, value in result.modifications:
            # Key is string (namespace.name format)
            assert isinstance(param, str)
            assert '.' in param, "Should have namespace prefix"
            
            # Value preserved as string (Pydantic will validate/convert)
            assert isinstance(value, str)


class TestErrorHandlingStructured:
    """Test error handling and recovery (yt-project standards)."""
    
    def test_handles_malformed_json(self, tmp_path):
        """
        Given: LLM returns malformed JSON
        When:  Parser attempts to parse
        Then:  Should return empty result with error logged
        
        Validates: Graceful degradation
        """
        config = Mock()
        config.faiss_db_path = tmp_path
        
        architect = ArchitectService(config, Mock())
        
        # Mock malformed JSON
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '{"modifications": [invalid json'
        mock_llm.chat = Mock(return_value=mock_response)
        architect.llm = mock_llm
        
        baseline_case = {
            'metadata': {
                'inputs_content': {'amr.n_cell': '64 64 64'}
            }
        }
        
        # Act
        with patch('src.services.architect.logger') as mock_logger:
            result = architect._llm_plan(
                prompt="Test",
                solver="AMReX",
                documentation=[],
                cases=[baseline_case]
            )
        
        # Assert - should return empty result, not crash
        assert result is not None
        assert len(result.modifications) == 0
        assert "fail" in result.reasoning.lower() or "parse" in result.reasoning.lower()
        
        # Verify error was logged
        mock_logger.error.assert_called()
    
    def test_returns_partial_results_on_validation_failure(self, tmp_path):
        """
        Given: LLM returns mix of valid/invalid parameters
        When:  Validation filters invalid ones
        Then:  Should return partial valid results
        
        Validates: Best-effort strategy
        """
        config = Mock()
        config.faiss_db_path = tmp_path
        
        architect = ArchitectService(config, Mock())
        
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps({
            "modifications": [
                {"parameter": "amr.n_cell", "value": "128 128 128"},  # Valid
                {"parameter": "fake.parameter", "value": "bad"},       # Invalid
                {"parameter": "amr.max_level", "value": "2"}          # Valid
            ],
            "reasoning": "Test"
        })
        mock_llm.chat = Mock(return_value=mock_response)
        architect.llm = mock_llm
        
        baseline_case = {
            'metadata': {
                'inputs_content': {
                    'amr.n_cell': '64 64 64',
                    'amr.max_level': '0'
                }
            }
        }
        
        # Act
        result = architect._llm_plan(
            prompt="Test",
            solver="AMReX",
            documentation=[],
            cases=[baseline_case]
        )
        
        # Assert - should return 2 valid modifications
        assert len(result.modifications) == 2
        params = [m[0] for m in result.modifications]
        assert 'amr.n_cell' in params
        assert 'amr.max_level' in params
        assert 'fake.parameter' not in params


# Architect Service: LLM Planning Marker
pytestmark = pytest.mark.architect_llm_planning
