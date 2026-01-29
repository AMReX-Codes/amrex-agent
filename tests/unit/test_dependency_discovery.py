"""
Unit tests for dependency discovery system.

Test modes (controlled by pytest markers):
- Mock tests (default): Fast tests with tmp_path
- Real tests (-m real_repos): Tests against ../AMReX, ../warpx

Run mock tests:     pytest tests/unit/test_dependency_discovery.py
Run real tests:     pytest tests/unit/test_dependency_discovery.py -m real_repos
Run both:           pytest tests/unit/test_dependency_discovery.py -m "real_repos or not real_repos"
"""

import pytest
from pathlib import Path
import json
import sys

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'database' / 'scripts'))

from dependency_discovery import (
    GitmodulesParser,
    DependenciesJsonParser,
    DependencyDiscovery,
    TroubleshootingInfo,
    Dependency
)


pytestmark = pytest.mark.input_writer_schema_composition


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def amrex_repo():
    """Path to AMReX repo (relative to project root)."""
    project_root = Path(__file__).parent.parent.parent
    return project_root.parent / 'AMReX'


@pytest.fixture
def warpx_repo():
    """Path to WarpX repo (relative to project root)."""
    project_root = Path(__file__).parent.parent.parent
    return project_root.parent / 'warpx'


# ============================================================================
# Mock Tests (Always Run)
# ============================================================================

class TestGitmodulesParserMock:
    """Test .gitmodules parsing with mocked file system."""
    
    def test_parse_single_submodule(self, tmp_path, monkeypatch):
        """
        Given: Repo with single AMReX submodule (MOCKED)
        When: Parse .gitmodules
        Then: Discovers amrex dependency
        """
        # Arrange
        gitmodules = tmp_path / '.gitmodules'
        gitmodules.write_text('''
[submodule "amrex"]
    path = Submodules/amrex
    url = https://github.com/AMReX-Codes/amrex.git
    branch = development
''')
        
        # Act
        deps = GitmodulesParser.discover_recursive(tmp_path)
        
        # Assert
        assert len(deps) == 1
        assert deps[0].name == "amrex"
        assert deps[0].source == "gitmodules"
    
    def test_parse_nested_submodules(self, tmp_path):
        """
        Given: Nested submodules (AMReX app → PelePhysics → AMReX) (MOCKED)
        When: Parse recursively
        Then: Returns dependencies in order: amrex, pelephysics
        """
        # Arrange
        pelec_gitmodules = tmp_path / '.gitmodules'
        pelec_gitmodules.write_text('''
[submodule "PelePhysics"]
    path = Submodules/PelePhysics
    url = https://github.com/AMReX-Combustion/PelePhysics.git
''')
        
        pelephysics_dir = tmp_path / 'Submodules' / 'PelePhysics'
        pelephysics_dir.mkdir(parents=True)
        
        pelephysics_gitmodules = pelephysics_dir / '.gitmodules'
        pelephysics_gitmodules.write_text('''
[submodule "amrex"]
    path = Submodules/amrex
    url = https://github.com/AMReX-Codes/amrex.git
''')
        
        # Act
        deps = GitmodulesParser.discover_recursive(tmp_path)
        
        # Assert
        assert len(deps) == 2
        dep_names = [d.name for d in deps]
        assert dep_names[0] == "amrex"
        assert dep_names[1] == "pelephysics"
    
    def test_ignores_non_amrex_packages(self, tmp_path):
        """
        Given: .gitmodules with non-AMReX submodules (MOCKED)
        When: Parse .gitmodules
        Then: Only returns AMReX ecosystem packages
        """
        # Arrange
        gitmodules = tmp_path / '.gitmodules'
        gitmodules.write_text('''
[submodule "amrex"]
    path = amrex
    url = https://github.com/AMReX-Codes/amrex.git

[submodule "some-random-lib"]
    path = libs/random
    url = https://github.com/random/lib.git
''')
        
        # Act
        deps = GitmodulesParser.discover_recursive(tmp_path)
        
        # Assert
        assert len(deps) == 1
        assert deps[0].name == "amrex"
    
    def test_handles_missing_gitmodules(self, tmp_path):
        """
        Given: Repo with no .gitmodules (MOCKED)
        When: Parse .gitmodules
        Then: Returns empty list
        """
        # Act
        deps = GitmodulesParser.discover_recursive(tmp_path)
        
        # Assert
        assert deps == []


class TestDependenciesJsonParserMock:
    """Test dependencies.json parsing with mocked files."""
    
    def test_parse_warpx_style(self, tmp_path):
        """
        Given: WarpX-style dependencies.json (MOCKED)
        When: Parse dependencies
        Then: Extracts amrex, picsar with versions
        """
        # Arrange
        deps_json = tmp_path / 'dependencies.json'
        deps_json.write_text(json.dumps({
            "version_warpx": "25.10",
            "version_amrex": "25.10",
            "version_picsar": "25.06",
            "commit_amrex": "807c7a26649b386be243fd8dfb3c1fec481183ca",
            "commit_picsar": "0c329e66010267662a82219f7de7abbd231463f4"
        }))
        
        # Act
        deps = DependenciesJsonParser.parse(tmp_path)
        
        # Assert
        assert len(deps) == 3
        amrex_dep = next(d for d in deps if d.name == "amrex")
        assert amrex_dep.version == "25.10"
        assert amrex_dep.source == "dependencies.json"
    
    def test_handles_missing_file(self, tmp_path):
        """
        Given: No dependencies.json (MOCKED)
        When: Parse dependencies
        Then: Returns empty list
        """
        # Act
        deps = DependenciesJsonParser.parse(tmp_path)
        
        # Assert
        assert deps == []


class TestDependencyDiscoveryHierarchyMock:
    """Test hierarchical discovery with mocked file system."""
    
    def test_prefers_gitmodules_over_json(self, tmp_path):
        """
        Given: Both .gitmodules AND dependencies.json present (MOCKED)
        When: Discover dependencies
        Then: Uses .gitmodules (primary)
        """
        # Arrange
        gitmodules = tmp_path / '.gitmodules'
        gitmodules.write_text('''
[submodule "amrex"]
    path = amrex
    url = https://github.com/AMReX-Codes/amrex.git
''')
        
        deps_json = tmp_path / 'dependencies.json'
        deps_json.write_text(json.dumps({
            "version_amrex": "25.10",
            "commit_amrex": "different"
        }))
        
        # Act
        deps = DependencyDiscovery.discover(tmp_path)
        
        # Assert
        assert len(deps) > 0
        assert deps[0].source == "gitmodules"
    
    def test_fallback_to_json_when_no_gitmodules(self, tmp_path):
        """
        Given: Only dependencies.json (MOCKED)
        When: Discover dependencies
        Then: Falls back to dependencies.json
        """
        # Arrange
        deps_json = tmp_path / 'dependencies.json'
        deps_json.write_text(json.dumps({
            "version_amrex": "25.10",
            "commit_amrex": "abc123"
        }))
        
        # Act
        deps = DependencyDiscovery.discover(tmp_path)
        
        # Assert
        assert len(deps) > 0
        assert deps[0].source == "dependencies.json"


class TestTroubleshootingInfoMock:
    """Test troubleshooting info extraction."""
    
    def test_extract_ci_dependencies(self, tmp_path):
        """
        Given: .github/workflows/dependencies/*.sh (MOCKED)
        When: Extract CI deps
        Then: Returns relevant lines
        """
        # Arrange
        deps_dir = tmp_path / '.github' / 'workflows' / 'dependencies'
        deps_dir.mkdir(parents=True)
        
        ubuntu_sh = deps_dir / 'ubuntu.sh'
        ubuntu_sh.write_text('''
export AMREX_VERSION=24.08
git clone https://github.com/AMReX-Codes/amrex.git
''')
        
        # Act
        info = TroubleshootingInfo.extract_ci_deps(tmp_path)
        
        # Assert
        assert 'amrex' in info
        assert any('AMREX_VERSION' in line for line in info['amrex'])


class TestCompositionOrder:
    """Test dependency ordering (pure logic)."""
    
    def test_orders_by_dependency_hierarchy(self):
        """
        Given: Dependencies in depth-first order
        When: Get composition order
        Then: Returns base → derived
        """
        # Arrange
        deps = [
            Dependency("amrex", "gitmodules"),
            Dependency("pelephysics", "gitmodules"),
        ]
        
        # Act
        order = DependencyDiscovery.get_composition_order(deps)
        
        # Assert
        assert order == ["amrex", "pelephysics"]
    
    def test_deduplicates_dependencies(self):
        """
        Given: Duplicate dependencies
        When: Get composition order
        Then: Removes duplicates
        """
        # Arrange
        deps = [
            Dependency("amrex", "gitmodules"),
            Dependency("pelephysics", "gitmodules"),
            Dependency("amrex", "dependencies.json"),
        ]
        
        # Act
        order = DependencyDiscovery.get_composition_order(deps)
        
        # Assert
        assert order == ["amrex", "pelephysics"]


# ============================================================================
# Real Repo Tests (Run with -m real_repos)
# ============================================================================

@pytest.mark.real_repos
class TestRealAMReXRepo:
    """Test against actual AMReX repository at ../AMReX."""
    
    def test_discover_amrex_dependencies(self, amrex_repo):
        """
        Given: Real AMReX repo at ../AMReX
        When: Discover dependencies
        Then: Finds dependencies
        
        Note: Auto-skips if ../AMReX not found
        """
        if not amrex_repo.exists():
            pytest.skip(f"AMReX not found at {amrex_repo}")
        
        # Also skip if .gitmodules not present (repo might not use submodules)
        if not (amrex_repo / '.gitmodules').exists():
            pytest.skip(f"AMReX has no .gitmodules file")
        
        # Act
        deps = DependencyDiscovery.discover(amrex_repo)
        
        # Assert
        assert len(deps) > 0
        dep_names = [d.name for d in deps]
        print(f"\n📦 AMReX dependencies: {dep_names}")
        
        assert any('amrex' in name for name in dep_names)
    
    def test_amrex_composition_order(self, amrex_repo):
        """
        Given: Real AMReX dependencies
        When: Get composition order
        Then: AMReX before PelePhysics
        
        Note: Auto-skips if ../AMReX not found
        """
        if not amrex_repo.exists():
            pytest.skip(f"AMReX not found at {amrex_repo}")
        
        # Also skip if .gitmodules not present (repo might not use submodules)
        if not (amrex_repo / '.gitmodules').exists():
            pytest.skip(f"AMReX has no .gitmodules file")
        
        # Act
        deps = DependencyDiscovery.discover(amrex_repo)
        order = DependencyDiscovery.get_composition_order(deps)
        
        # Assert
        print(f"\n📊 Composition: {' → '.join(order)}")
        
        if 'amrex' in order and 'pelephysics' in order:
            assert order.index('amrex') < order.index('pelephysics')


@pytest.mark.real_repos
class TestRealWarpXRepo:
    """Test against actual WarpX repository at ../warpx."""
    
    def test_discover_warpx_dependencies(self, warpx_repo):
        """
        Given: Real WarpX repo at ../warpx
        When: Discover dependencies
        Then: Finds dependencies
        
        Note: Auto-skips if ../warpx not found
        """
        if not warpx_repo.exists():
            pytest.skip(f"WarpX not found at {warpx_repo}")
        
        # Act
        deps = DependencyDiscovery.discover(warpx_repo)
        
        # Assert
        assert len(deps) > 0
        dep_names = [d.name for d in deps]
        print(f"\n📦 WarpX dependencies: {dep_names}")
        print(f"   Source: {deps[0].source}")
        
        assert any('amrex' in name for name in dep_names)
