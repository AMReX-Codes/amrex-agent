"""
Utils Temporary Fix Tests - Cases Service: Utils Dependency Cleanup

Tracks technical debt: utils.py uses hardcoded patterns temporarily.
Config-driven scanning will be implemented in Cases Service: Config-Driven Scanner.
"""
import pytest
from pathlib import Path


@pytest.mark.technical_debt
class TestCircularDependencyFixed:
    """Verify the circular dependency is broken."""
    
    def test_utils_no_cases_import(self):
        """
        Validates that utils.py does NOT import from the service layer.
        Critical to prevent circular dependencies (Config -> Service -> Utils -> Config).
        
        Status: TEMPORARY FIX
        Next: Cases Service: Config-Driven Scanner will implement config-driven scanning
        """
        from database.scripts import utils
        
        utils_path = Path(utils.__file__)
        content = utils_path.read_text()
        
        # Check for forbidden imports
        forbidden = [
            "from services.cases",
            "from src.services.cases",
            "import services.cases",
            "AMReXCasesService",
        ]
        
        violations = [f for f in forbidden if f in content]
        
        assert len(violations) == 0, \
            f"Circular dependency detected! utils.py imports: {violations}\n" + \
            "utils.py must not import services.cases."


@pytest.mark.technical_debt
class TestTemporaryScanning:
    """Verify temporary scanning logic works (will be replaced in 3d)."""
    
    def test_utils_basic_scanning(self, tmp_path):
        """
        Validates temporary scanning logic works for standard AMReX structures.
        
        Status: TEMPORARY IMPLEMENTATION
        Target for replacement: Cases Service: Config-Driven Scanner (Config-driven scanning)
        """
        from database.scripts.utils import find_case_directories
        
        # Arrange: Create a mock AMReX repository structure
        source_dir = tmp_path / "AMReX"
        valid_case = source_dir / "Exec" / "RegTests" / "PMF"
        valid_case.mkdir(parents=True)
        (valid_case / "inputs.3d").touch()  # Mark as valid case
        
        # Create a non-case directory (no inputs file)
        ignored_dir = source_dir / "Exec" / "Source"
        ignored_dir.mkdir(parents=True)

        # Act
        rel_paths, abs_paths = find_case_directories(source_dir)

        # Assert
        assert "Exec/RegTests/PMF" in rel_paths
        assert valid_case in abs_paths
        assert len(abs_paths) == 1, \
            f"Should find exactly 1 case. Found: {rel_paths}"
    
    
    def test_warpx_examples_pattern(self, tmp_path):
        """
        WarpX uses Examples/ instead of Exec/.
        Verifies hardcoded patterns include both.
        
        Status: HARDCODED (temporary)
        Future: Patterns will come from WarpXConfig.search_patterns
        """
        from database.scripts.utils import find_case_directories
        
        source_dir = tmp_path / "WarpX"
        warpx_case = source_dir / "Examples" / "Physics_applications" / "laser"
        warpx_case.mkdir(parents=True)
        (warpx_case / "inputs").touch()

        rel_paths, abs_paths = find_case_directories(source_dir)

        assert any("Examples" in p for p in rel_paths), \
            f"Should find WarpX cases in Examples/. Found: {rel_paths}"
    
    
    def test_handles_nonexistent_directory(self, tmp_path):
        """
        Edge case: Directory doesn't exist.
        Should not crash (empty results OK).
        """
        from database.scripts.utils import find_case_directories
        
        nonexistent = tmp_path / "DoesNotExist"
        
        rel_paths, abs_paths = find_case_directories(nonexistent)
        
        assert rel_paths == [], "Should return empty list for nonexistent dir"
        assert abs_paths == []


@pytest.mark.technical_debt
class TestDebtDocumentation:
    """Document what needs to be done in Cases Service: Config-Driven Scanner."""
    
    def test_documents_future_architecture(self):
        """
        This test documents the planned architecture for Cases Service: Config-Driven Scanner.
        
        Cases Service: Config-Driven Scanner will implement:
        1. BaseAMReXConfig.search_patterns (data)
        2. database/configs/scanner.py (behavior)
        3. Refactor utils.py to use scanner
        4. Refactor services/cases.py to use scanner
        
        Benefits:
        - Single source of truth (configs)
        - No circular dependencies (scanner is leaf)
        - Code-specific patterns (WarpX: Examples/, Pele: Exec/)
        """
        from database.scripts.utils import find_case_directories
        
        # This test always passes - it's documentation
        assert True, "See docstring for Cases Service: Config-Driven Scanner architecture plan"
    
    
    def test_tracks_hardcoded_patterns(self):
        """
        Verify hardcoded patterns debt is RESOLVED.
        
        Cases Service: Config-Driven Scanner migrated patterns to configs:
        - **/Exec/**      → BaseAMReXConfig.search_patterns ✅
        - **/Examples/**  → WarpXConfig.search_patterns ✅
        - **/RegTests/**  → BaseAMReXConfig.search_patterns ✅
        - **/Tests/**     → BaseAMReXConfig.search_patterns ✅
        
        Status: DEBT RESOLVED in Cases Service: Config-Driven Scanner
        """
        from database.scripts.utils import find_case_directories
        import inspect
        
        source = inspect.getsource(find_case_directories)
        
        # Verify hardcoded patterns are REMOVED (debt resolved)
        has_hardcoded_list = (
            "case_patterns = [" in source and 
            "'**/Exec/**'" in source
        )
        
        assert not has_hardcoded_list, \
            "Hardcoded patterns should be removed (resolved in Cases Service: Config-Driven Scanner)"
        
        # Should now use config scanner
        assert "scan_for_cases" in source, \
            "Should use config.scan_for_cases() instead"
        
        print("\n✅ Technical Debt RESOLVED:")
        print("   Hardcoded patterns removed from utils.py")
        print("   Patterns now in config classes (Cases Service: Config-Driven Scanner)")
