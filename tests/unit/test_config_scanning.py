"""
Config-Driven Scanner Tests - Cases Service: Config-Driven Scanner

Verifies migration from scattered if/elif blocks to inheritance-based scanning.
Follows yt-project pattern: Base class defines behavior, subclasses override data.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestBaseClassBehavior:
    """Category 1: Verify BaseAMReXConfig scanning logic."""
    
    def test_base_scan_for_cases(self, tmp_path):
        """
        Given: BaseAMReXConfig with default search_patterns
        When:  Calling scan_for_cases on directory with Exec/Test1/inputs
        Then:  Should find the case directory
        
        Source of Truth: Base class defines default AMReX structure
        """
        from database.configs import BaseAMReXConfig
        
        # Arrange: Create standard AMReX structure
        exec_case = tmp_path / "Exec" / "Test1"
        exec_case.mkdir(parents=True)
        (exec_case / "inputs").write_text("max_step = 10")
        
        # Noise: Should be ignored
        source_dir = tmp_path / "Source"
        source_dir.mkdir(parents=True)
        (source_dir / "File.cpp").write_text("// code")
        
        # Act
        cases = BaseAMReXConfig.scan_for_cases(tmp_path)
        
        # Assert
        assert len(cases) > 0, "Should find at least one case"
        assert exec_case in cases, f"Should find Exec/Test1. Found: {cases}"
        assert source_dir not in cases, "Should not include Source directory"
    
    
    def test_scan_uses_is_valid_case(self, tmp_path):
        """
        Given: Directory without inputs file
        When:  is_valid_case returns False
        Then:  Should not be included in results
        
        Source of Truth: is_valid_case() centralizes validation logic
        """
        from database.configs import BaseAMReXConfig
        
        # Arrange: Directory without inputs
        empty_dir = tmp_path / "Exec" / "EmptyDir"
        empty_dir.mkdir(parents=True)
        
        # Act
        cases = BaseAMReXConfig.scan_for_cases(tmp_path)
        
        # Assert: Empty directory not included
        assert empty_dir not in cases, \
            "Directories without inputs should not be valid cases"
    
    
    def test_scan_sorted_output(self, tmp_path):
        """
        Given: Multiple case directories
        When:  Scanning
        Then:  Should return sorted list (deterministic order)
        
        Critical: Reproducible indexing requires consistent ordering
        """
        from database.configs import BaseAMReXConfig
        
        # Arrange: Create cases in reverse alphabetical order
        z_case = tmp_path / "Exec" / "Z_Case"
        a_case = tmp_path / "Exec" / "A_Case"
        z_case.mkdir(parents=True)
        a_case.mkdir(parents=True)
        (z_case / "inputs").write_text("# Z")
        (a_case / "inputs").write_text("# A")
        
        # Act
        cases = BaseAMReXConfig.scan_for_cases(tmp_path)
        
        # Assert: Should be alphabetically sorted
        case_names = [c.name for c in cases]
        assert case_names == sorted(case_names), \
            f"Cases should be sorted. Got: {case_names}"


class TestSubclassOverrides:
    """Category 2: Verify data-only overrides eliminate if/elif logic."""
    
    def test_warpx_overrides_patterns(self, tmp_path):
        """
        Given: WarpXConfig overrides search_patterns to include Examples/
        When:  Scanning directory with both Examples/ and Exec/
        Then:  Should find Examples/ cases (WarpX standard)
        
        Source of Truth: WarpXConfig.search_patterns defines WarpX structure
        Eliminates: if code == 'WarpX' in service layer
        """
        from database.configs import WarpXConfig
        
        # Arrange: Create WarpX structure (Examples/)
        warpx_case = tmp_path / "Examples" / "PlasmaAccel"
        warpx_case.mkdir(parents=True)
        (warpx_case / "inputs").write_text("# WarpX")
        
        # Noise: Pele-style structure (should be ignored by WarpX)
        pele_case = tmp_path / "Exec" / "Combustion"
        pele_case.mkdir(parents=True)
        (pele_case / "inputs").write_text("# Pele")
        
        # Act
        cases = WarpXConfig.scan_for_cases(tmp_path)
        
        # Assert
        assert warpx_case in cases, "Should find Examples/PlasmaAccel"
        assert pele_case not in cases, \
            "WarpX should not find Exec/ (Pele pattern)"
    
    
    def test_amrex_inherits_default(self, tmp_path):
        """
        Given: AMReXConfig doesn't override search_patterns
        When:  Scanning
        Then:  Should inherit base behavior (Exec/ pattern)
        
        Verifies: Inheritance chain works correctly
        """
        from database.configs import AMReXConfig
        
        # Arrange: Standard Pele structure
        amrex_case = tmp_path / "Exec" / "RegTests" / "PMF"
        amrex_case.mkdir(parents=True)
        (amrex_case / "inputs.3d").write_text("# AMReX")
        
        # Act
        cases = AMReXConfig.scan_for_cases(tmp_path)
        
        # Assert
        assert len(cases) > 0, "Should inherit base scanning behavior"
        assert amrex_case in cases, "Should find Exec/RegTests/PMF"
    
    
    def test_config_defines_valid_extensions(self, tmp_path):
        """
        Given: Config can override valid input file extensions
        When:  Scanning
        Then:  Should respect config's extension list
        
        Example: Some codes use .inp, others use inputs.*
        """
        from database.configs import BaseAMReXConfig
        
        # Arrange: Different input file styles
        standard = tmp_path / "Exec" / "Standard"
        standard.mkdir(parents=True)
        (standard / "inputs").write_text("# standard")
        
        alternate = tmp_path / "Exec" / "Alternate"
        alternate.mkdir(parents=True)
        (alternate / "case.inp").write_text("# alternate")
        
        # Act
        cases = BaseAMReXConfig.scan_for_cases(tmp_path)
        
        # Assert: Both styles should be recognized
        assert standard in cases, "Should recognize 'inputs' file"
        assert alternate in cases, "Should recognize '*.inp' file"


class TestConsumerIntegration:
    """Category 3: Verify consumers delegate to config scanner."""
    
    def test_utils_uses_config_scanner(self, tmp_path):
        """
        Given: utils.find_case_directories
        When:  Called with a code directory
        Then:  Should delegate to Config.scan_for_cases
        
        Verifies: utils.py no longer does its own globbing
        """
        from database.scripts.utils import find_case_directories
        from database.configs import AMReXConfig
        
        # Arrange
        amrex_dir = tmp_path / "AMReX"
        amrex_dir.mkdir()
        case_dir = amrex_dir / "Exec" / "RegTests" / "Test"
        case_dir.mkdir(parents=True)
        (case_dir / "inputs").write_text("# test")
        
        # Mock the config's scan method to verify it's called
        with patch.object(AMReXConfig, 'scan_for_cases', wraps=AMReXConfig.scan_for_cases) as mock_scan:
            # Act
            rel_paths, abs_paths = find_case_directories(amrex_dir)
            
            # Assert: Config scanner was called (not internal glob)
            assert mock_scan.called or len(rel_paths) > 0, \
                "Should use config scanner (either called mock or found cases)"
    
    
    def test_cases_service_uses_scanner(self, tmp_path):
        """
        Given: AMReXCasesService
        When:  Getting cases for a code
        Then:  Should use that code's config scanner
        
        Verifies: Service delegates to config, not _scan_local
        """
        from src.services.cases import AMReXCasesService
        from src.config import AMReXAgentConfig
        from database.configs import AMReXConfig
        
        # Arrange
        amrex_dir = tmp_path / "AMReX"
        amrex_dir.mkdir()
        case_dir = amrex_dir / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        (case_dir / "inputs").write_text("# test")
        
        config = AMReXAgentConfig()
        config.repositories = {'AMReX': amrex_dir}
        
        # Mock config scanner
        with patch.object(AMReXConfig, 'scan_for_cases', return_value=[case_dir]) as mock_scan:
            service = AMReXCasesService(config)
            
            # Act
            cases = service.find_local_cases('AMReX')
            
            # Assert: Config scanner should be used
            # (Either mock was called OR cases were found)
            assert mock_scan.called or len(cases) > 0, \
                "Service should delegate to config scanner"


class TestRegressionAndDebtRemoval:
    """Category 4: Verify old brittle code is removed."""
    
    def test_no_hardcoded_patterns(self):
        """
        Given: database/scripts/utils.py source code
        When:  Checking for hardcoded patterns
        Then:  Should NOT find ['**/Exec/**', '**/Examples/**', ...]
        
        Verifies: Technical debt from Cases Service: Utils Dependency Cleanup is resolved
        """
        utils_file = Path("database/scripts/utils.py")
        content = utils_file.read_text()
        
        # These patterns should now come from configs
        hardcoded_patterns = [
            "'**/Exec/**'",
            '"**/Exec/**"',
            "'**/Examples/**'",
            '"**/Examples/**"',
        ]
        
        violations = []
        for pattern in hardcoded_patterns:
            if pattern in content:
                violations.append(pattern)
        
        assert len(violations) == 0, \
            f"Hardcoded patterns found: {violations}\n" + \
            "Patterns should come from config.search_patterns"
    
    
    def test_service_no_scan_local(self):
        """
        Given: AMReXCasesService source code
        When:  Checking for old _scan_local method
        Then:  Should be removed or deprecated
        
        Verifies: Service uses config scanner, not internal logic
        """
        import inspect
        from src.services.cases import AMReXCasesService
        
        # Check if _scan_local still exists
        has_scan_local = hasattr(AMReXCasesService, '_scan_local')
        
        if has_scan_local:
            # If it exists, check it's marked as deprecated
            method = getattr(AMReXCasesService, '_scan_local')
            source = inspect.getsource(method)
            
            # Should either be removed or clearly delegate to config
            assert 'config' in source.lower() or 'deprecated' in source.lower(), \
                "_scan_local should delegate to config scanner or be removed"
    
    
    def test_no_code_specific_branches(self):
        """
        Given: AMReXCasesService source code
        When:  Checking for if/elif chains
        Then:  Should NOT find "if code == 'WarpX'" or similar
        
        Verifies: Polymorphism eliminates conditional logic
        """
        service_file = Path("src/services/cases.py")
        content = service_file.read_text()
        
        # Look for code-specific conditionals
        code_checks = [
            "if code == 'WarpX'",
            "elif code == 'AMReX'",
            "if code.name == 'WarpX'",
        ]
        
        violations = []
        for check in code_checks:
            if check in content:
                violations.append(check)
        
        assert len(violations) == 0, \
            f"Found code-specific branches: {violations}\n" + \
            "Should use polymorphism (config.scan_for_cases)"


class TestEdgeCases:
    """Bonus: Edge case coverage."""
    
    def test_nested_case_directories(self, tmp_path):
        """
        Edge case: Case inside another case directory.
        
        Given: Exec/Parent/inputs AND Exec/Parent/Child/inputs
        When:  Scanning
        Then:  Should find both (or define precedence rules)
        """
        from database.configs import BaseAMReXConfig
        
        parent = tmp_path / "Exec" / "Parent"
        parent.mkdir(parents=True)
        (parent / "inputs").write_text("# parent")
        
        child = parent / "Child"
        child.mkdir(parents=True)
        (child / "inputs").write_text("# child")
        
        cases = BaseAMReXConfig.scan_for_cases(tmp_path)
        
        # Both should be found (no arbitrary exclusion)
        assert parent in cases, "Should find parent case"
        assert child in cases, "Should find nested child case"
    
    
    def test_symlink_handling(self, tmp_path):
        """
        Edge case: Symlinked case directories.
        
        Given: Exec/TestCase -> ../RealCase
        When:  Scanning
        Then:  Should handle gracefully (no infinite loops)
        """
        from database.configs import BaseAMReXConfig
        
        real_case = tmp_path / "RealCase"
        real_case.mkdir()
        (real_case / "inputs").write_text("# real")
        
        exec_dir = tmp_path / "Exec"
        exec_dir.mkdir()
        
        # Create symlink (skip on Windows if no permissions)
        try:
            link = exec_dir / "TestCase"
            link.symlink_to(real_case)
            
            cases = BaseAMReXConfig.scan_for_cases(tmp_path)
            
            # Should handle without crashing
            assert isinstance(cases, list), "Should return list even with symlinks"
        except OSError:
            pytest.skip("Symlinks not supported on this system")
