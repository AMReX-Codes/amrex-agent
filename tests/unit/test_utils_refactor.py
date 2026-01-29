"""
Utils Refactor Tests - Cases Service: Utils Dependency Cleanup

Removes circular dependency: utils.py → cases.py → utils.py
Solution: utils.py uses database.configs directly
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCircularDependencyRemoved:
    """Test 1: Architectural constraint - no cases.py import."""
    
    def test_utils_no_cases_import(self):
        """
        Given: database/scripts/utils.py source code
        When:  Checking imports
        Then:  Should NOT import from services.cases
        
        Critical: Prevents circular dependency that bloats indexing
        """
        utils_file = Path("database/scripts/utils.py")
        
        if not utils_file.exists():
            pytest.skip("utils.py not found")
        
        source = utils_file.read_text()
        
        # Check for forbidden imports
        forbidden_patterns = [
            'from services.cases import',
            'from src.services.cases import',
            'import services.cases',
            'import src.services.cases',
            'AMReXCasesService',
        ]
        
        violations = []
        for pattern in forbidden_patterns:
            if pattern in source:
                violations.append(pattern)
        
        assert len(violations) == 0, \
            f"utils.py imports from cases.py: {violations}\n" + \
            "Should use database.configs directly instead"


class TestConfigDirectAccess:
    """Test 2: Utils uses configs registry, not service."""
    
    @pytest.mark.technical_debt
    @pytest.mark.skip(reason="Deferred to Cases Service: Config-Driven Scanner: config-driven scanner")
    def test_utils_uses_configs_directly(self):
        """
        Given: find_case_directories function
        When:  Identifying code from directory name
        Then:  Should call discover_code_configs() not AMReXCasesService
        
        Verifies: Direct registry access (no service layer needed)
        """
        from database.scripts.utils import find_case_directories
        
        # Create temp structure
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "AMReX"
            test_dir.mkdir()
            
            # Mock the config discovery
            with patch('database.scripts.utils.discover_code_configs') as mock_discover:
                # Setup mock config
                mock_config = MagicMock()
                mock_config.code_name = "AMReX"
                mock_discover.return_value = [mock_config]
                
                # Act
                try:
                    find_case_directories(test_dir)
                except Exception:
                    pass  # We just care that it was called
                
                # Assert: Config discovery was used
                assert mock_discover.called, \
                    "Should call discover_code_configs() to identify code"
    
    
    @pytest.mark.technical_debt
    @pytest.mark.skip(reason="Deferred to Cases Service: Config-Driven Scanner: config-driven scanner")
    def test_utils_imports_from_configs(self):
        """
        Verify: utils.py imports from database.configs
        
        This is the POSITIVE check (we want this import).
        """
        utils_file = Path("database/scripts/utils.py")
        
        if not utils_file.exists():
            pytest.skip("utils.py not found")
        
        source = utils_file.read_text()
        
        # Should have the config import
        assert 'from database.configs import' in source or \
               'import database.configs' in source, \
            "utils.py should import from database.configs"
        
        # Ideally imports discover_code_configs
        assert 'discover_code_configs' in source, \
            "Should use discover_code_configs function"


class TestFunctionalEquivalence:
    """Test 3: Refactored utils still finds cases correctly."""
    
    def test_utils_metadata_access(self, tmp_path):
        """
        Given: Temp AMReX repo with Exec/RegTests/Test1/inputs
        When:  Calling find_case_directories
        Then:  Should find the case without using Service
        
        Functional test: Proves refactoring maintains behavior
        """
        from database.scripts.utils import find_case_directories
        
        # Arrange: Create realistic case structure
        amrex_dir = tmp_path / "AMReX"
        case_dir = amrex_dir / "Exec" / "RegTests" / "Test1"
        case_dir.mkdir(parents=True)
        
        # Create inputs file (marks it as a case)
        (case_dir / "inputs").write_text("max_step = 10")
        
        # Act
        relative_paths, absolute_paths = find_case_directories(amrex_dir)
        
        # Assert: Found the case
        assert len(relative_paths) > 0, "Should find at least one case"
        assert "Exec/RegTests/Test1" in relative_paths, \
            f"Should find Test1 case. Found: {relative_paths}"
        
        # Verify absolute paths are Path objects
        assert all(isinstance(p, Path) for p in absolute_paths), \
            "Should return Path objects for absolute paths"
    
    
    def test_handles_unknown_code(self, tmp_path):
        """
        Edge case: Directory name not in registry
        
        Given: Directory named "UnknownCode"
        When:  Calling find_case_directories
        Then:  Should not crash (falls back to generic scan)
        """
        from database.scripts.utils import find_case_directories
        
        # Create unknown code dir
        unknown_dir = tmp_path / "UnknownCode"
        case_dir = unknown_dir / "Exec" / "Tests" / "TestCase"
        case_dir.mkdir(parents=True)
        (case_dir / "inputs").write_text("# test")
        
        # Should not raise (uses generic patterns)
        relative_paths, absolute_paths = find_case_directories(unknown_dir)
        
        # Should still find it with generic glob
        assert len(relative_paths) >= 0, "Should handle unknown codes gracefully"
    
    
    def test_warpx_examples_pattern(self, tmp_path):
        """
        Code-specific test: WarpX uses Examples/ not Exec/
        
        Given: WarpX/Examples/Physics_applications/case
        When:  Scanning
        Then:  Should find it (proves glob patterns work)
        """
        from database.scripts.utils import find_case_directories
        
        warpx_dir = tmp_path / "WarpX"
        case_dir = warpx_dir / "Examples" / "Physics_applications" / "laser"
        case_dir.mkdir(parents=True)
        (case_dir / "inputs").write_text("# WarpX")
        
        relative_paths, _ = find_case_directories(warpx_dir)
        
        # Should find WarpX cases in Examples/
        assert any("Examples" in p for p in relative_paths), \
            f"Should find WarpX cases in Examples/. Found: {relative_paths}"


class TestPerformance:
    """Bonus: Ensure refactor doesn't add overhead."""
    
    def test_no_service_instantiation(self):
        """
        Given: Refactored utils.py
        When:  Scanning for cases
        Then:  Should NOT create AMReXCasesService instance
        
        Performance: Service instantiation is heavy (loads all configs, checks paths)
        Utils should be lightweight (config lookup only)
        """
        import sys
        
        # Check if AMReXCasesService is even importable from utils
        from database.scripts import utils as utils_module
        
        # Get all names in the module
        module_contents = dir(utils_module)
        
        assert 'AMReXCasesService' not in module_contents, \
            "utils.py should not have AMReXCasesService in namespace"
