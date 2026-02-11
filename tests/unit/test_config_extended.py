"""
Extended tests for src/config.py - Coverage push to 90%+

Tests the remaining uncovered code:
1. AMReXAgentConfig.amrex_agent_root property
2. Deprecated wrapper methods (test_connection, setup_environment)
3. get_llm_client() function with all providers
4. Error handling and edge cases

Gate 1 Day 1 Phase 2: Achieving 90%+ coverage on config.py
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import warnings

from src.config import AMReXAgentConfig, get_llm_client, unwrap_llm_client


# =============================================================================
# AMReXAgentConfig Properties
# =============================================================================

class TestAMReXAgentConfigProperties:
    """Test computed properties on AMReXAgentConfig."""
    
    def test_amrex_agent_root_returns_repo_root(self):
        """
        Given: A AMReXAgentConfig instance
        When:  Accessing amrex_agent_root property
        Then:  Should return path to repository root (where src/ is)
        
        Technical: config.py is at src/config.py
        So amrex_agent_root = Path(__file__).parent.parent
        
        FIX: It's a @property, not a method - access without ()
        """
        # Arrange
        config = AMReXAgentConfig()
        
        # Act - Access as property, not method
        root = config.amrex_agent_root
        
        # Assert
        assert isinstance(root, Path)
        # Should end with amrex_agent directory name
        assert root.name == "amrex_agent" or root.is_dir()
        # Should contain src/ directory
        assert (root / "src").exists()


# =============================================================================
# Deprecated Method Wrappers
# =============================================================================

class TestDeprecatedConfigMethods:
    """Test backward compatibility of deprecated AMReXAgentConfig methods.
    
    These methods are wrappers that delegate to ConfigService.
    They should work but emit DeprecationWarning.
    """
    
    @patch('src.services.config_service.ConfigService.setup_environment_vars')
    def test_setup_environment_wrapper_emits_warning(self, mock_setup):
        """
        Given: AMReXAgentConfig instance
        When:  Calling deprecated setup_environment() method
        Then:  Should emit DeprecationWarning and delegate to ConfigService
        
        Backward compatibility: Old code still works during transition.
        """
        # Arrange
        config = AMReXAgentConfig(
            cborg_api_key="test-key",
            llm_model="test-model"
        )
        
        # Act & Assert - Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            config.setup_environment()
            
            # Should have emitted deprecation warning
            assert len(w) >= 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            
            # Should have called ConfigService
            assert mock_setup.called
    
    @patch('src.services.config_service.ConfigService.test_llm_connection')
    @patch('src.services.config_service.ConfigService.auto_detect_model')
    @patch('src.services.config_service.ConfigService.load_api_keys')
    def test_test_connection_wrapper_emits_warning(
        self,
        mock_load,
        mock_detect,
        mock_test
    ):
        """
        Given: AMReXAgentConfig instance
        When:  Calling deprecated test_connection() method
        Then:  Should emit DeprecationWarning and delegate to ConfigService
        
        Complex wrapper: Calls multiple ConfigService methods.
        """
        # Arrange
        config = AMReXAgentConfig(
            cborg_api_key="test-key",
            llm_model="test-model"
        )
        
        # Setup mocks
        updated_config = AMReXAgentConfig(
            cborg_api_key="loaded-key",
            llm_model="detected-model"
        )
        mock_load.return_value = updated_config
        mock_detect.return_value = updated_config
        mock_test.return_value = True
        
        # Act & Assert
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            config.test_connection()
            
            # Should emit warning
            assert len(w) >= 1
            assert issubclass(w[0].category, DeprecationWarning)
            
            # Should have called ConfigService methods
            assert mock_load.called
            assert mock_detect.called
            assert mock_test.called


# =============================================================================
# get_llm_client() Function Tests
# =============================================================================

class TestGetLlmClient:
    """Test LLM client factory function.
    
    get_llm_client() returns configured OpenAI client based on provider.
    
    Providers:
    - cborg: OpenAI client pointing to CBORG endpoint
    - alcf: OpenAI client pointing to ALCF endpoint
    - openai: OpenAI client with OpenAI API
    - anthropic: Not implemented (raises NotImplementedError)
    
    PELE-SPECIFIC: Model preference order in CBORG auto-detection
    
    FIX: OpenAI is imported INSIDE get_llm_client(), so mock openai.OpenAI directly
    """
    
    @patch('openai.OpenAI')  # FIX: Mock at import location
    def test_returns_cborg_client_with_api_key(self, mock_openai_class):
        """
        Given: Config with cborg provider and API key
        When:  get_llm_client() is called
        Then:  Should return OpenAI client configured for CBORG
        
        CBORG uses OpenAI-compatible API at LBL endpoint.
        """
        # Arrange
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="test-cborg-key",
            llm_model="llama-70b"  # Model already set
        )
        
        # Act
        result = get_llm_client(config)
        
        # Assert
        mock_openai_class.assert_called_once_with(
            api_key="test-cborg-key",
            base_url="https://api.cborg.lbl.gov/v1"
        )
        assert unwrap_llm_client(result) == mock_client
    
    @patch('openai.OpenAI')
    def test_cborg_auto_detects_model_when_not_set(self, mock_openai_class):
        """
        Given: CBORG config without llm_model specified
        When:  get_llm_client() is called
        Then:  Should query API for models and auto-select best one
        
        PELE-SPECIFIC: Preference order is combustion-oriented
        (but works for any scientific workload)
        """
        # Arrange
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock models.list() response
        mock_models = [
            Mock(id='gpt-4'),
            Mock(id='llama-3.1-70b-instruct'),
            Mock(id='claude-sonnet-4'),
        ]
        mock_client.models.list.return_value = mock_models
        
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="test-key"
            # No llm_model set - should auto-detect
        )
        
        # Act
        result = get_llm_client(config)
        
        # Assert - Should have selected llama (preferred)
        assert config.llm_model == 'llama-3.1-70b-instruct'
        assert mock_client.models.list.called
    
    @patch('openai.OpenAI')
    def test_cborg_prefers_lbl_models(self, mock_openai_class):
        """
        Given: CBORG API returns LBL custom models
        When:  Auto-detection runs
        Then:  Should prefer lbl/* models over standard ones
        
        LBL models are optimized for NERSC scientific workloads.
        """
        # Arrange
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_models = [
            Mock(id='llama-3.1-70b-instruct'),
            Mock(id='lbl/Llama-4-Scout-17B-16E-Instruct'),  # Should pick this
            Mock(id='gpt-4'),
        ]
        mock_client.models.list.return_value = mock_models
        
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="test-key"
        )
        
        # Act
        get_llm_client(config)
        
        # Assert
        assert config.llm_model == 'lbl/Llama-4-Scout-17B-16E-Instruct'
        assert config.llm_model.startswith('lbl/')
    
    @patch('openai.OpenAI')
    def test_cborg_fallback_to_first_model(self, mock_openai_class):
        """
        Given: No preferred models available
        When:  Auto-detection runs
        Then:  Should fall back to first available model
        
        Edge case: Future models not in preference list.
        """
        # Arrange
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_models = [
            Mock(id='unknown-future-model'),
            Mock(id='experimental-v2'),
        ]
        mock_client.models.list.return_value = mock_models
        
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="test-key"
        )
        
        # Act
        get_llm_client(config)
        
        # Assert - Should pick first one
        assert config.llm_model == 'unknown-future-model'
    
    def test_cborg_raises_error_when_no_api_key(self, monkeypatch):
        """
        Given: CBORG config without API key
        When:  get_llm_client() is called
        Then:  Should raise ValueError
        
        Security: Don't allow client creation without credentials.
        
        FIX: Clear environment to prevent picking up real API key
        """
        # Arrange - Clear real environment
        monkeypatch.delenv('CBORG_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        
        config = AMReXAgentConfig(
            llm_provider="cborg"
            # No cborg_api_key
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            get_llm_client(config)
        
        assert "CBORG_API_KEY not set" in str(exc_info.value)
    
    @patch('openai.OpenAI')
    def test_returns_openai_client(self, mock_openai_class):
        """
        Given: Config with openai provider
        When:  get_llm_client() is called
        Then:  Should return OpenAI client with standard API
        
        Fallback provider when CBORG unavailable.
        """
        # Arrange
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        config = AMReXAgentConfig(
            llm_provider="openai",
            openai_api_key="sk-test-openai-key"
        )
        
        # Act
        result = get_llm_client(config)
        
        # Assert
        mock_openai_class.assert_called_once_with(
            api_key="sk-test-openai-key"
        )
        assert unwrap_llm_client(result) == mock_client

    @patch('openai.OpenAI')
    def test_returns_alcf_client(self, mock_openai_class):
        """
        Given: Config with alcf provider and API key
        When:  get_llm_client() is called
        Then:  Should return OpenAI client configured for ALCF
        """
        # Arrange
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        config = AMReXAgentConfig(
            llm_provider="alcf",
            alcf_api_key="test-alcf-key",
            alcf_base_url="https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1"
        )

        # Act
        result = get_llm_client(config)

        # Assert
        mock_openai_class.assert_called_once_with(
            api_key="test-alcf-key",
            base_url="https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1"
        )
        assert unwrap_llm_client(result) == mock_client

    def test_alcf_raises_error_when_no_api_key(self, monkeypatch):
        """
        Given: ALCF config without API key
        When:  get_llm_client() is called
        Then:  Should raise ValueError
        """
        # Arrange - Clear environment
        monkeypatch.delenv('ALCF_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('CBORG_API_KEY', raising=False)

        config = AMReXAgentConfig(
            llm_provider="alcf"
            # No alcf_api_key
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            get_llm_client(config)

        assert "ALCF_API_KEY not set" in str(exc_info.value)
    
    def test_openai_raises_error_when_no_api_key(self, monkeypatch):
        """
        Given: OpenAI config without API key
        When:  get_llm_client() is called
        Then:  Should raise ValueError
        
        FIX: Clear environment to prevent picking up real API key
        """
        # Arrange - Clear environment
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('CBORG_API_KEY', raising=False)
        
        config = AMReXAgentConfig(
            llm_provider="openai"
            # No openai_api_key
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            get_llm_client(config)
        
        assert "OPENAI_API_KEY not set" in str(exc_info.value)
    
    def test_anthropic_raises_not_implemented(self):
        """
        Given: Config with anthropic provider
        When:  get_llm_client() is called
        Then:  Should raise NotImplementedError
        
        Future work: Implement Anthropic client wrapper.
        """
        # Arrange
        config = AMReXAgentConfig(
            llm_provider="anthropic",
            anthropic_api_key="test-key"
        )
        
        # Act & Assert
        with pytest.raises(NotImplementedError) as exc_info:
            get_llm_client(config)
        
        assert "Anthropic provider not yet implemented" in str(exc_info.value)
    
    def test_invalid_provider_raises_error(self):
        """
        Given: Config with invalid provider name
        When:  get_llm_client() is called
        Then:  Should raise ValueError
        
        This shouldn't happen (Pydantic validates), but defensive check.
        """
        # Arrange - Bypass Pydantic validation for test
        config = AMReXAgentConfig(llm_provider="cborg")
        config.llm_provider = "invalid_provider"  # Force invalid value
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            get_llm_client(config)
        
        assert "Unknown LLM provider" in str(exc_info.value)


# =============================================================================
# Integration Tests
# =============================================================================

class TestConfigIntegration:
    """Integration tests for full config workflow.
    
    Tests end-to-end flow: ConfigService.initialize() → get_llm_client()
    """
    
    @patch('openai.OpenAI')  # FIX: Mock at openai module level
    @patch('src.services.config_service.ConfigService.test_llm_connection')
    @patch('src.services.config_service.ConfigService.auto_detect_model')
    @patch('src.services.config_service.ConfigService.load_api_keys')
    def test_full_initialization_to_client_creation(
        self,
        mock_load_keys,
        mock_detect_model,
        mock_test_conn,
        mock_openai_class
    ):
        """
        Integration test: Initialize config and create LLM client.
        
        Given: ConfigService and get_llm_client() working together
        When:  Full workflow runs
        Then:  Should successfully create client
        
        This tests the actual usage pattern in production.
        """
        # Arrange - Setup ConfigService mocks
        initialized_config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="initialized-key",
            llm_model="initialized-model"
        )
        mock_load_keys.return_value = initialized_config
        mock_detect_model.return_value = initialized_config
        mock_test_conn.return_value = True
        
        # Arrange - Setup OpenAI mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Act - Run full workflow
        from src.services.config_service import ConfigService
        service = ConfigService(verbose=False)
        config = service.initialize()
        client = get_llm_client(config)
        
        # Assert - Full chain worked
        assert mock_load_keys.called
        assert mock_detect_model.called
        assert mock_test_conn.called
        assert unwrap_llm_client(client) == mock_client
        
        # Verify client created with correct config
        mock_openai_class.assert_called_with(
            api_key="initialized-key",
            base_url="https://api.cborg.lbl.gov/v1"
        )
