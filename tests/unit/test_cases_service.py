"""
Cases Service Tests - Cases Service

Build Order: Config → Embedding → Cases
Following Amendment B: Portable repo-relative paths
"""
import pytest
from pathlib import Path
from src.config import AMReXAgentConfig
from src.services.cases import AMReXCasesService


class TestLocalCaseDiscovery:
    """Test 1: Find local cases with repo-relative paths."""

    def test_find_local_cases(self, temp_repo):
        """
        Given: Temp repo with Exec/RegTests/TestCase/inputs
        When:  Scanning for cases
        Then:  Returns repo-relative path (not absolute)

        Pass: Returns ["Exec/RegTests/TestCase"]
        Fail: Returns ["/tmp/pytest-xxx/Exec/RegTests/TestCase"]

        Amendment B: Portable paths for cross-environment indexing
        """
        # Arrange
        config = AMReXAgentConfig()
        config.repositories = {'AMReX': temp_repo}
        service = AMReXCasesService(config)

        # Act
        cases = service.find_local_cases("AMReX")

        # Assert
        assert len(cases) > 0, "Should find at least one case"

        # Critical: Check for repo-relative paths
        for case_path in cases:
            assert not case_path.startswith("/"), \
                f"Path should be repo-relative, got: {case_path}"
            assert case_path.startswith("Exec/"), \
                f"Expected Exec/ prefix, got: {case_path}"


class TestGitHubFallback:
    """Test 2: Fallback to common cases when local repo missing."""

    def test_github_fallback(self, monkeypatch):
        """
        Given: Config with non-existent amrex_repo_path
        When:  Attempting to find cases
        Then:  Returns hardcoded common cases (PMF, Sedov, etc.)

        Pass: Returns ["Exec/RegTests/PMF", "Exec/RegTests/Sedov", ...]
        Fail: Raises FileNotFoundError or returns []
        """
        # Arrange
        config = AMReXAgentConfig()
        config.repositories = {'AMReX': Path("/nonexistent/path")}

        # Ensure no env vars interfere
        monkeypatch.delenv("AMREX_HOME", raising=False)

        service = AMReXCasesService(config)

        # Act
        cases = service.find_local_cases("AMReX")

        # Assert
        assert len(cases) > 0, "Should return fallback cases"
        assert "Tests/Amr/Advection_AmrCore" in cases or "Advection_AmrCore" in cases, \
            "Should include Advection_AmrCore in fallback list"


class TestMultiCodeDetection:
    """Test 3: Correctly segregate cases by code (AMReX, PeleLMeX)."""

    def test_code_detection(self, tmp_path):
        """
        Given: Two separate repos (AMReX and PeleLMeX)
        When:  Calling list_all_cases()
        Then:  Returns dict with separate keys

        Pass: {"AMReX": [...], "PeleLMeX": [...]}
        Fail: Mixed cases or missing keys
        """
        # Arrange
        amrex_repo = tmp_path / "AMReX"
        pelelmex_repo = tmp_path / "PeleLMeX"

        # Create case structure
        (amrex_repo / "Exec/RegTests/CaseA").mkdir(parents=True)
        (amrex_repo / "Exec/RegTests/CaseA/inputs").write_text("# AMReX")

        (pelelmex_repo / "Exec/RegTests/CaseB").mkdir(parents=True)
        (pelelmex_repo / "Exec/RegTests/CaseB/inputs").write_text("# PeleLMeX")

        config = AMReXAgentConfig()
        
        # Override ALL repositories to use temp repos only (prevents scanning real repos)
        config.repositories = {
            'AMReX': amrex_repo,
            'PeleLMeX': pelelmex_repo,
            'PeleMP': None,
            'incflo': None,
            'ERF': None,
        }

        service = AMReXCasesService(config)

        # Act
        all_cases = service.list_all_cases()

        # Assert
        assert "AMReX" in all_cases, "Should have AMReX key"
        assert "PeleLMeX" in all_cases, "Should have PeleLMeX key"

        # Check segregation (verify temp cases were found)
        amrex_cases = all_cases["AMReX"]
        pelelmex_cases = all_cases["PeleLMeX"]

        # Should find our temp cases
        assert any("CaseA" in c for c in amrex_cases), \
            f"AMReX should contain CaseA. Found: {amrex_cases}"
        assert any("CaseB" in c for c in pelelmex_cases), \
            f"PeleLMeX should contain CaseB. Found: {pelelmex_cases}"
        
        # Verify proper segregation
        assert not any("CaseB" in c for c in amrex_cases), \
            "AMReX should NOT contain PeleLMeX cases"
        assert not any("CaseA" in c for c in pelelmex_cases), \
            "PeleLMeX should NOT contain AMReX cases"


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary AMReX-like repository structure."""
    repo = tmp_path / "AMReX"
    case_dir = repo / "Exec" / "RegTests" / "TestCase"
    case_dir.mkdir(parents=True)
    
    # Create minimal inputs file
    (case_dir / "inputs").write_text("""
# Test case
max_step = 10
""")
    
    return repo
