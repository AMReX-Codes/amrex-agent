"""
Unit tests for src/config.py

Gate 0: Testing detect_environment() with 100% coverage
"""

import pytest
from pathlib import Path
from src.config import detect_environment, resolve_database_path, AMReXAgentConfig

from unittest.mock import patch

class TestDetectEnvironment:
    """Test environment detection logic"""
    
    def test_detects_perlmutter(self):
        """Should detect Perlmutter when NERSC_HOST is set"""
        # Arrange
        env = {'NERSC_HOST': 'perlmutter'}
        
        # Act
        result = detect_environment(env)
        
        # Assert
        assert result == 'perlmutter'
    
    def test_detects_mcp(self):
        """Should detect MCP when MCP_SERVER is set"""
        # Arrange
        env = {'MCP_SERVER': 'true'}
        
        # Act
        result = detect_environment(env)
        
        # Assert
        assert result == 'mcp'
    
    def test_detects_local_by_default(self):
        """Should detect local when no special env vars set"""
        # Arrange
        env = {}
        
        # Act
        result = detect_environment(env)
        
        # Assert
        assert result == 'local'
    
    def test_perlmutter_takes_precedence_over_mcp(self):
        """When both are set, Perlmutter should win (if-elif logic)"""
        # Arrange
        env = {
            'NERSC_HOST': 'perlmutter',
            'MCP_SERVER': 'true'
        }
        
        # Act
        result = detect_environment(env)
        
        # Assert
        assert result == 'perlmutter'
    
    def test_ignores_other_env_vars(self):
        """Should not be affected by unrelated env vars"""
        # Arrange
        env = {
            'PATH': '/usr/bin',
            'HOME': '/home/user',
            'RANDOM_VAR': 'value'
        }
        
        # Act
        result = detect_environment(env)
        
        # Assert
        assert result == 'local'
    
    def test_uses_os_environ_when_no_arg(self, monkeypatch):
        """When called with no args, should use os.environ"""
        # Arrange - set real environment variable
        monkeypatch.setenv('NERSC_HOST', 'perlmutter')
        
        # Act - call without arguments
        result = detect_environment()
        
        # Assert
        assert result == 'perlmutter'


class TestResolveDatabasePath:
    """Test database path resolution across environments"""
    
    def test_uses_override_when_set(self, monkeypatch):
        """Should use AMREX_DATABASE_PATH when set (highest priority)"""
        # Arrange
        monkeypatch.setenv('AMREX_DATABASE_PATH', '/custom/database')
        
        # Act
        from src.config import resolve_database_path
        result = resolve_database_path('faiss')
        
        # Assert
        assert result == Path('/custom/database/faiss')
    
    def test_resolves_perlmutter_path(self, monkeypatch):
        """Should use CFS path on Perlmutter"""
        # Arrange
        monkeypatch.setenv('NERSC_HOST', 'perlmutter')
        monkeypatch.delenv('AMREX_DATABASE_PATH', raising=False)
        monkeypatch.delenv('PELE_DATABASE_PATH', raising=False)
        
        # Act
        from src.config import resolve_database_path
        result = resolve_database_path('reports')
        
        # Assert
        expected = Path('/global/cfs/cdirs/mp111/jmsexton/test_pelec_sf/amrex_agent/database/reports')
        assert result == expected
    
    def test_resolves_mcp_path(self, monkeypatch):
        """Should use ~/.amrex_agent on MCP"""
        # Arrange
        monkeypatch.setenv('MCP_SERVER', 'true')
        monkeypatch.delenv('NERSC_HOST', raising=False)
        monkeypatch.delenv('AMREX_DATABASE_PATH', raising=False)
        monkeypatch.delenv('PELE_DATABASE_PATH', raising=False)
        
        # Act
        from src.config import resolve_database_path
        result = resolve_database_path('faiss')
        
        # Assert
        expected = Path.home() / '.amrex_agent' / 'database' / 'faiss'
        assert result == expected
    
    def test_resolves_local_path(self, monkeypatch):
        """Should use relative path locally"""
        # Arrange - clear all environment vars
        monkeypatch.delenv('NERSC_HOST', raising=False)
        monkeypatch.delenv('MCP_SERVER', raising=False)
        monkeypatch.delenv('AMREX_DATABASE_PATH', raising=False)
        monkeypatch.delenv('PELE_DATABASE_PATH', raising=False)
        
        # Act
        from src.config import resolve_database_path
        result = resolve_database_path('testdata')
        
        # Assert
        # The function calculates: Path(__file__).parent.parent.parent / 'database' / relative_path
        # Since config.py is at src/config.py, parent.parent.parent gives repo root
        # We need absolute path
        config_file = Path('src/config.py').resolve()  # Make absolute
        repo_root = config_file.parent.parent
        expected = repo_root / 'database' / 'testdata'
        assert result == expected
    
    def test_override_takes_precedence_over_perlmutter(self, monkeypatch):
        """Override should win even on Perlmutter"""
        # Arrange
        monkeypatch.setenv('AMREX_DATABASE_PATH', '/override/path')
        monkeypatch.setenv('NERSC_HOST', 'perlmutter')
        
        # Act
        from src.config import resolve_database_path
        result = resolve_database_path('test')
        
        # Assert
        assert result == Path('/override/path/test')
        assert 'cfs' not in str(result)  # Should NOT use Perlmutter path


# =============================================================================
# Additional Coverage Tests - Gate 1 Phase 2
# =============================================================================

class TestDetectEnvironmentDefaultParameter:
    """Test detect_environment() with default env parameter.
    
    Missing coverage: Lines 29-31 (env=None default case)
    """
    
    def test_detect_environment_with_no_parameter_uses_os_environ(self, monkeypatch):
        """
        Given: detect_environment() called without env parameter
        When:  env defaults to None
        Then:  Should use os.environ as fallback
        
        Coverage: Lines 29-31 (if env is None: env = dict(os.environ))
        """
        # Arrange - Set real environment
        monkeypatch.setenv('NERSC_HOST', 'perlmutter')
        
        # Act - Call without env parameter (uses default None)
        result = detect_environment()
        
        # Assert
        assert result == 'perlmutter'
    
    def test_detect_environment_mcp_branch(self, monkeypatch):
        """
        Given: MCP_SERVER environment variable set
        When:  detect_environment() called
        Then:  Should return 'mcp'
        
        Coverage: Line 34 (elif env.get('MCP_SERVER'))
        """
        # Arrange
        monkeypatch.delenv('NERSC_HOST', raising=False)
        monkeypatch.setenv('MCP_SERVER', 'true')
        
        # Act
        result = detect_environment()
        
        # Assert
        assert result == 'mcp'


class TestResolveDatabasePathEnvironments:
    """Test resolve_database_path() for different environments.
    
    Missing coverage: Lines 68, 74-75, 79 (perlmutter and mcp paths)
    """
    
    def test_perlmutter_database_path(self, monkeypatch):
        """
        Given: Running on Perlmutter (NERSC_HOST set)
        When:  resolve_database_path() called
        Then:  Should return Perlmutter CFS path
        
        Coverage: Lines 74-75 (if env == 'perlmutter')
        """
        # Arrange
        monkeypatch.setenv('NERSC_HOST', 'perlmutter')
        monkeypatch.delenv('PELE_AGENT_DB_PATH', raising=False)
        
        # Act
        result = resolve_database_path('faiss')
        
        # Assert
        assert '/global/cfs/cdirs' in str(result)
        assert 'amrex_agent/database/faiss' in str(result)
    
    def test_mcp_database_path(self, monkeypatch):
        """
        Given: Running on MCP (MCP_SERVER set)
        When:  resolve_database_path() called
        Then:  Should return user's home directory path
        
        Coverage: Lines 78-79 (elif env == 'mcp')
        """
        # Arrange
        monkeypatch.delenv('NERSC_HOST', raising=False)
        monkeypatch.setenv('MCP_SERVER', 'true')
        monkeypatch.delenv('PELE_AGENT_DB_PATH', raising=False)
        
        # Act
        result = resolve_database_path('reports')
        
        # Assert
        assert '.amrex_agent/database/reports' in str(result)
        assert result.is_absolute()


class TestLoadConfigDeprecated:
    """Test deprecated load_config() function.
    
    Missing coverage: Lines 396-405 (load_config body)
    """
    
    @patch('src.services.config_service.ConfigService.setup_environment_vars')
    @patch('src.services.config_service.ConfigService.test_llm_connection')
    @patch('src.services.config_service.ConfigService.auto_detect_model')
    @patch('src.services.config_service.ConfigService.load_api_keys')
    def test_load_config_actually_calls_config_service(
        self,
        mock_load_keys,
        mock_detect_model,
        mock_test_connection,
        mock_setup_env
    ):
        """
        Given: Deprecated load_config() function
        When:  Function is called
        Then:  Should delegate to ConfigService.initialize()
        
        Coverage: Lines 396-405 (full function body)
        
        This test actually CALLS load_config() (previous test just checked callable).
        """
        import warnings
        from src.config import load_config
        
        # Arrange - Mock ConfigService methods
        mock_config = AMReXAgentConfig(
            cborg_api_key="test-key",
            llm_model="test-model"
        )
        mock_load_keys.return_value = mock_config
        mock_detect_model.return_value = mock_config
        mock_test_connection.return_value = True
        
        # Act - Actually call the function
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            result = load_config()
            
            # Assert - Warning emitted
            assert len(w) >= 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "load_config() is deprecated" in str(w[0].message)
            
            # Assert - ConfigService methods called
            assert mock_load_keys.called
            assert mock_detect_model.called
            assert mock_test_connection.called
            assert mock_setup_env.called
            
            # Assert - Returns config
            assert isinstance(result, AMReXAgentConfig)
