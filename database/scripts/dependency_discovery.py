"""
Hierarchical Dependency Discovery for AMReX-based Solvers.

Priority Order:
1. .gitmodules (PRIMARY) - Recursive submodule discovery
2. dependencies.json (FALLBACK) - Explicit version tracking
3. CI/Build files (TROUBLESHOOTING) - Informative on failure

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import configparser
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Dependency:
    """Represents a discovered dependency."""

    name: str
    source: str  # "gitmodules", "dependencies.json", "ci", "cmake"
    path: Path | None = None
    url: str | None = None
    version: str | None = None
    commit: str | None = None

    def __str__(self):
        parts = [self.name]
        if self.version:
            parts.append(f"v{self.version}")
        if self.commit:
            parts.append(f"@{self.commit[:7]}")
        return " ".join(parts)


class GitmodulesParser:
    """Parse .gitmodules to discover submodule dependencies (PRIMARY)."""

    # Known AMReX ecosystem packages
    AMREX_PACKAGES = {
        'amrex', 'pelephysics', 'pelec', 'pelelm', 'picsar',
        'warpx', 'mfix', 'erf', 'iamr', 'amrex-hydro'
    }

    @classmethod
    def discover_recursive(
        cls,
        repo_path: Path,
        visited: set[Path] | None = None
    ) -> list[Dependency]:
        """
        Recursively discover dependencies from .gitmodules.

        Parameters
        ----------
        repo_path : Path
            Starting repository.
        visited : Optional[Set[Path]], optional
            Track visited repos to avoid cycles.

        Returns
        -------
        List[Dependency]
            Dependencies in dependency order (base → derived).
        """
        if visited is None:
            visited = set()

        if repo_path in visited:
            return []

        visited.add(repo_path)

        gitmodules = repo_path / '.gitmodules'

        if not gitmodules.exists():
            return []

        # Parse .gitmodules
        config = configparser.ConfigParser()
        config.read(gitmodules)

        dependencies = []

        for section in config.sections():
            if not section.startswith('submodule'):
                continue

            # Extract submodule info
            name = section.split('"')[1] if '"' in section else ''
            path_str = config[section].get('path', '')
            url = config[section].get('url', '')
            config[section].get('branch', None)

            # Get full path
            submodule_path = repo_path / path_str if path_str else None

            # Extract package name
            pkg_name = Path(name).name if name else (Path(url).stem if url else Path(path_str).name)
            pkg_name = pkg_name.lower()
            pkg_name = pkg_name.lower()

            # Only process AMReX ecosystem packages
            if pkg_name not in cls.AMREX_PACKAGES:
                continue

            # Get commit if submodule is initialized
            commit = None
            if submodule_path and submodule_path.exists():
                commit = cls._get_commit(submodule_path)

            dep = Dependency(
                name=pkg_name,
                source="gitmodules",
                path=submodule_path,
                url=url,
                commit=commit
            )

            # Recursively discover nested submodules FIRST (depth-first)
            if submodule_path and submodule_path.exists():
                nested_deps = cls.discover_recursive(submodule_path, visited)
                dependencies.extend(nested_deps)

            # Then add this dependency
            dependencies.append(dep)

        return dependencies

    @staticmethod
    def _get_commit(repo_path: Path) -> str | None:
        """Get current commit hash of a repo."""
        import subprocess

        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        return None


class DependenciesJsonParser:
    """Parse dependencies.json (FALLBACK)."""

    AMREX_PACKAGES = GitmodulesParser.AMREX_PACKAGES

    @classmethod
    def parse(cls, repo_path: Path) -> list[Dependency]:
        """
        Parse dependencies.json if present.

        Parameters
        ----------
        repo_path : Path
            Repository root to inspect.

        Returns
        -------
        List[Dependency]
            Dependencies parsed from the file.
        """
        deps_file = repo_path / 'dependencies.json'

        if not deps_file.exists():
            return []

        try:
            data = json.loads(deps_file.read_text())
        except json.JSONDecodeError:
            return []

        dependencies = []

        for key in data:
            if key.startswith('version_'):
                pkg_name = key.replace('version_', '').lower()

                if pkg_name in cls.AMREX_PACKAGES:
                    version = data[key]
                    commit = data.get(f'commit_{pkg_name}', None)

                    dependencies.append(Dependency(
                        name=pkg_name,
                        source="dependencies.json",
                        version=version,
                        commit=commit
                    ))

        return dependencies


class TroubleshootingInfo:
    """Extract troubleshooting info from CI/build files (DIAGNOSTIC)."""

    @staticmethod
    def extract_ci_deps(repo_path: Path) -> dict[str, list[str]]:
        """
        Grep .github/workflows/dependencies/ for AMReX package info.

        Parameters
        ----------
        repo_path : Path
            Repository root to inspect.

        Returns
        -------
        Dict[str, List[str]]
            Mapping of package name to relevant lines.
        """
        deps_dir = repo_path / '.github' / 'workflows' / 'dependencies'

        if not deps_dir.exists():
            return {}

        info = {}

        for dep_file in deps_dir.glob('*.sh'):
            content = dep_file.read_text()

            # Look for AMReX package mentions
            for pkg in GitmodulesParser.AMREX_PACKAGES:
                pattern = rf'(?i){pkg}'  # Case-insensitive

                matches = []
                for line in content.split('\n'):
                    if re.search(pattern, line):
                        matches.append(line.strip())

                if matches:
                    info.setdefault(pkg, []).extend(matches)

        return info

    @staticmethod
    def extract_build_vars(repo_path: Path) -> dict[str, list[str]]:
        """
        Grep build files for dependency variables.

        Parameters
        ----------
        repo_path : Path
            Repository root to inspect.

        Returns
        -------
        Dict[str, List[str]]
            Mapping of package name to build variable lines.
        """
        info = {}

        # Check GNUmakefile
        makefile = repo_path / 'GNUmakefile'
        if makefile.exists():
            content = makefile.read_text()

            # Look for *_HOME variables
            home_pattern = r'(\w+_HOME)\s*[?:]?=\s*(.+)'
            for match in re.finditer(home_pattern, content):
                var_name = match.group(1)
                var_value = match.group(2)

                # Extract package name
                pkg = var_name.replace('_HOME', '').lower()
                if pkg in GitmodulesParser.AMREX_PACKAGES:
                    info.setdefault(pkg, []).append(f"{var_name} = {var_value}")

        # Check CMakeLists.txt
        cmake = repo_path / 'CMakeLists.txt'
        if cmake.exists():
            content = cmake.read_text()

            # Look for find_package, FetchContent, add_subdirectory
            patterns = [
                r'find_package\s*\(\s*(\w+)',
                r'FetchContent_Declare\s*\(\s*(\w+)',
                r'add_subdirectory\s*\(\s*([^\)]+)\)'
            ]

            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    pkg = match.group(1).lower()
                    if pkg in GitmodulesParser.AMREX_PACKAGES or 'amrex' in pkg:
                        info.setdefault(pkg, []).append(match.group(0))

        return info

    @staticmethod
    def display(repo_path: Path, missing_packages: list[str]):
        """
        Display troubleshooting info for missing packages.

        Parameters
        ----------
        repo_path : Path
            Repository root to inspect.
        missing_packages : List[str]
            Packages that could not be resolved.

        Returns
        -------
        None
            Prints troubleshooting guidance.
        """
        print("\n" + "="*70)
        print("💡 Troubleshooting Info")
        print("="*70)

        ci_info = TroubleshootingInfo.extract_ci_deps(repo_path)
        build_info = TroubleshootingInfo.extract_build_vars(repo_path)

        for pkg in missing_packages:
            print(f"\n📦 {pkg}:")

            found_any = False

            if pkg in ci_info:
                print("\n  Found in .github/workflows/dependencies/:")
                for line in ci_info[pkg][:5]:  # Show first 5
                    print(f"    {line}")
                found_any = True

            if pkg in build_info:
                print("\n  Found in build files:")
                for line in build_info[pkg][:3]:
                    print(f"    {line}")
                found_any = True

            if not found_any:
                print("  ⚠️  No info found in CI or build files")

            # Suggest command
            print("\n  💡 Suggestion:")
            print(f"     Build schema: python database/scripts/build_schema.py <{pkg.upper()}_HOME>")


class DependencyDiscovery:
    """Unified dependency discovery with fallback hierarchy."""

    @staticmethod
    def discover(repo_path: Path) -> list[Dependency]:
        """
        Discover dependencies using hierarchical strategy.

        1. Try .gitmodules (PRIMARY)
        2. Fallback to dependencies.json
        3. Return empty list if both fail (triggers troubleshooting)

        Parameters
        ----------
        repo_path : Path
            Repository root to inspect.

        Returns
        -------
        List[Dependency]
            Discovered dependencies.
        """
        print(f"Discovering dependencies for: {repo_path.name}")

        # PRIMARY: .gitmodules
        print("  Checking .gitmodules...", end=" ")
        gitmodules_deps = GitmodulesParser.discover_recursive(repo_path)

        if gitmodules_deps:
            print(f"✅ Found {len(gitmodules_deps)} dependencies")
            return gitmodules_deps
        else:
            print("⚠️  No submodules found")

        # FALLBACK: dependencies.json
        print("  Checking dependencies.json...", end=" ")
        json_deps = DependenciesJsonParser.parse(repo_path)

        if json_deps:
            print(f"✅ Found {len(json_deps)} dependencies")
            return json_deps
        else:
            print("⚠️  Not found")

        print("\n  ℹ️  No dependencies discovered via .gitmodules or dependencies.json")
        return []

    @staticmethod
    def discover_recursive(repo_path: Path) -> list[Dependency]:
        """
        Discover dependencies via .gitmodules recursively only.

        Parameters
        ----------
        repo_path : Path
            Repository root to inspect.

        Returns
        -------
        List[Dependency]
            Discovered dependencies.
        """
        return GitmodulesParser.discover_recursive(repo_path)

    @staticmethod
    def get_composition_order(deps: list[Dependency]) -> list[str]:
        """
        Order dependencies for composition (base → derived).

        Since gitmodules discovery is depth-first, the list is already ordered!
        Just deduplicate by name.

        Parameters
        ----------
        deps : List[Dependency]
            Discovered dependencies.

        Returns
        -------
        List[str]
            Unique dependency names in composition order.
        """
        seen = set()
        ordered = []

        for dep in deps:
            if dep.name not in seen:
                seen.add(dep.name)
                ordered.append(dep.name)

        return ordered


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python dependency_discovery.py <repo_path> [--troubleshoot]")
        sys.exit(1)

    repo_path = Path(sys.argv[1])

    # Discover dependencies
    deps = DependencyDiscovery.discover(repo_path)

    if deps:
        print("\n" + "="*70)
        print("Discovered Dependencies:")
        print("="*70)
        for dep in deps:
            print(f"  • {dep} (from {dep.source})")

        order = DependencyDiscovery.get_composition_order(deps)
        print(f"\nComposition order: {' → '.join(order)}")

    # Show troubleshooting if requested
    if "--troubleshoot" in sys.argv:
        TroubleshootingInfo.display(repo_path, [d.name for d in deps])
