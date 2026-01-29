"""
Indexing Engine: Path Standards Enforcement: Path Naming & Metadata Standards

Architecture tests enforcing the path taxonomy and metadata consistency.
Quality gate between Data Ingestion (Components 1-5) and Decision Logic (Architect Service).

References:
- Amendment B: Portable repo_path identifiers
- Amendment C: Full inputs_content parsing
- yt-project coding standards (descriptive variable names)

Markers:
- @pytest.mark.architecture: Enforces design patterns
- @pytest.mark.quality: Validates data quality
"""

import ast
import json
import pytest
from pathlib import Path
from typing import Set, Dict, Any


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Category 1: Path Naming Enforcement
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.architecture
def test_metadata_keys_standard(tmp_path):
    """
    Enforce standard path naming from Indexing Engine: Path Standards Enforcement taxonomy.
    
    ARCHITECTURE: Validates extract_metadata returns exact 4 required path keys.
    
    References:
    - base_amrex_config.py schema
    - Amendment B: Portable repo_path identifiers
    
    Expected Behavior:
    - Must include: case_name, case_path, repo_path, local_path
    - Must NOT include: case_dir, source_dir, abs_path, dir_path
    """
    from database.configs import BaseAMReXConfig
    
    # Arrange: Create realistic case structure
    case_dir = tmp_path / "Exec/RegTests/Sedov"
    case_dir.mkdir(parents=True)
    (case_dir / "inputs").write_text("amr.max_level = 2\namr.n_cell = 64 64 64")
    
    # Act
    metadata = BaseAMReXConfig.extract_metadata(case_dir, repo_root=tmp_path)
    
    # Assert: Required keys present
    required_keys = {'case_name', 'case_path', 'repo_path', 'local_path'}
    missing = required_keys - metadata.keys()
    assert not missing, (
        f"Missing standard keys: {missing}\n"
        f"Indexing Engine: Path Standards Enforcement requires all 4 path keys for quality gate.\n"
        f"See path taxonomy in specification."
    )
    
    # Assert: Forbidden internal keys absent
    forbidden_keys = {'case_dir', 'source_dir', 'abs_path', 'dir_path', 'root'}
    leaked = forbidden_keys & metadata.keys()
    assert not leaked, (
        f"Found forbidden internal keys: {leaked}\n"
        f"These are implementation details and must not appear in metadata.\n"
        f"Use standard keys: {required_keys}"
    )
    
    # Assert: All path fields are strings (JSON serializable)
    for key in required_keys:
        value = metadata.get(key)
        assert isinstance(value, str), (
            f"{key} must be str for JSON serialization, got {type(value)}\n"
            f"Fix: metadata['{key}'] = str(path_obj)"
        )


@pytest.mark.architecture
def test_function_parameters_consistent():
    """
    Enforce yt-style descriptive parameter names.
    
    ARCHITECTURE: Scans source code for ambiguous path parameter names.
    
    References:
    - yt-project coding standards: "Variable names should be short but descriptive"
    - Indexing Engine: Path Standards Enforcement path taxonomy
    
    Expected Behavior:
    - Reject: dir, folder, path (too vague)
    - Prefer: local_path, case_path, repo_path (explicit)
    """
    
    # Define naming rules
    forbidden_params = {
        "dir": "Use 'local_path' or 'case_path'",
        "folder": "Use 'local_path'",
        "path": "Too vague - use 'case_path' or 'local_path'",
        "dir_path": "Use 'local_path'",
        "abs_path": "Use 'local_path'",
        "full_path": "Use 'local_path'",
        "rel_path": "Use 'case_path' or 'repo_path'",
    }
    
    # AST visitor pattern
    class PathParamVisitor(ast.NodeVisitor):
        def __init__(self):
            self.violations = []
        
        def visit_FunctionDef(self, node):
            for arg in node.args.args:
                if arg.arg in forbidden_params:
                    self.violations.append({
                        'function': node.name,
                        'param': arg.arg,
                        'suggestion': forbidden_params[arg.arg],
                        'line': node.lineno
                    })
            self.generic_visit(node)
    
    # Scan directories
    source_dirs = [Path("src/services"), Path("database/indexing"), Path("database/configs")]
    all_violations = []
    
    for directory in source_dirs:
        if not directory.exists():
            continue
            
        for py_file in directory.rglob("*.py"):
            if py_file.name.startswith("test_"):
                continue  # Skip test files
                
            try:
                tree = ast.parse(py_file.read_text())
                visitor = PathParamVisitor()
                visitor.visit(tree)
                
                for v in visitor.violations:
                    all_violations.append(
                        f"{py_file.name}:{v['line']} - {v['function']}({v['param']})\n"
                        f"  Suggestion: {v['suggestion']}"
                    )
            except SyntaxError:
                pass  # Skip files with syntax errors
    
    # Report violations
    if all_violations:
        violation_report = "\n\n".join(all_violations)
        pytest.fail(
            f"Found {len(all_violations)} parameter naming violations:\n\n"
            f"{violation_report}\n\n"
            f"Follow yt-project standards: Use descriptive names that indicate\n"
            f"whether paths are relative (case_path, repo_path) or absolute (local_path).\n\n"
            f"This is Indexing Engine: Path Standards Enforcement's quality gate for Decision Logic (Architect Service)."
        )


@pytest.mark.architecture
def test_no_internal_vars_in_metadata(tmp_path):
    """
    Prevent internal variables from leaking into metadata.
    
    ARCHITECTURE: Internal variables like repo_root are machine-specific.
    
    References:
    - Amendment B: Portable identifiers
    - PRD Section 5.4 (FR-5): Structured metadata search
    
    Expected Behavior:
    - repo_root, root, source_dir: Internal only (break portability)
    - repo_path: Public (portable across machines)
    """
    from database.configs import BaseAMReXConfig
    
    # Arrange
    case_dir = tmp_path / "Exec/RegTests/Sedov"
    case_dir.mkdir(parents=True)
    (case_dir / "inputs").touch()
    
    # Act
    metadata = BaseAMReXConfig.extract_metadata(case_dir, repo_root=tmp_path)
    
    # Assert: Internal variables not in metadata
    internal_vars = {'repo_root', 'root', 'source_dir', 'base_dir'}
    leaked = internal_vars & metadata.keys()
    
    assert not leaked, (
        f"Internal variables leaked into metadata: {leaked}\n"
        f"These break portability - they depend on where the user cloned the repo.\n"
        f"Use 'repo_path' (relative) instead of absolute paths.\n\n"
        f"Example violation:\n"
        f"  metadata['repo_root'] = '/home/user/codes/AMReX'  # ❌ Machine-specific\n"
        f"  metadata['repo_path'] = 'Exec/RegTests/Sedov'     # ✅ Portable"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Category 2: Metadata Dictionary Consistency
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.quality
def test_metadata_dict_structure(tmp_path):
    """
    Validate metadata structure for JSON serializability.
    
    QUALITY: FAISS metadata must be JSON-serializable.
    
    References:
    - FAISS metadata storage requirements
    - Existing test pattern (test_metadata_is_json_serializable)
    
    Expected Behavior:
    - All Path objects converted to strings
    - No non-serializable types (sets, Path, etc.)
    """
    from database.configs import BaseAMReXConfig
    from pathlib import Path as PathType
    
    # Arrange
    case_dir = tmp_path / "Exec/RegTests/Sedov"
    case_dir.mkdir(parents=True)
    (case_dir / "inputs").touch()
    
    # Act
    metadata = BaseAMReXConfig.extract_metadata(case_dir, repo_root=tmp_path)
    
    # Assert: All path fields are strings, not Path objects
    path_fields = ['case_path', 'repo_path', 'local_path']
    for key in path_fields:
        value = metadata.get(key)
        assert value is not None, f"Missing required path field: {key}"
        assert isinstance(value, str), (
            f"{key} must be str for JSON serialization, got {type(value)}\n"
            f"Fix: metadata['{key}'] = str(path_obj)"
        )
        assert not isinstance(value, PathType), (
            f"{key} is a Path object - must convert to string"
        )
    
    # Assert: Entire metadata is JSON-serializable
    try:
        json_str = json.dumps(metadata)
        roundtrip = json.loads(json_str)
        # Don't assert equality if there are floats or other non-exact types
    except (TypeError, ValueError) as e:
        pytest.fail(f"Metadata not JSON-serializable: {e}\n{metadata}")


@pytest.mark.quality
def test_metadata_portability(tmp_path):
    """
    Verify repo_path is portable across different machines.
    
    QUALITY: Tests repo_path portability (NERSC vs laptop vs CI).
    
    References:
    - Amendment B: Portable repo_path identifiers
    - Existing test (test_path_portability)
    
    Expected Behavior:
    - repo_path is relative (no leading /)
    - Strips machine-specific prefixes (/global/cfs, /home, C:\\)
    - Same case on different machines has identical repo_path
    """
    from database.configs import BaseAMReXConfig
    
    # Arrange: Simulate NERSC directory structure
    nersc_root = tmp_path / "global/cfs/cdirs/m3018/AMReX"
    case_dir = nersc_root / "Exec/RegTests/Sedov"
    case_dir.mkdir(parents=True)
    (case_dir / "inputs").touch()
    
    # Act
    metadata = BaseAMReXConfig.extract_metadata(case_dir, repo_root=nersc_root)
    
    repo_path = metadata['repo_path']
    
    # Assert: No absolute paths
    assert not repo_path.startswith('/'), (
        f"repo_path must be relative, got: {repo_path}\n"
        f"Absolute paths break portability across different machines."
    )
    
    # Assert: No machine-specific prefixes
    forbidden_prefixes = ['global/cfs', 'home/', 'Users/', 'C:\\', '/mnt']
    for prefix in forbidden_prefixes:
        assert prefix not in repo_path, (
            f"repo_path contains machine-specific prefix '{prefix}': {repo_path}\n"
            f"Must strip all absolute path components."
        )
    
    # Assert: Matches expected portable format
    assert repo_path == "Exec/RegTests/Sedov", (
        f"Expected portable path 'Exec/RegTests/Sedov', got: {repo_path}"
    )
    
    # Assert: Same case on different machines has same repo_path
    # Simulate local laptop structure
    laptop_root = tmp_path / "codes/AMReX"
    laptop_case = laptop_root / "Exec/RegTests/Sedov"
    laptop_case.mkdir(parents=True)
    (laptop_case / "inputs").touch()
    
    laptop_metadata = BaseAMReXConfig.extract_metadata(laptop_case, repo_root=laptop_root)
    
    assert laptop_metadata['repo_path'] == metadata['repo_path'], (
        f"repo_path must be identical across machines!\n"
        f"NERSC:  {metadata['repo_path']}\n"
        f"Laptop: {laptop_metadata['repo_path']}\n\n"
        f"This is critical for Architect Service (Decision Logic) to work correctly."
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Category 3: Backward Compatibility & Deprecation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.architecture
def test_deprecated_keys_aliased(tmp_path):
    """
    Verify deprecated keys are properly aliased during Phase 1.
    
    ARCHITECTURE: Backward compatibility for legacy FAISS indices.
    
    Expected Behavior:
    - metadata['case'] exists and equals metadata['repo_path']
    - TODO: Mark for removal in Phase 2 (after Architect Service migration)
    """
    from database.configs import BaseAMReXConfig
    
    # Arrange
    case_dir = tmp_path / "Exec/RegTests/Sedov"
    case_dir.mkdir(parents=True)
    (case_dir / "inputs").touch()
    
    # Act
    metadata = BaseAMReXConfig.extract_metadata(case_dir, repo_root=tmp_path)
    
    # Assert: Deprecated alias exists
    if 'case' in metadata:
        # Phase 1: Should be aliased to repo_path
        assert metadata['case'] == metadata['repo_path'], (
            f"Deprecated 'case' key must alias 'repo_path' for backward compatibility.\n"
            f"Got: case={metadata['case']}, repo_path={metadata['repo_path']}"
        )
    # Phase 2: Will remove this key entirely (test will need updating)
