"""
Schema Resolution Strategy Tests (Input Writer: Config Model Factory)

Tests dynamic schema path resolution with multiple strategies:
  • newest: Use most recently modified schema
  • exact: Match git hash, rebuild if needed
  • tag: Use specific version tag

TDD: Tests written BEFORE implementation.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import time
from types import SimpleNamespace

class TestSchemaResolutionBasic:
    """Test basic schema path resolution (newest strategy)."""
    
    def test_resolve_basic_schema_path(self, tmp_path):
        """
        Given: Single schema file for solver
        When:  resolve_schema_path() called
        Then:  Returns path to that file
        
        Validates: Basic discovery works
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        # Create mock schema
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        schema_file = schema_dir / "amrex_schema_abc123.json"
        schema_file.write_text('{"parameters": {}}')
        
        # Mock solver config
        mock_config = Mock()
        mock_config.code_name = "AMReX"
        mock_config.schema_strategy = "newest"
        mock_config.schema_pattern = f"{mock_config.code_name.lower()}_schema_*.json"  # Add this!
        
        # Resolve
        result = ConfigModelFactory.resolve_schema_path(
            mock_config,
            schema_dir,
            tmp_path  # repo_path (not used for "newest")
        )
        
        assert result == schema_file
        assert result.exists()
    
    def test_resolve_latest_version_by_mtime(self, tmp_path):
        """
        Given: Multiple schema versions for same solver
        When:  resolve_schema_path() called with "newest" strategy
        Then:  Returns file with most recent modification time
        
        Validates: Newest strategy implementation
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        # Create old schema
        old_schema = schema_dir / "amrex_schema_old.json"
        old_schema.write_text('{"parameters": {}}')
        time.sleep(0.01)  # Ensure different mtime
        
        # Create new schema (more recent)
        new_schema = schema_dir / "amrex_schema_new.json"
        new_schema.write_text('{"parameters": {}}')
        
        # Mock config
        mock_config = Mock()
        mock_config.code_name = "AMReX"
        mock_config.schema_strategy = "newest"
        mock_config.schema_pattern = f"{mock_config.code_name.lower()}_schema_*.json"  # Add this!
        
        # Resolve
        result = ConfigModelFactory.resolve_schema_path(
            mock_config,
            schema_dir,
            tmp_path
        )
        
        # Should return newer file
        assert result == new_schema
    
    def test_schema_not_found(self, tmp_path):
        """
        Given: Empty schema directory
        When:  resolve_schema_path() called
        Then:  Raises FileNotFoundError with helpful message
        
        Validates: Error handling for missing schemas
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        mock_config = Mock()
        mock_config.code_name = "NonExistent"
        mock_config.schema_strategy = "newest"
        mock_config.schema_pattern = f"{mock_config.code_name.lower()}_schema_*.json"
        
        # Should raise with helpful message
        with pytest.raises(FileNotFoundError) as exc:
            ConfigModelFactory.resolve_schema_path(
                mock_config,
                schema_dir,
                tmp_path
            )
        
        # Check error message contains solver name (case-insensitive)
        assert "nonexistent" in str(exc.value).lower()
        assert "schema" in str(exc.value).lower()
    
    def test_solver_name_normalization(self, tmp_path):
        """
        Given: Schema file with lowercase name
        When:  Resolver called with CamelCase name
        Then:  Correctly matches (case-insensitive)
        
        Validates: Solver name normalization
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        # File uses lowercase (build_schema.py convention)
        schema_file = schema_dir / "amrex_schema_abc123.json"
        schema_file.write_text('{"parameters": {}}')
        
        # Config uses CamelCase
        mock_config = Mock()
        mock_config.code_name = "AMReX"  # CamelCase
        mock_config.schema_strategy = "newest"
        mock_config.schema_pattern = f"{mock_config.code_name.lower()}_schema_*.json"
        
        result = ConfigModelFactory.resolve_schema_path(
            mock_config,
            schema_dir,
            tmp_path
        )
        
        assert result == schema_file


class TestSchemaStalenessPolicyIntegration:
    def test_resolve_schema_path_applies_mismatch_policy_when_runtime_config_provided(self, tmp_path):
        from src.services.config_model_factory import ConfigModelFactory

        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        schema_file = schema_dir / "amrex_schema_abc123.json"
        schema_file.write_text('{"parameters": {}}')

        solver_config = Mock()
        solver_config.code_name = "AMReX"
        solver_config.schema_strategy = "newest"
        solver_config.schema_pattern = "amrex_schema_*.json"

        runtime_config = SimpleNamespace(
            database_mismatch_policy="warn_continue",
            repositories={"AMReX": tmp_path},
        )
        fake_report = SimpleNamespace(is_stale=False)

        with patch(
            "src.services.config_model_factory.check_schema_staleness",
            return_value=fake_report,
        ) as mock_check, patch(
            "src.services.config_model_factory.apply_mismatch_policy",
            return_value=SimpleNamespace(proceed=True, rebuild_triggered=False),
        ) as mock_apply:
            result = ConfigModelFactory.resolve_schema_path(
                solver_config,
                schema_dir,
                tmp_path,
                runtime_config=runtime_config,
            )

        assert result == schema_file
        mock_check.assert_called_once()
        mock_apply.assert_called_once()
        assert mock_apply.call_args.kwargs["policy"] == "warn_continue"

    def test_resolve_schema_path_skips_mismatch_policy_without_runtime_config(self, tmp_path):
        from src.services.config_model_factory import ConfigModelFactory

        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        schema_file = schema_dir / "amrex_schema_abc123.json"
        schema_file.write_text('{"parameters": {}}')

        solver_config = Mock()
        solver_config.code_name = "AMReX"
        solver_config.schema_strategy = "newest"
        solver_config.schema_pattern = "amrex_schema_*.json"

        with patch("src.services.config_model_factory.check_schema_staleness") as mock_check, patch(
            "src.services.config_model_factory.apply_mismatch_policy"
        ) as mock_apply:
            result = ConfigModelFactory.resolve_schema_path(
                solver_config,
                schema_dir,
                tmp_path,
            )

        assert result == schema_file
        mock_check.assert_not_called()
        mock_apply.assert_not_called()


class TestSchemaResolutionExactStrategy:
    """Test 'exact' strategy (git hash matching)."""
    
    def test_resolve_strategy_exact_match(self, tmp_path):
        """
        Given: Schema matching current git hash exists
        When:  Strategy is "exact"
        Then:  Returns matching schema (ignores newer files)
        
        Validates: Exact strategy prefers hash match over recency
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        # Create old matching schema
        match_schema = schema_dir / "amrex_schema_abc1234.json"
        match_schema.write_text('{"parameters": {}}')
        time.sleep(0.01)
        
        # Create newer non-matching schema
        newer_schema = schema_dir / "amrex_schema_xyz9876.json"
        newer_schema.write_text('{"parameters": {}}')
        
        # Mock config with exact strategy
        mock_config = Mock()
        mock_config.code_name = "AMReX"
        mock_config.schema_strategy = "exact"
        
        # Mock git hash
        with patch.object(
            ConfigModelFactory,
            '_get_git_hash',
            return_value='abc1234'
        ):
            result = ConfigModelFactory.resolve_schema_path(
                mock_config,
                schema_dir,
                tmp_path
            )
        
        # Should return hash-matching file, NOT newer one
        assert result == match_schema
    
    def test_resolve_strategy_exact_rebuild(self, tmp_path):
        """
        Given: No schema matches current git hash
        When:  Strategy is "exact"
        Then:  Triggers SchemaBuilder to create new schema
        
        Validates: On-demand schema rebuilding
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        # Old schema exists (wrong hash)
        old_schema = schema_dir / "amrex_schema_old.json"
        old_schema.write_text('{"parameters": {}}')
        
        # Mock config
        mock_config = Mock()
        mock_config.code_name = "AMReX"
        mock_config.schema_strategy = "exact"
        
        # Mock SchemaBuilder
        mock_builder = MagicMock()
        new_schema_path = schema_dir / "amrex_schema_beef777.json"
        mock_builder.save.return_value = new_schema_path
        
        with patch.object(
            ConfigModelFactory,
            '_get_git_hash',
            return_value='beef777'
        ), patch(
            'database.scripts.build_schema.SchemaBuilder',
            return_value=mock_builder
        ):
            result = ConfigModelFactory.resolve_schema_path(
                mock_config,
                schema_dir,
                tmp_path
            )
        
        # Should have called builder
        mock_builder.scan_source_code.assert_called_once()
        mock_builder.save.assert_called_once()
        
        # Should return new path
        assert 'beef777' in result.name


class TestSchemaResolutionTagStrategy:
    """Test 'tag' strategy (versioned schemas)."""
    
    def test_resolve_strategy_tag(self, tmp_path):
        """
        Given: Multiple tagged schema versions
        When:  Strategy is "tag" with specific version
        Then:  Returns exactly that tagged version
        
        Validates: Reproducibility via tagged schemas
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        # Create tagged schemas
        v1_schema = schema_dir / "amrex_schema_v1.0.json"
        v1_schema.write_text('{"parameters": {}}')
        
        v2_schema = schema_dir / "amrex_schema_v2.0.json"
        v2_schema.write_text('{"parameters": {}}')
        
        # Mock config requesting v1.0
        mock_config = Mock()
        mock_config.code_name = "AMReX"
        mock_config.schema_strategy = "tag"
        mock_config.schema_tag = "v1.0"
        
        result = ConfigModelFactory.resolve_schema_path(
            mock_config,
            schema_dir,
            tmp_path
        )
        
        # Should return v1.0, not v2.0
        assert result == v1_schema
    
    def test_tag_not_found(self, tmp_path):
        """
        Given: Requested tag doesn't exist
        When:  Strategy is "tag"
        Then:  Raises FileNotFoundError
        
        Validates: Tag validation
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        mock_config = Mock()
        mock_config.code_name = "AMReX"
        mock_config.schema_strategy = "tag"
        mock_config.schema_tag = "nonexistent"
        
        with pytest.raises(FileNotFoundError) as exc:
            ConfigModelFactory.resolve_schema_path(
                mock_config,
                schema_dir,
                tmp_path
            )
        
        assert "nonexistent" in str(exc.value)


class TestGitHashHelper:
    """Test _get_git_hash() helper method."""
    
    def test_get_git_hash_valid_repo(self, tmp_path):
        """
        Given: Valid git repository
        When:  _get_git_hash() called
        Then:  Returns short commit hash
        
        Validates: Git integration works
        """
        from src.services.config_model_factory import ConfigModelFactory
        import subprocess
        
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=tmp_path, check=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@test.com'],
            cwd=tmp_path,
            check=True
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test'],
            cwd=tmp_path,
            check=True
        )
        (tmp_path / 'test.txt').write_text('test')
        subprocess.run(['git', 'add', '.'], cwd=tmp_path, check=True)
        subprocess.run(
            ['git', 'commit', '-m', 'test'],
            cwd=tmp_path,
            check=True
        )
        
        # Get hash
        result = ConfigModelFactory._get_git_hash(tmp_path)
        
        # Should return 7-character hash
        assert len(result) == 7
        assert result.isalnum()
    
    def test_get_git_hash_non_repo(self, tmp_path):
        """
        Given: Directory is not a git repo
        When:  _get_git_hash() called
        Then:  Returns "unknown" (graceful fallback)
        
        Validates: Error handling for non-git directories
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        result = ConfigModelFactory._get_git_hash(tmp_path)
        
        assert result == "unknown"



class TestSchemaResolutionIntegration:
    """Integration tests with real SchemaBuilder (no mocks)."""
    
    @pytest.mark.slow
    def test_exact_strategy_real_rebuild(self, tmp_path):
        """
        Given: No schema exists for current code state
        When:  Strategy is "exact"
        Then:  Actually runs SchemaBuilder and creates schema
        
        Validates: Real integration with Input Writer: Schema Scraper
        Note: This is a REAL test (no mocks) - tests actual SchemaBuilder
        """
        from src.services.config_model_factory import ConfigModelFactory
        
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        # Create a minimal source file for SchemaBuilder to parse
        repo_path = tmp_path / "TestSolver"
        repo_path.mkdir()
        source_dir = repo_path / "Source"
        source_dir.mkdir()
        
        # Create C++ file with ParmParse calls
        cpp_file = source_dir / "test.cpp"
        cpp_code = """
#include <AMReX_ParmParse.H>

void setup() {
    amrex::ParmParse pp("test");
    int n_cells;
    pp.get("n_cells", n_cells);
    
    amrex::Real cfl;
    pp.query("cfl", cfl);
}
"""
        cpp_file.write_text(cpp_code)
        
        # Initialize git repo (needed for hash)
        import subprocess
        subprocess.run(['git', 'init'], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@test.com'],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test'],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(['git', 'add', '.'], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'test'],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        
        # Mock config
        mock_config = Mock()
        mock_config.code_name = "TestSolver"
        mock_config.schema_strategy = "exact"
        
        # Resolve - should trigger real SchemaBuilder
        result = ConfigModelFactory.resolve_schema_path(
            mock_config,
            schema_dir,
            repo_path
        )
        
        # Verify schema file was actually created
        assert result.exists()
        assert result.name.startswith("testsolver_schema_")
        
        # Verify it contains parsed content
        import json
        schema = json.loads(result.read_text())
        
        # SchemaBuilder might wrap in 'parameters' or return flat dict
        params = schema.get('parameters', schema)
        
        # Should have found parameters from parsing
        assert len(params) > 0, "Schema should contain parsed parameters"



# Test marker
pytestmark = pytest.mark.input_writer_config_model_factory


class TestSchemaResolutionIntegration:
    """Integration tests with real SchemaBuilder (no mocks)."""
    
    @pytest.mark.slow
    def test_exact_strategy_real_rebuild(self, tmp_path):
        """
        Given: No schema exists for current code state
        When:  Strategy is "exact"
        Then:  Actually runs SchemaBuilder and creates schema
        
        Validates: Real integration with Input Writer: Schema Scraper
        Note: This is a REAL test (no mocks) - tests actual SchemaBuilder
        """
        from src.services.config_model_factory import ConfigModelFactory
        import subprocess
        import json
        
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        # Create a minimal source file for SchemaBuilder to parse
        repo_path = tmp_path / "TestSolver"
        repo_path.mkdir()
        source_dir = repo_path / "Source"
        source_dir.mkdir()
        
        # Create C++ file with ParmParse calls
        cpp_file = source_dir / "test.cpp"
        cpp_code = """#include <AMReX_ParmParse.H>

void setup() {
    amrex::ParmParse pp("test");
    int n_cells;
    pp.get("n_cells", n_cells);
    
    amrex::Real cfl;
    pp.query("cfl", cfl);
}
"""
        cpp_file.write_text(cpp_code)
        
        # Initialize git repo (needed for hash)
        subprocess.run(['git', 'init'], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@test.com'],
            cwd=repo_path, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test'],
            cwd=repo_path, check=True, capture_output=True
        )
        subprocess.run(['git', 'add', '.'], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'test'],
            cwd=repo_path, check=True, capture_output=True
        )
        
        # Mock config
        mock_config = Mock()
        mock_config.code_name = "TestSolver"
        mock_config.schema_strategy = "exact"
        
        # Resolve - should trigger real SchemaBuilder
        result = ConfigModelFactory.resolve_schema_path(
            mock_config,
            schema_dir,
            repo_path
        )
        
        # Verify schema file was actually created
        assert result.exists(), "Schema file should be created"
        assert result.name.startswith("testsolver_schema_"), f"Schema name wrong: {result.name}"
        
        # Verify it contains parsed content
        schema = json.loads(result.read_text())
        
        # SchemaBuilder might wrap in 'parameters' or return flat dict
        params = schema.get('parameters', schema)
        
        # Should have found parameters from parsing
        assert len(params) > 0, "Schema should contain parsed parameters"
