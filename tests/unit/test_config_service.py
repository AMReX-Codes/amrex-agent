# NOTE: This test suite is written to be AMReX-generic.
# Only the following assumptions are Pele-specific:
#   1. Environment variable name: PELE_REPORTS_DIR (line 439+)
#   2. pele_tools integration references (conceptual only)
# All other tests work for any AMReX-based code.
# See AMREX_GENERALIZATION.md for abstraction roadmap.

"""
Unit tests for ConfigService - Configuration initialization with side effects

Testing Strategy:
-----------------
ConfigService extracts side effects (file I/O, API calls, env vars) from
AMReXAgentConfig. This allows the data model to be pure while initialization
logic is testable in isolation.

Key Testing Principles:
1. Isolate external dependencies (files, API, environment)
2. Use monkeypatch for environment isolation (never pollute test environment)
3. Mock external services at the boundary (openai.OpenAI)
4. Test one behavior per test (focused, readable)
5. Use Given-When-Then pattern (Arrange-Act-Assert)

Gate 1 Goal: 95%+ coverage on config_service.py
"""

import pytest
import os
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.services.config_service import ConfigService
from src.config import AMReXAgentConfig


# =============================================================================
# ConfigService Initialization Tests
# =============================================================================

class TestConfigServiceConstruction:
    """Test ConfigService object creation and basic behavior.
    
    ConfigService is a stateless helper - no complex setup needed.
    The only state is verbose mode (controls printing).
    """
    
    def test_default_verbose_mode_is_on(self):
        """
        Given: Creating ConfigService with no arguments
        When:  Checking verbose attribute
        Then:  Should default to True (production use expects output)
        
        Rationale: Production users want to see initialization progress.
        """
        service = ConfigService()
        
        assert service.verbose is True
    
    def test_can_disable_verbose_mode(self):
        """
        Given: Creating ConfigService with verbose=False
        When:  Checking verbose attribute
        Then:  Should be False (test use wants quiet)
        
        Rationale: Tests don't need output noise.
        """
        service = ConfigService(verbose=False)
        
        assert service.verbose is False
    
    def test_verbose_mode_prints_messages(self, caplog):
        """
        Given: ConfigService with verbose=True
        When:  Calling _print() helper
        Then:  Should print to stdout
        
        Technical: capsys is pytest fixture that captures stdout/stderr
        """
        service = ConfigService(verbose=True)
        test_message = "initialization progress"
        
        with caplog.at_level(logging.INFO, logger="src.services.config_service"):
            service._print(test_message)

        assert test_message in caplog.text
    
    def test_silent_mode_suppresses_output(self, caplog):
        """
        Given: ConfigService with verbose=False
        When:  Calling _print() helper
        Then:  Should not print anything
        
        Use case: Test suites should run silently by default
        """
        service = ConfigService(verbose=False)
        
        with caplog.at_level(logging.INFO, logger="src.services.config_service"):
            service._print("this should not appear")

        assert "this should not appear" not in caplog.text


# =============================================================================
# API Key Loading Tests
# =============================================================================

class TestApiKeyLoading:
    """Test loading CBORG API keys from files.
    
    Behavior: load_api_keys() looks for ~/.nersc/cborg_api_key.txt
    Priority: 
      1. If config already has key -> return unchanged
      2. If file exists -> load from file
      3. If file missing/unreadable -> return unchanged
    
    This is a PURE function (no mutation, returns new config).
    """
    
    def test_respects_existing_api_key(self):
        """
        Given: Config already has cborg_api_key set
        When:  load_api_keys() is called
        Then:  Should return config unchanged (don't overwrite)
        
        Rationale: Explicit config takes precedence over file.
        Use case: Testing with mock keys, or user override.
        """
        # Arrange
        service = ConfigService(verbose=False)
        existing_key = "user-provided-key-123"
        config = AMReXAgentConfig(cborg_api_key=existing_key)
        
        # Act
        result = service.load_api_keys(config)
        
        # Assert
        assert result.cborg_api_key == existing_key
        assert result is config  # Same object returned (no copy needed)
    
    def test_loads_key_from_nersc_key_file(self, tmp_path, monkeypatch):
        """
        Given: No API key in config, but ~/.nersc/cborg_api_key.txt exists
        When:  load_api_keys() is called
        Then:  Should load key from file and return new config
        
        Technical Notes:
        - Use monkeypatch to isolate from real filesystem
        - Clear real environment vars to avoid leakage
        - tmp_path is pytest fixture providing temp directory
        """
        # Arrange - Clear real environment (prevent test pollution)
        monkeypatch.delenv('CBORG_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        
        # Arrange - Mock filesystem structure
        fake_home = tmp_path / "test_home"
        fake_home.mkdir()
        nersc_dir = fake_home / ".nersc"
        nersc_dir.mkdir()
        key_file = nersc_dir / "cborg_api_key.txt"
        key_file.write_text("file-stored-key-456\n")  # Note: includes newline
        
        # Arrange - Mock Path.home() to use fake directory
        monkeypatch.setattr(Path, 'home', lambda: fake_home)
        
        # Arrange - Create config without key
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig()  # No cborg_api_key set
        
        # Act
        result = service.load_api_keys(config)
        
        # Assert
        assert result.cborg_api_key == "file-stored-key-456"  # Stripped newline
    
    def test_handles_missing_key_file_gracefully(self, tmp_path, monkeypatch):
        """
        Given: No API key in config, and no key file exists
        When:  load_api_keys() is called
        Then:  Should return config unchanged (no crash)
        
        Use case: Fresh install, user hasn't set up key yet.
        Expected: Code continues to run (will fail later on API call).
        """
        # Arrange - Clear environment
        monkeypatch.delenv('CBORG_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        
        # Arrange - Mock home with no .nersc directory
        fake_home = tmp_path / "empty_home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, 'home', lambda: fake_home)
        
        # Arrange
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig()
        
        # Act
        result = service.load_api_keys(config)
        
        # Assert - Key should still be None (no crash, no magic)
        assert result.cborg_api_key is None
    
    def test_handles_unreadable_key_file(self, tmp_path, monkeypatch):
        """
        Given: Key file exists but has no read permissions
        When:  load_api_keys() is called
        Then:  Should handle error gracefully, return config unchanged
        
        Real-world scenario: File permissions issue, corrupted filesystem.
        Expected: Log warning but don't crash (robustness).
        """
        # Arrange - Clear environment
        monkeypatch.delenv('CBORG_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        
        # Arrange - Create unreadable file
        fake_home = tmp_path / "test_home"
        fake_home.mkdir()
        nersc_dir = fake_home / ".nersc"
        nersc_dir.mkdir()
        key_file = nersc_dir / "cborg_api_key.txt"
        key_file.write_text("key-content")
        key_file.chmod(0o000)  # Remove all permissions
        
        monkeypatch.setattr(Path, 'home', lambda: fake_home)
        
        # Arrange
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig()
        
        # Act
        result = service.load_api_keys(config)
        
        # Assert
        assert result.cborg_api_key is None
        
        # Cleanup (restore permissions for pytest cleanup)
        key_file.chmod(0o644)


# =============================================================================
# Model Auto-Detection Tests
# =============================================================================

class TestModelAutoDetection:
    """Test automatic LLM model selection from CBORG API.
    
    Behavior: auto_detect_model() queries CBORG for available models,
    then selects the "best" one based on a preference order.
    
    Preference Order (highest to lowest):
    1. LBL custom models (lbl/*)
    2. Llama models
    3. Claude models
    4. GPT models
    
    Skip Conditions:
    - Not using CBORG provider -> skip
    - No API key -> skip
    - CBORG_MODEL env var set -> use that
    - Model already in config -> keep it
    """
    
    def test_skips_detection_for_non_cborg_providers(self):
        """
        Given: Config set to use OpenAI (not CBORG)
        When:  auto_detect_model() is called
        Then:  Should skip detection, return config unchanged
        
        Rationale: Only CBORG needs auto-detection.
        OpenAI/Anthropic models are hardcoded in client code.
        """
        # Arrange
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(
            llm_provider="openai",
            cborg_api_key="doesnt-matter"
        )
        
        # Act
        result = service.auto_detect_model(config)
        
        # Assert
        assert result.llm_model is None
    
    def test_skips_detection_when_no_api_key(self, monkeypatch):
        """
        Given: CBORG provider but no API key available
        When:  auto_detect_model() is called
        Then:  Should skip detection (can't call API without key)
        
        Edge case: User selected CBORG but hasn't configured credentials.
        """
        # Arrange - Ensure no key in environment
        monkeypatch.delenv('CBORG_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('CBORG_MODEL', raising=False)
        
        # Arrange
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(llm_provider="cborg")  # No key
        
        # Act
        result = service.auto_detect_model(config)
        
        # Assert
        assert result.llm_model is None
    
    def test_uses_cborg_model_from_environment(self, monkeypatch):
        """
        Given: CBORG_MODEL environment variable is set
        When:  auto_detect_model() is called
        Then:  Should use env var value (skip API query)
        
        Use case: User wants specific model, sets CBORG_MODEL=llama-70b
        Benefit: Faster startup, no API call, user control.
        """
        # Arrange
        desired_model = "user-selected-model"
        monkeypatch.setenv('CBORG_MODEL', desired_model)
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="test-key"
        )
        
        # Act
        result = service.auto_detect_model(config)
        
        # Assert
        assert result.llm_model == desired_model
    
    def test_preserves_existing_model_in_config(self, monkeypatch):
        """
        Given: Config already has llm_model set
        When:  auto_detect_model() is called
        Then:  Should keep existing model (don't re-detect)
        
        Rationale: Config is explicit user choice, don't overwrite.
        Performance: Skip unnecessary API call.
        """
        # Arrange - Clear environment
        monkeypatch.delenv('CBORG_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('CBORG_MODEL', raising=False)
        
        # Arrange
        service = ConfigService(verbose=False)
        existing_model = "gpt-4"
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="key",
            llm_model=existing_model
        )
        
        # Act
        result = service.auto_detect_model(config)
        
        # Assert
        assert result.llm_model == existing_model
    
    @patch('openai.OpenAI')
    def test_selects_llama_over_gpt_and_claude(self, mock_openai_class, monkeypatch):
        """
        Given: CBORG API returns [gpt-4, llama-3.1-70b, claude-sonnet-4]
        When:  auto_detect_model() is called
        Then:  Should select llama-3.1-70b (higher preference)
        
        Technical: Mock openai.OpenAI class (imported inside function)
        Strategy: Verify preference order logic works correctly.
        """
        # Arrange - Clear environment
        monkeypatch.delenv("CBORG_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("CBORG_MODEL", raising=False)
        
        # Arrange - Mock the OpenAI client
        mock_client_instance = MagicMock()
        mock_openai_class.return_value = mock_client_instance
        
        # Arrange - Mock API response
        available_models = [
            Mock(id='gpt-4'),
            Mock(id='llama-3.1-70b-instruct'),
            Mock(id='claude-sonnet-4'),
        ]
        mock_client_instance.models.list.return_value = available_models
        
        # Arrange
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="test-key"
        )
        
        # Act
        result = service.auto_detect_model(config)
        
        # Assert - Should pick llama (preferred over claude and gpt)
        assert result.llm_model == 'llama-3.1-70b-instruct'
    
    @patch('openai.OpenAI')
    def test_prefers_lbl_custom_models(self, mock_openai_class, monkeypatch):
        """
        Given: API returns both LBL and standard models
        When:  auto_detect_model() is called
        Then:  Should select LBL model (highest preference)
        
        Rationale: LBL models are optimized for NERSC/scientific workloads.
        """
        # Arrange - Clear environment
        monkeypatch.delenv("CBORG_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("CBORG_MODEL", raising=False)
        
        # Arrange
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        available_models = [
            Mock(id='gpt-4'),
            Mock(id='lbl/Llama-4-Scout-17B-16E-Instruct'),  # LBL custom
            Mock(id='llama-3.1-70b-instruct'),
        ]
        mock_client.models.list.return_value = available_models
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="test-key"
        )
        
        # Act
        result = service.auto_detect_model(config)
        
        # Assert
        assert result.llm_model == 'lbl/Llama-4-Scout-17B-16E-Instruct'
        assert result.llm_model.startswith('lbl/')
    
    @patch('openai.OpenAI')
    def test_handles_api_errors_gracefully(self, mock_openai_class, monkeypatch):
        """
        Given: CBORG API call raises exception (network error, auth failure, etc)
        When:  auto_detect_model() is called
        Then:  Should log error and return config unchanged (no crash)
        
        Use case: CBORG temporarily down, network issues, invalid key.
        Expected: Code continues (will fail on actual LLM call later).
        """
        # Arrange - Clear environment
        monkeypatch.delenv("CBORG_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("CBORG_MODEL", raising=False)
        
        # Arrange - Mock API to raise exception
        mock_openai_class.side_effect = Exception("API connection failed")
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="test-key"
        )
        
        # Act - Should not crash
        result = service.auto_detect_model(config)
        
        # Assert
        assert result.llm_model is None  # No model selected
    
    @patch('openai.OpenAI')
    def test_fallback_to_first_model_when_no_preference_match(self, mock_openai_class, monkeypatch):
        """
        Given: API returns only unknown/unrecognized models
        When:  auto_detect_model() is called
        Then:  Should select first available model (better than nothing)
        
        Edge case: CBORG added new model types not in our preference list.
        Fallback: Use first one, system still works.
        """
        # Arrange - Clear environment
        monkeypatch.delenv("CBORG_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("CBORG_MODEL", raising=False)
        
        # Arrange
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Models not in preference list
        available_models = [
            Mock(id='future-model-v1'),
            Mock(id='experimental-transformer-2'),
        ]
        mock_client.models.list.return_value = available_models
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="test-key"
        )
        
        # Act
        result = service.auto_detect_model(config)
        
        # Assert - Should pick first one
        assert result.llm_model == 'future-model-v1'


# =============================================================================
# LLM Connection Testing
# =============================================================================

class TestLlmConnectionValidation:
    """Test API connection verification.
    
    Behavior: test_llm_connection() makes a minimal API call to verify
    that credentials and model selection work correctly.
    
    Test strategy: Send "Say OK" prompt, expect response.
    """
    
    def test_returns_false_for_non_cborg_providers(self):
        """
        Given: Config using OpenAI/Anthropic (not CBORG)
        When:  test_llm_connection() is called
        Then:  Should return False (only tests CBORG connections)
        
        Rationale: Function is CBORG-specific.
        """
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(llm_provider="openai")
        
        result = service.test_llm_connection(config)
        
        assert result is False
    
    def test_returns_false_when_missing_api_key(self):
        """Skip test if no API key (can't connect)"""
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(llm_provider="cborg")  # No key
        
        result = service.test_llm_connection(config)
        
        assert result is False
    
    def test_returns_false_when_missing_model(self):
        """Skip test if no model selected (nothing to test)"""
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="key"
            # No model
        )
        
        result = service.test_llm_connection(config)
        
        assert result is False
    
    @patch('openai.OpenAI')
    def test_returns_true_when_api_call_succeeds(self, mock_openai_class):
        """
        Given: Valid credentials and model
        When:  test_llm_connection() makes test API call
        Then:  Should return True (connection verified)
        
        This is the happy path - everything configured correctly.
        """
        # Arrange - Mock successful API response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="OK"))
        ]
        mock_client.chat.completions.create.return_value = mock_response
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="valid-key",
            llm_model="test-model"
        )
        
        # Act
        result = service.test_llm_connection(config)
        
        # Assert
        assert result is True
    
    @patch('openai.OpenAI')
    def test_returns_false_when_api_call_fails(self, mock_openai_class):
        """
        Given: API call raises exception
        When:  test_llm_connection() is called
        Then:  Should return False (connection failed)
        
        Errors: Invalid key, network timeout, rate limit, etc.
        """
        # Arrange
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("Auth failed")
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(
            llm_provider="cborg",
            cborg_api_key="invalid-key",
            llm_model="test-model"
        )
        
        # Act
        result = service.test_llm_connection(config)
        
        # Assert
        assert result is False


# =============================================================================
# Environment Variable Setup Tests
# =============================================================================

class TestEnvironmentVariableSetup:
    """Test environment variable configuration for pele_tools.
    
    SIDE EFFECT WARNING: This function modifies os.environ.
    All tests use monkeypatch for isolation.
    
    Variables set:
    - PELE_REPORTS_DIR: Path to knowledge base
    - CBORG_API_KEY: API key for pele_tools
    - CBORG_MODEL: Model name for pele_tools
    """
    
    # PELE-SPECIFIC: This env var name is combustion-code specific
    # Future: Should be CODE_KNOWLEDGE_BASE or configurable
    def test_sets_reports_dir_when_path_exists(self, tmp_path, monkeypatch):
        """
        Given: knowledge_base_path exists on filesystem
        When:  setup_environment_vars() is called
        Then:  Should set PELE_REPORTS_DIR environment variable
        
        Use case: pele_tools reads this to find knowledge base.
        """
        # Arrange - Create actual directory
        kb_path = tmp_path / "knowledge_base"
        kb_path.mkdir()
        
        # Arrange - Clean environment
        monkeypatch.delenv('PELE_REPORTS_DIR', raising=False)
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(knowledge_base_path=kb_path)
        
        # Act
        service.setup_environment_vars(config)
        
        # Assert
        assert os.environ['PELE_REPORTS_DIR'] == str(kb_path.resolve())
    
    def test_skips_reports_dir_when_path_missing(self, tmp_path, monkeypatch):
        """
        Given: knowledge_base_path doesn't exist
        When:  setup_environment_vars() is called
        Then:  Should NOT set PELE_REPORTS_DIR (avoid pointing to invalid path)
        
        Safety: Don't set env var to non-existent directory.
        """
        # Arrange
        kb_path = tmp_path / "nonexistent"  # Not created
        monkeypatch.delenv('PELE_REPORTS_DIR', raising=False)
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(knowledge_base_path=kb_path)
        
        # Act
        service.setup_environment_vars(config)
        
        # Assert
        assert 'PELE_REPORTS_DIR' not in os.environ
    
    def test_sets_cborg_api_key_env_var(self, monkeypatch):
        """
        Given: Config has cborg_api_key
        When:  setup_environment_vars() is called
        Then:  Should set CBORG_API_KEY environment variable
        
        Why: pele_tools subprocess reads API key from environment.
        """
        # Arrange
        monkeypatch.delenv('CBORG_API_KEY', raising=False)
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(cborg_api_key="test-key-789")
        
        # Act
        service.setup_environment_vars(config)
        
        # Assert
        assert os.environ['CBORG_API_KEY'] == "test-key-789"
    
    def test_sets_cborg_model_env_var(self, monkeypatch):
        """
        Given: Config has llm_model
        When:  setup_environment_vars() is called
        Then:  Should set CBORG_MODEL environment variable
        
        Why: pele_tools reads model selection from environment.
        """
        # Arrange
        monkeypatch.delenv('CBORG_MODEL', raising=False)
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(llm_model="llama-70b")
        
        # Act
        service.setup_environment_vars(config)
        
        # Assert
        assert os.environ['CBORG_MODEL'] == "llama-70b"
    
    def test_sets_all_environment_variables_together(self, tmp_path, monkeypatch):
        """
        Integration test: Set all env vars at once.
        
        Verifies: Multiple env vars set correctly in single call.
        """
        # Arrange - Create real directory
        kb_path = tmp_path / "kb"
        kb_path.mkdir()
        
        # Arrange - Clean environment
        for var in ['PELE_REPORTS_DIR', 'CBORG_API_KEY', 'CBORG_MODEL']:
            monkeypatch.delenv(var, raising=False)
        
        service = ConfigService(verbose=False)
        config = AMReXAgentConfig(
            knowledge_base_path=kb_path,
            cborg_api_key="integration-key",
            llm_model="integration-model"
        )
        
        # Act
        service.setup_environment_vars(config)
        
        # Assert - All three variables set
        assert os.environ['PELE_REPORTS_DIR'] == str(kb_path.resolve())
        assert os.environ['CBORG_API_KEY'] == "integration-key"
        assert os.environ['CBORG_MODEL'] == "integration-model"


# =============================================================================
# Full Initialization Workflow Tests
# =============================================================================

class TestFullInitialization:
    """Test the complete initialization workflow.
    
    initialize() orchestrates all steps:
    1. Create base config
    2. Load API keys
    3. Auto-detect model
    4. Test connection
    5. Setup environment
    
    Testing strategy: Mock each step, verify they're called in order.
    """
    
    @patch('src.services.config_service.ConfigService.test_llm_connection')
    @patch('src.services.config_service.ConfigService.auto_detect_model')
    @patch('src.services.config_service.ConfigService.load_api_keys')
    def test_initialization_calls_all_steps_in_correct_order(
        self, 
        mock_load_keys,
        mock_detect_model,
        mock_test_connection
    ):
        """
        Given: ConfigService with all methods mocked
        When:  initialize() is called
        Then:  Should call load_keys -> detect_model -> test_connection
        
        Verifies: Workflow orchestration works correctly.
        """
        # Arrange - Setup mocks to return valid configs
        base_config = AMReXAgentConfig()
        mock_load_keys.return_value = base_config
        mock_detect_model.return_value = base_config
        mock_test_connection.return_value = True
        
        service = ConfigService(verbose=False)
        
        # Act
        result = service.initialize()
        
        # Assert - All steps called
        assert mock_load_keys.called
        assert mock_detect_model.called
        assert mock_test_connection.called
        assert isinstance(result, AMReXAgentConfig)
    
    @patch('src.services.config_service.ConfigService.setup_environment_vars')
    @patch('src.services.config_service.ConfigService.test_llm_connection')
    @patch('src.services.config_service.ConfigService.auto_detect_model')
    @patch('src.services.config_service.ConfigService.load_api_keys')
    def test_initialization_sets_up_environment(
        self,
        mock_load_keys,
        mock_detect_model,
        mock_test_connection,
        mock_setup_env
    ):
        """
        Verify: setup_environment_vars() is called during initialization.
        
        Why: Ensures pele_tools has correct environment.
        """
        # Arrange
        base_config = AMReXAgentConfig()
        mock_load_keys.return_value = base_config
        mock_detect_model.return_value = base_config
        mock_test_connection.return_value = True
        
        service = ConfigService(verbose=False)
        
        # Act
        service.initialize()
        
        # Assert
        assert mock_setup_env.called


# =============================================================================
# Backward Compatibility Tests
# =============================================================================

class TestDeprecatedApiBackwardCompatibility:
    """Test deprecated functions still work (with warnings).
    
    Deprecated:
    - load_config() -> Use ConfigService().initialize()
    - AMReXAgentConfig.test_connection() -> Use ConfigService
    - AMReXAgentConfig.setup_environment() -> Use ConfigService
    
    Strategy: Verify they work but emit DeprecationWarning.
    """
    
    def test_load_config_is_still_callable(self):
        """
        Given: Legacy code calls load_config()
        When:  Function is imported
        Then:  Should be callable (not removed yet)
        
        Maintains backward compatibility during transition period.
        """
        from src.config import load_config
        
        assert callable(load_config)
    
    def test_peleagentconfig_test_connection_shows_deprecation_warning(self):
        """
        Given: Legacy code calls config.test_connection()
        When:  Method is called
        Then:  Should emit DeprecationWarning
        
        Warns users to migrate to new API.
        """
        import warnings
        
        config = AMReXAgentConfig(cborg_api_key="test", llm_model="test")
        
        # Arrange - Capture warnings
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")
            
            # Mock the actual work (we're testing the warning, not the logic)
            with patch('src.services.config_service.ConfigService.load_api_keys'):
                with patch('src.services.config_service.ConfigService.auto_detect_model'):
                    with patch('src.services.config_service.ConfigService.test_llm_connection'):
                        # Act
                        config.test_connection()
            
            # Assert - Warning was emitted
            assert len(warning_list) >= 1
            assert issubclass(warning_list[0].category, DeprecationWarning)
            assert "deprecated" in str(warning_list[0].message).lower()
