#!/usr/bin/env python3
"""
Input Writer: Schema Scraper: AMReX Parameter Schema Builder.

Offline script to generate JSON schemas from C++ source code.
Run from repository root or as standalone script.

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import contextlib
import json
import logging
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    # Reuse Indexing Engine: Build Metadata Extensions build parsing
    from database.scripts.amrex_metadata_utils import extract_generic_build_config
except ModuleNotFoundError:
    PELE_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(PELE_AGENT_ROOT) not in sys.path:
        sys.path.insert(0, str(PELE_AGENT_ROOT))
    from database.scripts.amrex_metadata_utils import extract_generic_build_config

logger = logging.getLogger(__name__)


def _resolve_solver_config(repo_path: Path):
    """Resolve solver config class by repo name using registry."""
    from database.configs import BaseAMReXConfig, discover_code_configs

    repo_name = repo_path.name.lower()
    for cfg in discover_code_configs():
        if cfg.code_name.lower() == repo_name or getattr(cfg, "github_repo", "").lower() == repo_name:
            return cfg
    return BaseAMReXConfig

class SchemaComposer:
    """Compose full solver schema from component schemas."""

    def compose(
        self,
        components: list[dict[str, Any]],
        solver_name: str
    ) -> dict[str, Any]:
        """
        Merge component schemas into full solver schema.

        Parameters
        ----------
        components : List[Dict[str, Any]]
            Schema dictionaries to merge.
        solver_name : str
            Solver name for logging.

        Returns
        -------
        Dict[str, Any]
            Merged schema dictionary.
        """
        merged = {}

        for component_schema in components:
            for param_name, param_data in component_schema.items():
                if param_name in merged:
                    # Collision detected
                    if merged[param_name] == param_data:
                        # Same definition, OK
                        logger.debug(f"Duplicate definition of {param_name} (same)")
                    else:
                        # Conflict!
                        logger.warning(
                            f"Schema conflict for {param_name} in {solver_name}"
                        )

                merged[param_name] = param_data

        logger.info(
            f"Composed schema for {solver_name}: {len(merged)} parameters"
        )
        return merged


    def merge(self, schemas: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Merge multiple schemas, detecting parameter collisions.

        Parameters
        ----------
        schemas : List[Dict[str, Any]]
            Schema dictionaries to merge.

        Returns
        -------
        Dict[str, Any]
            Merged schema with all parameters.

        Warnings
        --------
            Logs warning if same parameter defined in multiple schemas
        """
        merged = {}

        for schema in schemas:
            for param_name, param_data in schema.items():
                if param_name in merged:
                    # Collision detected
                    logger.warning(
                        f"Parameter '{param_name}' defined in multiple schemas. "
                        f"Using first definition."
                    )
                else:
                    merged[param_name] = param_data

        return merged


class EnhancedTypeExtractor:
    """Enhanced type extraction with backward variable search."""

    # AMReX type patterns (ordered by specificity)
    TYPE_PATTERNS = [
        # AMReX types
        (r'\b(Real|amrex::Real)\b', 'Real'),
        (r'\b(IntVect|amrex::IntVect)\b', 'IntVect'),
        (r'\b(RealVect|amrex::RealVect)\b', 'RealVect'),
        (r'\bVector<\s*(Real|int|long|double)\s*>', 'Vector'),
        (r'\bArray<\s*(Real|int)\s*,\s*\d+\s*>', 'Array'),

        # Standard C++ types
        (r'\b(int|long|long\s+int)\b', 'int'),
        (r'\b(double|float)\b', 'Real'),  # Map to AMReX Real
        (r'\b(bool)\b', 'bool'),
        (r'\b(std::string|string)\b', 'string'),

        # Container types
        (r'\bstd::vector<\s*(\w+)\s*>', 'Vector'),
        (r'\bstd::array<\s*(\w+)\s*,\s*\d+\s*>', 'Array'),
    ]

    @classmethod
    def extract_type_enhanced(
        cls,
        param_name: str,
        var_name: str,
        source_file: Path,
        line_number: int
    ) -> str | None:
        """
        Extract type with enhanced strategies.

        Parameters
        ----------
        param_name : str
            Parameter name (e.g., "cfl").
        var_name : str
            Variable name from the ParmParse call.
        source_file : Path
            Source file containing the call.
        line_number : int
            Line number of the ParmParse call.

        Returns
        -------
        Optional[str]
            Type string (e.g., "Real", "int"), or ``None``.
        """
        content = source_file.read_text()
        lines = content.split('\n')

        # Strategy 1: Search backward for local variable declaration
        type_found = cls._search_backward_declaration(
            var_name, lines, line_number
        )
        if type_found:
            return type_found

        # Strategy 2: Search in class definition (member variables)
        type_found = cls._search_class_members(
            var_name, source_file, content
        )
        if type_found:
            return type_found

        # Strategy 3: Check header file if this is a .cpp
        if source_file.suffix == '.cpp':
            header = source_file.with_suffix('.H')
            if not header.exists():
                header = source_file.with_suffix('.h')

            if header.exists():
                type_found = cls._search_header_file(var_name, header)
                if type_found:
                    return type_found

        return None

    @classmethod
    def _search_backward_declaration(
        cls,
        var_name: str,
        lines: list,
        start_line: int,
        search_distance: int = 100
    ) -> str | None:
        """
        Search backward from ParmParse call for variable declaration.

        Patterns:
          Real cfl;
          int n_cells = 32;
          Vector<Real> values;
          bool use_reactions = false;
        """
        # Search backward (but not too far)
        search_start = max(0, start_line - search_distance)

        for line_idx in range(start_line - 1, search_start, -1):
            line = lines[line_idx].strip()

            # Skip comments
            if line.startswith('//') or line.startswith('/*'):
                continue

            # Look for declaration patterns
            for type_pattern, type_name in cls.TYPE_PATTERNS:
                # Pattern: <type> <var_name> [= value];
                pattern = rf'{type_pattern}\s+{re.escape(var_name)}\s*[=;]'

                if re.search(pattern, line):
                    return type_name

                # Pattern: <type> <var1>, <var2>, <var_name>;
                pattern = rf'{type_pattern}\s+\w+(?:\s*,\s*\w+)*\s*,\s*{re.escape(var_name)}\s*[=;]'
                if re.search(pattern, line):
                    return type_name

        return None

    @classmethod
    def _search_class_members(
        cls,
        var_name: str,
        source_file: Path,
        content: str
    ) -> str | None:
        """
        Search for member variable declarations.

        Patterns:
          class MyClass {
            Real m_cfl;
            int m_nsteps;
          };
        """
        # Find class definition
        class_pattern = r'class\s+\w+\s*(?::\s*public\s+\w+)?\s*\{'

        for match in re.finditer(class_pattern, content):
            class_start = match.end()

            # Find matching closing brace (simplified - doesn't handle nested)
            brace_count = 1
            class_end = class_start

            for i in range(class_start, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        class_end = i
                        break

            # Search within class body
            class_body = content[class_start:class_end]

            for type_pattern, type_name in cls.TYPE_PATTERNS:
                # Pattern: <type> m_var_name;
                pattern = rf'{type_pattern}\s+{re.escape(var_name)}\s*[=;]'

                if re.search(pattern, class_body):
                    return type_name

        return None

    @classmethod
    def _search_header_file(
        cls,
        var_name: str,
        header_file: Path
    ) -> str | None:
        """Search in header file for member variable declarations."""
        if not header_file.exists():
            return None

        content = header_file.read_text()

        # Use same class member search
        return cls._search_class_members(var_name, header_file, content)

    @classmethod
    def _search_class_members(
        cls,
        var_name: str,
        source_file: Path,
        content: str
    ) -> str | None:
        """
        Search for member variable declarations.

        Patterns:
          class MyClass {
            Real m_cfl;
            int m_nsteps;
          };
        """
        # Find class definition
        class_pattern = r'class\s+\w+\s*(?::\s*public\s+\w+)?\s*\{'

        for match in re.finditer(class_pattern, content):
            class_start = match.end()

            # Find matching closing brace (simplified - doesn't handle nested)
            brace_count = 1
            class_end = class_start

            for i in range(class_start, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        class_end = i
                        break

            # Search within class body
            class_body = content[class_start:class_end]

            for type_pattern, type_name in cls.TYPE_PATTERNS:
                # Pattern: <type> m_var_name;
                pattern = rf'{type_pattern}\s+{re.escape(var_name)}\s*[=;]'

                if re.search(pattern, class_body):
                    return type_name

        return None

    @classmethod
    def _search_header_file(
        cls,
        var_name: str,
        header_file: Path
    ) -> str | None:
        """Search in header file for member variable declarations."""
        if not header_file.exists():
            return None

        content = header_file.read_text()

        # Use same class member search
        return cls._search_class_members(var_name, header_file, content)


# Example usage showing improvement
if __name__ == "__main__":
    # Test case from PeleC
    test_code = """
void PeleC::read_params()
{
    ParmParse pp("pelec");

    Real cfl = 0.3;
    pp.query("cfl", cfl);

    int max_level = 0;
    pp.query("max_level", max_level);

    Vector<Real> gravity;
    pp.queryarr("gravity", gravity);

    bool do_react = false;
    pp.query("do_react", do_react);
}
"""

    # Write to temp file
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as f:
        f.write(test_code)
        temp_file = Path(f.name)

    # Test extraction
    extractor = EnhancedTypeExtractor()

    test_cases = [
        ("cfl", "cfl", 5),
        ("max_level", "max_level", 8),
        ("gravity", "gravity", 11),
        ("do_react", "do_react", 14),
    ]

    print("Enhanced Type Extraction Test:")
    print("="*70)

    for param, var, line in test_cases:
        type_found = extractor.extract_type_enhanced(
            param, var, temp_file, line
        )
        print(f"{param:15} → {type_found or 'None'}")

    temp_file.unlink()


@dataclass
class Declaration:
    """Variable declaration information."""

    var_name: str
    var_type: str
    file_path: Path
    line_number: int
    scope: str  # "local", "member", "global"


class DeclarationExtractor:
    """Extract all variable declarations from C++ codebase."""

    # Comprehensive type patterns
    DECLARATION_PATTERNS = [
        # AMReX types
        r'\b(Real|amrex::Real)\s+(\w+)\s*[=;,]',
        r'\b(IntVect|amrex::IntVect)\s+(\w+)\s*[=;,\(]',
        r'\b(RealVect|amrex::RealVect)\s+(\w+)\s*[=;,\(]',
        r'\bVector<(Real|int|long)>\s+(\w+)\s*[=;,\(]',
        r'\bArray<(Real|int),\s*\d+>\s+(\w+)\s*[=;,\(]',

        # Standard C++ types
        r'\b(int|long|long\s+int)\s+(\w+)\s*[=;,]',
        r'\b(double|float)\s+(\w+)\s*[=;,]',
        r'\b(bool)\s+(\w+)\s*[=;,]',
        r'\b(std::string|string)\s+(\w+)\s*[=;,]',

        # Containers
        r'\bstd::vector<(\w+)>\s+(\w+)\s*[=;,\(]',
        r'\bstd::array<(\w+),\s*\d+>\s+(\w+)\s*[=;,\(]',
    ]

    @classmethod
    def extract_all_declarations(
        cls,
        source_dirs: list[Path],
        extensions: list[str] = None
    ) -> dict[str, list[Declaration]]:
        """
        Extract all variable declarations from source directories.

        Parameters
        ----------
        source_dirs : List[Path]
            Directories to scan.
        extensions : List[str], optional
            File extensions to process.

        Returns
        -------
        Dict[str, List[Declaration]]
            Mapping of variable name to declarations.
        """
        if extensions is None:
            extensions = ['.cpp', '.H', '.h', '.cc']
        declarations = defaultdict(list)

        # Collect all source files
        all_files = []
        for source_dir in source_dirs:
            if not source_dir.exists():
                continue

            for ext in extensions:
                all_files.extend(source_dir.rglob(f'*{ext}'))

        print(f"Scanning {len(all_files)} files for declarations...")

        # Single pass through all files
        for file_path in all_files:
            try:
                file_decls = cls._extract_from_file(file_path)

                for decl in file_decls:
                    declarations[decl.var_name].append(decl)

            except Exception:
                # Skip problematic files silently
                pass

        print(f"Found {sum(len(v) for v in declarations.values())} declarations for {len(declarations)} unique variables")

        return declarations

    @classmethod
    def _extract_from_file(cls, file_path: Path) -> list[Declaration]:
        """Extract all declarations from a single file."""
        content = file_path.read_text(errors='ignore')
        lines = content.split('\n')

        declarations = []

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*'):
                continue

            # Try each pattern
            for pattern in cls.DECLARATION_PATTERNS:
                for match in re.finditer(pattern, line):
                    # Extract type and variable name
                    groups = match.groups()

                    if len(groups) == 2:
                        var_type = groups[0]
                        var_name = groups[1]
                    else:
                        # Container type - combine parts
                        var_type = groups[0]  # Inner type or full type
                        var_name = groups[1]

                    # Normalize type
                    var_type = cls._normalize_type(var_type)

                    # Determine scope
                    scope = cls._determine_scope(line, file_path)

                    declarations.append(Declaration(
                        var_name=var_name,
                        var_type=var_type,
                        file_path=file_path,
                        line_number=line_num,
                        scope=scope
                    ))

        return declarations

    @staticmethod
    def _normalize_type(cpp_type: str) -> str:
        """Normalize C++ type to schema type."""
        type_map = {
            'double': 'Real',
            'float': 'Real',
            'long': 'int',
            'long int': 'int',
            'amrex::Real': 'Real',
            'amrex::IntVect': 'IntVect',
            'amrex::RealVect': 'RealVect',
        }

        return type_map.get(cpp_type, cpp_type)

    @staticmethod
    def _determine_scope(line: str, file_path: Path) -> str:
        """Determine if declaration is local, member, or global."""
        # Simple heuristic
        if 'private:' in line or 'protected:' in line or 'public:' in line:
            return 'member'
        elif file_path.suffix in ['.H', '.h']:
            return 'member'  # Header files usually have members
        else:
            return 'local'

    @classmethod
    def match_variable_to_declaration(
        cls,
        var_name: str,
        file_path: Path,
        declarations: dict[str, list[Declaration]]
    ) -> str | None:
        """
        Match a ParmParse variable to its declaration.

        Strategy:
        1. Prefer declarations in same file
        2. Then check header file
        3. Then any file with matching name

        Parameters
        ----------
        var_name : str
            Variable name from the ParmParse call.
        file_path : Path
            File where the ParmParse call is located.
        declarations : Dict[str, List[Declaration]]
            Map of all declarations.

        Returns
        -------
        Optional[str]
            Type string, or ``None``.
        """
        if var_name not in declarations:
            return None

        decl_list = declarations[var_name]

        # Strategy 1: Same file (highest priority)
        for decl in decl_list:
            if decl.file_path == file_path:
                return decl.var_type

        # Strategy 2: Corresponding header file
        if file_path.suffix == '.cpp':
            header = file_path.with_suffix('.H')
            if not header.exists():
                header = file_path.with_suffix('.h')

            for decl in decl_list:
                if decl.file_path == header:
                    return decl.var_type

        # Strategy 3: Any declaration (take first one)
        if decl_list:
            return decl_list[0].var_type

        return None



class SchemaBuilder:
    """Extract parameter schema from AMReX source code."""

    def __init__(self, repo_root: Path):
        """
        Initialize schema builder.

        Args:
            repo_root: Root directory of AMReX-based code repository
        """
        self.root = Path(repo_root)
        self.schema: dict[str, dict[str, Any]] = {}
        self.build_config: dict[str, str] = {}
        self.current_namespace = None
        self.ifdef_stack = []  # Track nested #ifdef blocks
        self.parmparse_namespaces = {}  # Track ParmParse var → namespace
        self.declaration_map = None  # Populated during scan

    def scan_source_code(
        self,
        source_dirs: list[str],
        solver_config: Any | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Scan C++ files for ParmParse calls.

        Phase 1: Extract all variable declarations (single pass)
        Phase 2: Match ParmParse calls to declarations

        Parameters
        ----------
        source_dirs : List[str]
            Directory names to scan relative to repo root (e.g., ["Source", "Exec"]).
        solver_config : object, optional
            Solver config with build requirements and patterns.

        Returns
        -------
        Dict[str, Dict[str, Any]]
            Extracted schema mapping.
        """
        # Phase 0: Parse _cpp_parameters files (source of truth for PeleC params)
        print("Phase 0: Parsing _cpp_parameters definition files...")
        for dir_name in source_dirs:
            cpp_params_file = self.root / dir_name / "_cpp_parameters"
            if cpp_params_file.exists() and cpp_params_file.is_file():
                cpp_params = self._parse_cpp_parameters_file(cpp_params_file)
                self.schema.update(cpp_params)

        # Also check Source/Params for PeleC
        pelec_params_file = self.root / "Source" / "Params" / "_cpp_parameters"
        if pelec_params_file.exists() and pelec_params_file.is_file():
            cpp_params = self._parse_cpp_parameters_file(pelec_params_file)
            self.schema.update(cpp_params)

        # Phase 1: Build declaration map from directories
        print("Phase 1: Extracting variable declarations...")
        source_paths = []

        for dir_name in source_dirs:
            dir_path = self.root / dir_name
            if dir_path.exists() and dir_path.is_dir():
                source_paths.append(dir_path)

        if source_paths:
            self.declaration_map = DeclarationExtractor.extract_all_declarations(source_paths)
            print(f"  → Found {len(self.declaration_map)} unique variables")
        else:
            print("  ⚠️  No source directories found")
            self.declaration_map = {}

        # Phase 2: Scan for ParmParse calls
        # Sort to scan _cpp_parameters last (for precedence)
        print("Phase 2: Extracting ParmParse calls...")
        sorted_dirs = sorted(source_dirs, key=lambda d: 1 if '_cpp_parameters' in d else 0)

        for dir_name in sorted_dirs:
            dir_path = self.root / dir_name
            if not dir_path.exists():
                continue

            # Recursively find .cpp and .H files
            cpp_files = list(dir_path.rglob("*.cpp")) + list(dir_path.rglob("*.H"))
            for cpp_file in cpp_files:
                self._scan_file(cpp_file)

        # Apply config-defined build requirements (Amendment D.3)
        # For parameters without explicit #ifdef guards in source
        if solver_config and hasattr(solver_config, 'build_requirements'):
            print(f"Applying {len(solver_config.build_requirements)} build requirements...")
            applied = 0
            for param_name, required_flags in solver_config.build_requirements.items():
                if param_name in self.schema and not self.schema[param_name].get('build_flags'):
                    # Only add if no flags already detected from source
                    self.schema[param_name]['build_flags'] = required_flags
                    applied += 1
            print(f"  → Applied build_flags to {applied} parameters")
        else:
            print("  ⚠️  No solver_config or build_requirements")

        if solver_config and hasattr(solver_config, 'manual_schema_params'):
            manual_params = solver_config.manual_schema_params or {}
            print(f"Applying {len(manual_params)} manual schema params...")
            added = 0
            for param_name, param_info in manual_params.items():
                if param_name in self.schema:
                    continue
                self.schema[param_name] = {
                    'type': param_info.get('type', 'string'),
                    'required': param_info.get('required', False),
                    'is_array': param_info.get('is_array', False),
                    'build_flags': param_info.get('build_flags', []),
                    'default': param_info.get('default', None),
                    'source_file': param_info.get('source_file', 'manual_config'),
                    'source_type': 'manual',
                    'priority': self._get_param_priority(param_name),
                    'description': param_info.get('description'),
                }
                added += 1
            print(f"  → Added {added} manual schema params")
        else:
            print("  ⚠️  No solver_config or manual_schema_params")

        self._log_non_blocking_tier34_issues()
        return self.schema

    def _log_non_blocking_tier34_issues(self) -> None:
        """
        Log Tier 3/4 schema findings without blocking schema generation.

        Tier 3/4 are optional and informational. Their presence (or malformed
        priority tags) should be surfaced via logs only.
        """
        tier3_params: list[str] = []
        tier4_params: list[str] = []

        for param_name, param_data in self.schema.items():
            priority = str(param_data.get("priority", "tier4")).strip().lower()

            if priority == "tier3":
                tier3_params.append(param_name)
                continue
            if priority == "tier4":
                tier4_params.append(param_name)
                continue
            if priority in {"tier1", "tier2"}:
                continue

            # Unknown priority tags are informational only and treated as tier4.
            tier4_params.append(param_name)
            logger.warning(
                "Unknown priority '%s' for parameter '%s'; treating as tier4 non-blocking.",
                priority,
                param_name,
            )

        if tier3_params:
            logger.info(
                "Tier 3 non-blocking logging: %d optional parameter(s) detected.",
                len(tier3_params),
            )
        if tier4_params:
            logger.info(
                "Tier 4 non-blocking logging: %d informational parameter(s) detected.",
                len(tier4_params),
            )

    def _is_valid_param_name(self, name: str) -> bool:
        """
        Validate parameter name against AMReX/Pele conventions.

        Rejects:
        - Empty strings
        - Just '.' or '..'
        - Trailing dots
        - Non-alphanumeric characters (except underscores and dots)

        Args:
            name: Parameter name to validate

        Returns
        -------
            True if valid, False otherwise
        """
        if not name or not name.strip():
            return False

        name = name.strip()

        # Specific regressions found in SprayJet.cpp
        if name in ['.', '..']:
            return False

        # Formatting check - no trailing dots
        if name.endswith('.'):
            return False

        # Basic character check (alphanumeric, underscore, dot)
        # Allows "amr.n_cell", "pelec.chem_file"
        import re
        return re.match(r'^[a-zA-Z0-9_.]+$', name)

    def _scan_file(self, file_path: Path):
        """
        Scan a single C++ file for ParmParse calls.

        Uses declaration map for type inference (built in Phase 1).
        Falls back to inline backward search if declaration map misses.
        Captures get vs query semantics for required vs optional.

        Args:
            file_path: Path to C++ source file
        """
        try:
            content = file_path.read_text(errors='ignore')
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return

        lines = content.split('\n')

        # Track #ifdef blocks for build flag detection
        active_ifdefs = []
        ifdef_blocks = {}  # Maps line number → active #ifdef macros

        for line_num, line in enumerate(lines):
            stripped = line.strip()

            # Track #ifdef MACRO
            ifdef_match = re.match(r'#ifdef\s+(\w+)', stripped)
            if ifdef_match:
                macro = ifdef_match.group(1)
                # Normalize AMREX_USE_EB -> USE_EB
                if macro.startswith('AMREX_'):
                    macro = macro[6:]
                active_ifdefs.append(macro)

            # Track #ifndef MACRO
            ifndef_match = re.match(r'#ifndef\s+(\w+)', stripped)
            if ifndef_match:
                macro = '!' + ifndef_match.group(1)
                if macro.startswith('!AMREX_'):
                    macro = '!' + macro[7:]
                active_ifdefs.append(macro)

            # Track #endif
            if stripped.startswith('#endif') and active_ifdefs:
                active_ifdefs.pop()

            # Store active ifdefs for this line
            if active_ifdefs:
                ifdef_blocks[line_num] = list(active_ifdefs)

        # First, build a map of string variable assignments
        # Pattern: [const] std::string var_name = "value";
        # Used to resolve variable-based ParmParse declarations like: ParmParse pp(tag_prefix);
        string_vars = {}
        string_var_pattern = r'(?:const\s+)?std::string\s+(\w+)\s*=\s*"([^"]+)"'
        for match in re.finditer(string_var_pattern, content):
            var_name = match.group(1)
            var_value = match.group(2)
            string_vars[var_name] = var_value

        # Build namespace map from ParmParse declarations
        # Pattern: ParmParse pp("namespace") OR ParmParse pp(variable) OR ParmParse pp; (redeclaration)
        # Handles:
        # - ParmParse pp("namespace");   → string literal namespace
        # - ParmParse pp(tag_prefix);    → variable-based namespace (resolved via string_vars)
        # - ParmParse pp;                → no namespace (redeclaration)
        namespace_map = {}
        current_namespace = None

        # Updated pattern to match:
        # - ParmParse pp("namespace");   → group(1)=pp, group(2)="namespace", group(3)=None
        # - ParmParse pp(tag_prefix);    → group(1)=pp, group(2)=None, group(3)=tag_prefix
        # - ParmParse pp;                → group(1)=pp, group(2)=None, group(3)=None
        pp_decl_pattern = r'ParmParse\s+(\w+)\s*(?:\(\s*(?:"([^"]+)"|(\w+))\s*\))?'
        for match in re.finditer(pp_decl_pattern, content):
            var_name = match.group(1)  # e.g., pp or pp_amr
            namespace_literal = match.group(2)  # e.g., "amr" or None
            namespace_var = match.group(3)  # e.g., tag_prefix or None

            if namespace_literal:
                # ParmParse pp("namespace") - set the namespace mapping
                namespace_map[var_name] = namespace_literal
                current_namespace = namespace_literal
            elif namespace_var:
                # ParmParse pp(variable_name) - resolve variable to namespace
                namespace = string_vars.get(namespace_var)
                if namespace:
                    namespace_map[var_name] = namespace
                    current_namespace = namespace
            else:
                # ParmParse pp; (redeclaration without namespace)
                # Clear previous mapping so subsequent queries use top-level
                if var_name in namespace_map:
                    namespace_map.pop(var_name)
                current_namespace = None  # Reset current namespace

        # Find ParmParse calls
        # Pattern: pp.method("param_name", variable) OR pp.method("long_name", "short_name", variable)
        # Handles both 2-argument and 3-argument forms (for short parameter aliases)
        # Captures: (1)=pp_var, (2)=method, (3)=first_param, (4)=second_param_or_none, (5)=var_name
        # Example 2-arg: pp.query("max_level", max_level)          → groups: (pp, query, max_level, None, max_level)
        # Example 3-arg: pp.query("verbose", "v", verbose)         → groups: (pp, query, verbose, v, verbose)
        # Supports comprehensive AMReX_ParmParse.H method list from AMReX_ParmParse.H
        parmparse_pattern = r'(\w+)\.(get|query|getarr|queryarr|getkth|querykth|getktharr|queryktharr|getline|queryline|queryAdd|queryAddWithParser|getWithParser|queryWithParser|getarrWithParser|queryarrWithParser|getAsDouble|queryAsDouble|getarrAsDouble|queryarrAsDouble|gettable|querytable|get_enum_case_insensitive|query_enum_case_insensitive|get_enum_sloppy|query_enum_sloppy|add|addarr|set)\s*\(\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?\s*,\s*(\w+)'

        for match in re.finditer(parmparse_pattern, content):
            pp_var = match.group(1)           # e.g., pp, pp_amr
            method = match.group(2)           # 'get', 'query', 'queryAdd', 'getarr', 'queryarr', 'addarr', etc.
            param_name_1 = match.group(3)     # first parameter name (or long name in 3-arg form)
            param_name_2 = match.group(4)     # second parameter name only in 3-arg form (or None)
            var_name = match.group(5)         # C++ variable name

            # Use param_name_2 if it exists (3-arg form with short alias), else param_name_1
            param_name = param_name_2 if param_name_2 else param_name_1

            # Determine namespace
            namespace = namespace_map.get(pp_var, current_namespace)
            # No namespace means top-level
            full_name = param_name if not namespace else f"{namespace}.{param_name}"

            # Validate parameter name
            if not self._is_valid_param_name(full_name):
                continue

            # Skip if already in schema (from earlier file)
            if full_name in self.schema:
                continue

            # Phase 1: Use declaration map for type lookup (preferred)
            var_type = None
            if self.declaration_map:
                var_type = DeclarationExtractor.match_variable_to_declaration(
                    var_name, file_path, self.declaration_map
                )

            # Phase 2: Fallback to inline backward search if Phase 1 missed
            if not var_type and hasattr(self, '_detect_type_from_variable'):
                var_type = self._detect_type_from_variable(
                    content, var_name, match.start()
                )

            # Detect build flags from #ifdef blocks
            line_num = content[:match.start()].count('\n')
            build_flags = ifdef_blocks.get(line_num, [])

            # Extract additional metadata
            default_value = self._extract_default_value(content, var_name, match.start())
            source_type = self._classify_source_file(file_path)

            # Check for conflicts - prefer generated over manual
            if full_name in self.schema:
                existing = self.schema[full_name]
                if source_type == "generated" and existing.get("source_type") == "manual":
                    pass  # Overwrite with generated
                elif source_type == "manual" and existing.get("source_type") == "generated":
                    continue  # Keep generated, skip manual

            # Determine required/array based on ParmParse method semantics
            # From AMReX_ParmParse.H:
            # - get*/getWithParser/getline: required (must exist)
            # - query*/queryWithParser/queryline: optional (not required)
            # - *arr/Parser/Double/table: array-like or multi-value
            required = method in [
                'get', 'getarr', 'getkth', 'getktharr', 'getline',
                'getWithParser', 'getarrWithParser', 'getAsDouble',
                'getarrAsDouble', 'gettable',
                'get_enum_case_insensitive', 'get_enum_sloppy'
            ]
            is_array = method in [
                'getarr', 'queryarr', 'getkth', 'querykth',
                'getktharr', 'queryktharr', 'getline', 'queryline',
                'queryAdd', 'queryAddWithParser', 'addarr',
                'getarrWithParser', 'queryarrWithParser',
                'getarrAsDouble', 'queryarrAsDouble',
                'gettable', 'querytable'
            ]

            # Create schema entry with ALL fields
            lines = content.splitlines()
            description = self._extract_param_description(lines, line_num)
            self.schema[full_name] = {
                'type': var_type,
                'required': required,
                'is_array': is_array,
                'build_flags': build_flags,
                'default': default_value,
                'source_file': str(file_path.relative_to(self.root)),
                'source_type': source_type,
                'priority': self._get_param_priority(full_name),
                'description': description,
            }

        # Handle parseUserKey helpers (used for boundary conditions, etc.)
        # Pattern: parseUserKey(pp, "param", table, var, idx);
        parse_userkey_pattern = r'parseUserKey\(\s*(\w+)\s*,\s*"([^"]+)"\s*,\s*\w+\s*,\s*(\w+)'
        for match in re.finditer(parse_userkey_pattern, content):
            pp_var = match.group(1)
            param_name = match.group(2)
            var_name = match.group(3)

            namespace = namespace_map.get(pp_var, current_namespace)
            full_name = param_name if not namespace else f"{namespace}.{param_name}"

            if not self._is_valid_param_name(full_name):
                continue

            if full_name in self.schema:
                continue

            line_num = content[:match.start()].count('\n')
            build_flags = ifdef_blocks.get(line_num, [])
            source_type = self._classify_source_file(file_path)
            description = self._extract_param_description(content.splitlines(), line_num)

            # parseUserKey consumes string values from inputs (e.g., boundary flags).
            self.schema[full_name] = {
                'type': 'string',
                'required': False,
                'is_array': True,
                'build_flags': build_flags,
                'default': None,
                'source_file': str(file_path.relative_to(self.root)),
                'source_type': source_type,
                'priority': self._get_param_priority(full_name),
                'description': description,
            }


    def _detect_type_from_variable(self, content: str, var_name: str, context_start: int) -> str:
        """
        Detect C++ type from variable declaration.

        Args:
            content: Full file content
            var_name: Variable name to search for
            context_start: Position to start searching backwards from

        Returns
        -------
            Type string (e.g., 'int', 'Real', 'IntVect') or None
        """
        # Search backwards up to 1000 chars
        search_start = max(0, context_start - 1000)
        context = content[search_start:context_start]

        # Pattern: Type var_name; or Type var_name = ...;
        # Support C++ types: int, Real, IntVect, std::string, etc.
        type_pattern = rf'(\w+(?:::\w+)?)\s+{re.escape(var_name)}\s*[;=]'

        matches = list(re.finditer(type_pattern, context))
        if matches:
            # Take the last match (closest to our position)
            return matches[-1].group(1)

        return None

    def _parse_file(self, file_path: Path):
        """
        Parse single C++ file for ParmParse calls.

        Regex patterns:
        - ParmParse pp("namespace");
        - pp.get("param", var);
        - pp.query("param", var);
        - #ifdef MACRO blocks

        This is the legacy method - uses inline type detection.
        Kept for backward compatibility and fallback.
        """
        try:
            content = file_path.read_text(errors='ignore')

            # Track #ifdef blocks for build flag detection
            self.ifdef_stack = []
            ifdef_blocks = {}  # Maps line number → active #ifdef macros

            lines = content.split('\n')
            active_ifdefs = []

            for line_num, line in enumerate(lines):
                stripped = line.strip()

                # Track #ifdef MACRO
                ifdef_match = re.match(r'#ifdef\s+(\w+)', stripped)
                if ifdef_match:
                    macro = ifdef_match.group(1)
                    # Normalize AMREX_USE_EB -> USE_EB
                    if macro.startswith('AMREX_'):
                        macro = macro[6:]  # Remove 'AMREX_' prefix
                    active_ifdefs.append(macro)

                # Track #ifndef MACRO
                ifndef_match = re.match(r'#ifndef\s+(\w+)', stripped)
                if ifndef_match:
                    macro = '!' + ifndef_match.group(1)
                    if macro.startswith('!AMREX_'):
                        macro = '!' + macro[7:]
                    active_ifdefs.append(macro)

                # Track #endif
                if stripped.startswith('#endif') and active_ifdefs:
                    active_ifdefs.pop()

                # Store active ifdefs for this line
                if active_ifdefs:
                    ifdef_blocks[line_num] = list(active_ifdefs)

        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return

        # First, build a map of string variable assignments
        # Pattern: [const] std::string var_name = "value";
        # Used to resolve variable-based ParmParse declarations like: ParmParse pp(tag_prefix);
        string_vars = {}
        string_var_pattern = r'(?:const\s+)?std::string\s+(\w+)\s*=\s*"([^"]+)"'
        for match in re.finditer(string_var_pattern, content):
            var_name = match.group(1)
            var_value = match.group(2)
            string_vars[var_name] = var_value

        # Build namespace map from ParmParse declarations
        # Pattern: ParmParse pp("namespace") OR ParmParse pp(variable) OR ParmParse pp; (redeclaration)
        # Handles:
        # - ParmParse pp("namespace");   → string literal namespace
        # - ParmParse pp(tag_prefix);    → variable-based namespace (resolved via string_vars)
        # - ParmParse pp;                → no namespace (redeclaration)
        namespace_map = {}
        current_namespace = None

        # Updated pattern to match:
        # - ParmParse pp("namespace");   → group(1)=pp, group(2)="namespace", group(3)=None
        # - ParmParse pp(tag_prefix);    → group(1)=pp, group(2)=None, group(3)=tag_prefix
        # - ParmParse pp;                → group(1)=pp, group(2)=None, group(3)=None
        pp_decl_pattern = r'ParmParse\s+(\w+)\s*(?:\(\s*(?:"([^"]+)"|(\w+))\s*\))?'
        for match in re.finditer(pp_decl_pattern, content):
            var_name = match.group(1)  # e.g., pp or pp_amr
            namespace_literal = match.group(2)  # e.g., "amr" or None
            namespace_var = match.group(3)  # e.g., tag_prefix or None

            if namespace_literal:
                # ParmParse pp("namespace") - set the namespace mapping
                namespace_map[var_name] = namespace_literal
                current_namespace = namespace_literal
            elif namespace_var:
                # ParmParse pp(variable_name) - resolve variable to namespace
                namespace = string_vars.get(namespace_var)
                if namespace:
                    namespace_map[var_name] = namespace
                    current_namespace = namespace
            else:
                # ParmParse pp; (redeclaration without namespace)
                # Clear previous mapping so subsequent queries use top-level
                if var_name in namespace_map:
                    namespace_map.pop(var_name)
                current_namespace = None  # Reset current namespace

        # Find ALL ParmParse calls with unified pattern
        # Pattern: pp.method("param_name", variable) OR pp.method("long_name", "short_name", variable)
        # Handles both 2-argument and 3-argument forms (for short parameter aliases)
        # Captures: (1)=pp_var, (2)=method, (3)=first_param, (4)=second_param_or_none, (5)=var_name
        # Example 2-arg: pp.query("max_level", max_level)          → groups: (pp, query, max_level, None, max_level)
        # Example 3-arg: pp.query("verbose", "v", verbose)         → groups: (pp, query, verbose, v, verbose)
        # Supports comprehensive AMReX_ParmParse.H method list from AMReX_ParmParse.H
        parmparse_pattern = r'(\w+)\.(get|query|getarr|queryarr|getkth|querykth|getktharr|queryktharr|getline|queryline|queryAdd|queryAddWithParser|getWithParser|queryWithParser|getarrWithParser|queryarrWithParser|getAsDouble|queryAsDouble|getarrAsDouble|queryarrAsDouble|gettable|querytable|get_enum_case_insensitive|query_enum_case_insensitive|get_enum_sloppy|query_enum_sloppy|add|addarr|set)\s*\(\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?\s*,\s*(\w+)'

        for match in re.finditer(parmparse_pattern, content):
            pp_var = match.group(1)           # e.g., pp, pp_amr
            method = match.group(2)           # 'get', 'query', 'queryAdd', 'getarr', 'queryarr', 'addarr', etc.
            param_name_1 = match.group(3)     # first parameter name (or long name in 3-arg form)
            param_name_2 = match.group(4)     # second parameter name only in 3-arg form (or None)
            var_name = match.group(5)         # C++ variable name

            # Use param_name_2 if it exists (3-arg form with short alias), else param_name_1
            param_name = param_name_2 if param_name_2 else param_name_1

            # Determine namespace
            namespace = namespace_map.get(pp_var, current_namespace)
            # No namespace means top-level parameter
            full_name = param_name if not namespace else f"{namespace}.{param_name}"

            # Validate parameter name
            if not self._is_valid_param_name(full_name):
                continue

            # Skip if already in schema (from earlier file)
            if full_name in self.schema:
                continue

            # Phase 1: Try declaration map (if available)
            cpp_type = None
            if self.declaration_map:
                cpp_type = DeclarationExtractor.match_variable_to_declaration(
                    var_name, file_path, self.declaration_map
                )

            # Phase 2: Fallback to inline backward search
            if not cpp_type:
                cpp_type = self._detect_type_from_variable(
                    content, var_name, match.start()
                )

            # Detect build flags from #ifdef blocks
            line_num = content[:match.start()].count('\n')
            build_flags = ifdef_blocks.get(line_num, [])

            # Determine required/array based on ParmParse method semantics
            # From AMReX_ParmParse.H:
            # - get*/getWithParser/getline: required (must exist)
            # - query*/queryWithParser/queryline: optional (not required)
            # - *arr/Parser/Double/table: array-like or multi-value
            required = method in [
                'get', 'getarr', 'getkth', 'getktharr', 'getline',
                'getWithParser', 'getarrWithParser', 'getAsDouble',
                'getarrAsDouble', 'gettable',
                'get_enum_case_insensitive', 'get_enum_sloppy'
            ]
            is_array = method in [
                'getarr', 'queryarr', 'getkth', 'querykth',
                'getktharr', 'queryktharr', 'getline', 'queryline',
                'queryAdd', 'queryAddWithParser', 'addarr',
                'getarrWithParser', 'queryarrWithParser',
                'getarrAsDouble', 'queryarrAsDouble',
                'gettable', 'querytable'
            ]

            # Create schema entry with ALL fields
            lines = content.splitlines()
            description = self._extract_param_description(lines, line_num)
            self.schema[full_name] = {
                'type': cpp_type,
                'required': required,  # Source Code Truth
                'is_array': is_array,  # Array detection
                'build_flags': build_flags,
                'source_file': str(file_path.relative_to(self.root)),
                'description': description,
            }

    def load_build_config(self) -> dict[str, str]:
        """
        Parse build configuration from GNUmakefile or CMakeLists.txt.

        Reuses Indexing Engine: Build Metadata Extensions logic from amrex_metadata_utils.

        Returns
        -------
            Dict of build variables (e.g., {'DIM': '3', 'USE_EB': 'TRUE'})
        """
        try:
            raw_config = extract_generic_build_config(self.root)

            # Normalize keys to uppercase for consistency
            # Indexing Engine: Build Metadata Extensions returns lowercase, but AMReX conventions use uppercase
            # Preserve boolean values as strings (AMReX uses TRUE/FALSE)
            normalized = {}
            for key, value in raw_config.items():
                # Convert Python bool to AMReX string format
                if isinstance(value, bool):
                    value = "TRUE" if value else "FALSE"
                elif isinstance(value, int):
                    value = str(value)
                normalized[key.upper()] = value

            # Also check for CMakeLists.txt
            cmake_file = self.root / "CMakeLists.txt"
            if cmake_file.exists():
                cmake_config = self._parse_cmake(cmake_file)
                normalized.update(cmake_config)

            # Also parse GNUmakefile directly for ALL variables
            makefile = self.root / "GNUmakefile"
            if makefile.exists():
                makefile_config = self._parse_makefile(makefile)
                # Our parser takes precedence for comprehensive extraction
                normalized.update(makefile_config)

            self.build_config = normalized
            return self.build_config
        except Exception as e:
            logger.warning(f"Could not parse build config: {e}")
            return {}

    def save(
        self,
        output_path: Path,
        solver_name: str = "amrex",
        schema_version: int = 1
    ) -> Path:
        """
        Save schema to JSON file with version suffix.

        Parameters
        ----------
        output_path : Path
            Directory path to save schema.
        solver_name : str, optional
            Name for schema file (e.g., "pelec").

        Returns
        -------
        Path
            Path to the saved schema file.
        """
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        # Get commit hash for versioning
        commit_hash = self._get_commit_hash()

        # Filename: solver_schema_<hash>.json
        filename = f"{solver_name}_schema_{commit_hash}.json"
        output_path = output_path / filename

        from datetime import datetime, timezone
        # Keep legacy top-level parameter keys for compatibility while also
        # writing wrapped metadata/parameters for newer consumers.
        output_data = dict(self.schema)
        output_data["metadata"] = {
            "solver": solver_name,
            "schema_version": schema_version,
            "repo_commit": commit_hash,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        output_data["parameters"] = self.schema

        # Save
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Saved schema to {output_path}")
        return output_path




    def _extract_default_value(self, content: str, var_name: str, pos: int):
        """Extract default value from variable declaration."""
        # Look backward for initialization (up to 1000 chars)
        search_context = content[max(0, pos-1000):pos]

        # Pattern: Type var_name = value;
        pattern = rf'\b{re.escape(var_name)}\s*=\s*([^;]+);'
        match = re.search(pattern, search_context)

        if match:
            value_str = match.group(1).strip()

            # Handle vector initialization: {1, 2, 3}
            if value_str.startswith('{'):
                values = re.findall(r'[\d.]+', value_str)
                return [float(v) if '.' in v else int(v) for v in values]

            # Handle single numeric value
            try:
                return float(value_str) if '.' in value_str else int(value_str)
            except ValueError:
                return value_str  # Keep as string

        return None

    def _classify_source_file(self, file_path: Path) -> str:
        """Determine if file is generated or manual."""
        # Use relative path from repo root to avoid false positives from tmp dirs
        try:
            rel_path = str(file_path.relative_to(self.root))
        except ValueError:
            rel_path = str(file_path)

        if "_cpp_parameters" in rel_path or "generated" in rel_path.lower():
            return "generated"
        elif file_path.suffix == ".H":
            return "header"
        else:
            return "manual"

    def _get_param_priority(self, param_name: str) -> str:
        """Assign priority tier to parameter."""
        tier1 = {"pelec.cfl", "amr.n_cell", "pelec.do_react"}
        tier2 = {"amr.max_level", "amr.blocking_factor"}

        if param_name in tier1:
            return "tier1"
        elif param_name in tier2:
            return "tier2"
        else:
            return "tier3"

    def _extract_param_description(self, lines: list[str], line_num: int) -> str | None:
        """Extract nearby comment text for a parameter definition."""
        if line_num < 0 or line_num >= len(lines):
            return None
        line = lines[line_num]
        if '//' in line:
            desc = line.split('//', 1)[1].strip()
            if desc:
                return desc
        if '/*' in line and '*/' in line:
            desc = line.split('/*', 1)[1].split('*/', 1)[0].strip()
            if desc:
                return desc
        for offset in range(1, 3):
            idx = line_num - offset
            if idx < 0:
                break
            prev = lines[idx].strip()
            if prev.startswith('//'):
                desc = prev[2:].strip()
                if desc:
                    return desc
            if prev.startswith('/*') and prev.endswith('*/'):
                desc = prev[2:-2].strip()
                if desc:
                    return desc
        return None

    def _parse_cpp_parameters_file(self, file_path: Path) -> dict[str, dict[str, Any]]:
        """
        Parse PeleC/AMReX _cpp_parameters definition file.

        This is the source of truth that generates pelec_queries.H and pelec_defaults.H.
        Format:
            @namespace: pelec PeleC static
            param_name    type    default_value
        """
        import re
        params = {}
        content = file_path.read_text()

        # Extract namespace from @namespace directive
        namespace_match = re.search(r'@namespace:\s+(\w+)', content)
        if not namespace_match:
            return params

        namespace = namespace_match.group(1)
        print(f"  → Parsing {file_path.name}: namespace='{namespace}'")

        # Parse parameter definitions (skip comments and directives)
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('@'):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            param_name = parts[0]
            param_type = parts[1]
            default_value = ' '.join(parts[2:]) if len(parts) > 2 else None

            # Handle dual names: (input_name, cpp_var)
            if param_name.startswith('(') and ')' in param_name:
                param_name = param_name.strip('()').split(',')[0].strip()

            full_name = f"{namespace}.{param_name}"

            # Map _cpp_parameters types to schema types
            type_map = {
                'int': 'int',
                'Real': 'Real',
                'bool': 'bool',
                'string': 'string',
                'dim_array': 'RealVect'
            }

            # Convert default to proper type
            converted_default = default_value
            if default_value:
                if param_type == 'Real':
                    with contextlib.suppress(ValueError):
                        converted_default = float(default_value)
                elif param_type == 'int':
                    with contextlib.suppress(ValueError):
                        converted_default = int(default_value)
                elif param_type == 'bool':
                    converted_default = default_value.lower() in ['true', '1']

            params[full_name] = {
                'type': type_map.get(param_type, param_type),
                'default': converted_default,
                'required': False,  # All _cpp_parameters have defaults
                'is_array': param_type in ['dim_array'],
                'build_flags': [],
                'source_file': str(file_path.relative_to(self.root)),
                'source_type': 'generated',
                'priority': self._get_param_priority(full_name)
            }

        print(f"    Found {len(params)} parameters")
        return params

    def _parse_makefile(self, makefile: Path) -> dict[str, str]:
        """
        Parse GNUmakefile for all build variables (AMReX-compliant).

        Based on AMReX Tools/GNUMake/README.md specification.

        Extracts:
        - VAR = value (standard assignment)
        - VAR := value (immediate assignment)
        - Preserves TRUE/FALSE as strings (AMReX convention)
        - Skips comments (#) and blank lines
        - Captures both standard AMReX vars (DIM, USE_MPI, etc.)
          and custom application vars (USE_EB, USE_REACTIONS, etc.)

        Returns
        -------
            Dict of all build variables found
        """
        config = {}
        try:
            file_content = makefile.read_text()

            # Pattern: VAR = value or VAR := value
            # Handles:
            # - Optional whitespace around = or :=
            # - Captures everything after = as value
            # - Works with both assignments
            var_pattern = r'^(\w+)\s*:?=\s*(.*)$'

            for line in file_content.split('\n'):
                # Skip comments (lines starting with #)
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue

                # Remove inline comments (e.g., "DIM = 3  # dimension")
                if '#' in stripped:
                    stripped = stripped.split('#')[0].strip()

                match = re.match(var_pattern, stripped)
                if match:
                    var_name = match.group(1)
                    value = match.group(2).strip()

                    # Remove quotes if present (make allows VAR = "value")
                    if value.startswith('"') and value.endswith('"') or value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    # Skip empty values
                    if not value:
                        continue

                    # Normalize variable name to uppercase (AMReX convention)
                    # Preserves both standard (USE_MPI) and custom (USE_EB) vars
                    config[var_name.upper()] = value

        except Exception as e:
            logger.debug(f"Error parsing makefile {makefile}: {e}")

        return config

    def _parse_cmake(self, cmake_file: Path) -> dict[str, str]:
        """
        Parse CMakeLists.txt for build variables.

        Extracts:
        - set(VAR value)
        - option(VAR "description" value)

        Returns
        -------
            Dict of build variables
        """
        config = {}
        try:
            content = cmake_file.read_text()

            # Pattern: set(AMReX_SPACEDIM 3)
            set_pattern = r'set\s*\(\s*(\w+)\s+(\w+)'
            for match in re.finditer(set_pattern, content):
                var_name = match.group(1)
                value = match.group(2)
                # Normalize AMReX_SPACEDIM -> SPACEDIM
                if var_name.startswith('AMReX_'):
                    var_name = var_name.replace('AMReX_', '')
                config[var_name.upper()] = value

            # Pattern: option(AMReX_EB "Enable EB" ON)
            option_pattern = r'option\s*\(\s*(\w+)\s+"[^"]*"\s+(\w+)'
            for match in re.finditer(option_pattern, content):
                var_name = match.group(1)
                value = match.group(2)
                if var_name.startswith('AMReX_'):
                    var_name = var_name.replace('AMReX_', '')
                config[var_name.upper()] = value

        except Exception as e:
            logger.debug(f"Error parsing CMake: {e}")

        return config

    def _get_commit_hash(self) -> str:
        """Get short git commit hash for versioning."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def _parse_make_help(self) -> dict[str, Any]:
        """
        Parse 'make help' output to extract build capabilities.

        Real AMReX 'make help' shows active configuration in CPPFLAGS
        as preprocessor defines (e.g., -DAMREX_USE_MPI -DAMREX_SPACEDIM=3)

        Returns
        -------
            Dict of build capabilities with their values
        """
        capabilities = {}

        try:
            result = subprocess.run(
                ['make', 'help'],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.debug(f"make help failed: {result.stderr}")
                return capabilities

            output = result.stdout
            logger.debug(f"make help output length: {len(output)}")
            logger.debug("Looking for CPPFLAGS...")

            # Find CPPFLAGS line
            # Format: "    CPPFLAGS      = -DAMREX_USE_MPI -DAMREX_SPACEDIM=3 ..."
            for line in output.split('\\n'):
                if 'CPPFLAGS' in line and '=' in line:
                    # Extract the value part after =
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        cppflags = parts[1].strip()

                        # Parse -D flags
                        # Pattern: -DVAR or -DVAR=value
                        define_pattern = r'-D(\w+)(?:=(\S+))?'

                        for match in re.finditer(define_pattern, cppflags):
                            var_name = match.group(1)
                            value = match.group(2) if match.group(2) else 'TRUE'

                            # Normalize AMReX prefixes
                            # AMREX_USE_MPI -> USE_MPI (for consistency)
                            normalized_name = var_name
                            if var_name.startswith('AMREX_'):
                                normalized_name = var_name.replace('AMREX_', '')

                            # Store both versions for compatibility
                            capabilities[var_name] = value
                            if normalized_name != var_name:
                                capabilities[normalized_name] = value

        except subprocess.TimeoutExpired:
            logger.warning("make help timed out")
        except Exception as e:
            logger.debug(f"Error running make help: {e}")

        logger.debug(f"Extracted {len(capabilities)} capabilities")
        return capabilities

    def _parse_cmake_cache(self) -> dict[str, str]:
        """
        Parse CMake cache to extract build variables.

        Runs 'cmake -L -N' to list cache variables without running cmake.

        Returns
        -------
            Dict of build variables
        """
        config = {}

        try:
            # Check if CMakeLists.txt exists
            cmake_file = self.root / "CMakeLists.txt"
            if not cmake_file.exists():
                return config

            # Try to read from existing cache first
            cache_file = self.root / "CMakeCache.txt"
            if cache_file.exists():
                content = cache_file.read_text()

                # Parse cache entries
                # Format: VAR:TYPE=value
                cache_pattern = r'^\s*(\w+):(\w+)=(.*)$'

                for line in content.split('\n'):
                    if line.startswith('#') or not line.strip():
                        continue

                    match = re.match(cache_pattern, line)
                    if match:
                        var_name = match.group(1)
                        var_type = match.group(2)
                        value = match.group(3)

                        # Normalize AMReX prefixes
                        normalized_name = var_name
                        if var_name.startswith('AMReX_'):
                            normalized_name = var_name.replace('AMReX_', '')
                        if var_name.startswith('PELE_'):
                            normalized_name = var_name.replace('PELE_', '')

                        # Convert CMake bool to AMReX convention
                        if var_type == 'BOOL':
                            if value.upper() in ['ON', '1', 'TRUE', 'YES']:
                                value = 'TRUE'
                            else:
                                value = 'FALSE'

                        config[var_name] = value
                        if normalized_name != var_name:
                            config[normalized_name] = value
            else:
                # No cache file, try cmake -L (requires cmake to be installed)
                try:
                    result = subprocess.run(
                        ['cmake', '-L', '-N', '.'],
                        cwd=self.root,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if result.returncode == 0:
                        # Parse output
                        for line in result.stdout.split('\n'):
                            if ':' in line and '=' in line:
                                parts = line.split(':', 1)
                                if len(parts) == 2:
                                    var_name = parts[0].strip()
                                    rest = parts[1]
                                    if '=' in rest:
                                        type_and_val = rest.split('=', 1)
                                        value = type_and_val[1].strip()
                                        config[var_name] = value

                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

        except Exception as e:
            logger.debug(f"Error parsing CMake cache: {e}")

        return config

    def _get_active_build_vars(
        self,
        case_path: Path,
        var_names: list[str]
    ) -> dict[str, str]:
        """
        Query active build variables for a specific case using make print-VAR.

        Args:
            case_path: Path to case directory with GNUmakefile
            var_names: List of variable names to query

        Returns
        -------
            Dict of active variable values
        """
        active_vars = {}

        # Check if GNUmakefile exists
        makefile = Path(case_path) / "GNUmakefile"
        if not makefile.exists():
            logger.debug(f"No GNUmakefile in {case_path}")
            return active_vars

        # Query each variable using make print-VAR
        for var_name in var_names:
            try:
                result = subprocess.run(
                    ['make', f'print-{var_name}'],
                    cwd=case_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    output = result.stdout.strip()

                    # Parse output: "VAR = value"
                    if '=' in output:
                        parts = output.split('=', 1)
                        if len(parts) == 2:
                            value = parts[1].strip()
                            active_vars[var_name] = value

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            except Exception as e:
                logger.debug(f"Error querying {var_name}: {e}")

        return active_vars

    def build_system_schema(self, method: str = "source_scan") -> dict[str, Any]:
        """
        Pass 1: Build complete system schema.

        Discovers all possible parameters from source code and build system.

        Parameters
        ----------
        method : str, optional
            "source_scan" (parse C++) or "ctags" (use make tags).

        Returns
        -------
        Dict[str, Any]
            Schema with ``build`` capabilities and ``params`` runtime parameters.
        """
        schema = {
            'build': {},
            'params': {}
        }

        # Discover build capabilities
        # Try make help first
        build_caps = self._parse_make_help()
        if not build_caps:
            # Fallback to parsing GNUmakefile/CMake
            build_caps = self.load_build_config()

        schema['build'] = build_caps

        # Scan source code for parameters
        if method == "source_scan":
            source_dirs = ['Src', 'Source', 'Support']
            self.scan_source_code(source_dirs)
            schema['params'] = self.schema.copy()
        # else: ctags method not implemented yet

        logger.info(
            f"System schema: {len(schema['build'])} build flags, "
            f"{len(schema['params'])} runtime parameters"
        )

        return schema

    def apply_case_customization(
        self,
        system_schema: dict[str, Any],
        case_path: Path
    ) -> dict[str, Any]:
        """
        Pass 2: Filter system schema for specific case.

        Parameters
        ----------
        system_schema : Dict[str, Any]
            Full system schema from build_system_schema().
        case_path : Path
            Case directory.

        Returns
        -------
        Dict[str, Any]
            Case schema with ``flags`` and active ``params``.
        """
        case_schema = {
            'flags': {},
            'params': {}
        }

        # Get active build flags for this case
        if 'build' in system_schema:
            var_names = list(system_schema['build'].keys())
            active_flags = self._get_active_build_vars(case_path, var_names)
            case_schema['flags'] = active_flags

        # Filter parameters based on dependencies
        if 'params' in system_schema:
            for param_name, param_data in system_schema['params'].items():
                # Check if parameter's dependencies are satisfied
                deps = param_data.get('dependencies', [])

                is_active = True
                for dep in deps:
                    # Check if dependency is enabled
                    if dep in case_schema['flags']:
                        dep_value = case_schema['flags'][dep]
                        if dep_value not in ['TRUE', 'ON', '1', 'YES']:
                            is_active = False
                            break
                    else:
                        # Dependency not found - assume inactive
                        is_active = False
                        break

                if is_active:
                    case_schema['params'][param_name] = param_data.copy()

        logger.info(
            f"Case schema: {len(case_schema['params'])}/{len(system_schema.get('params', {}))} "
            f"parameters active"
        )

        return case_schema




def build_with_auto_compose(repo_path: Path, schema_dir: Path) -> Path:
    """
    Build and compose schemas automatically using dependency discovery.

    Workflow:
    1. Discover dependencies from .gitmodules (or dependencies.json)
    2. Build schema for each dependency
    3. Build schema for main repo
    4. Compose all schemas in dependency order

    Parameters
    ----------
    repo_path : Path
        Path to the main repository.
    schema_dir : Path
        Directory to write schemas.

    Returns
    -------
    Path
        Path to the composed schema file.
    """
    from dependency_discovery import DependencyDiscovery

    print("=" * 70)
    print("Auto-Compose Schema Build")
    print("=" * 70)
    print(f"Repository: {repo_path.name}")

    # Step 1: Discover dependencies
    print(f"\n{'='*70}")
    print("Step 1: Discovering Dependencies")
    print("=" * 70)

    deps = DependencyDiscovery.discover(repo_path)

    if deps:
        print(f"\nFound {len(deps)} dependencies:")
        for dep in deps:
            print(f"  • {dep}")
    else:
        print("\n⚠️  No dependencies found - building single schema")

    # Step 2: Build schemas for all dependencies
    print(f"\n{'='*70}")
    print("Step 2: Building Schemas")
    print("=" * 70)

    built_schemas = []

    for dep in deps:
        if dep.path and dep.path.exists():
            print(f"\nBuilding schema for {dep.name}...")
            builder = SchemaBuilder(dep.path)

            dep_config = _resolve_solver_config(dep.path)
            builder.scan_source_code(dep_config.schema_source_patterns, dep_config)

            if builder.schema:
                schema_path = builder.save(
                    schema_dir,
                    solver_name=dep.name,
                    schema_version=dep_config.schema_version
                )
                built_schemas.append((dep.name, schema_path))
                print(f"  ✅ Saved: {schema_path.name} ({len(builder.schema)} params)")
            else:
                print(f"  ⚠️  No parameters found in {dep.name}")
        else:
            print(f"  ⚠️  Skipping {dep.name} (path not found)")

    # Build schema for main repo
    print(f"\nBuilding schema for {repo_path.name}...")
    builder = SchemaBuilder(repo_path)

    solver_config = _resolve_solver_config(repo_path)
    builder.scan_source_code(solver_config.schema_source_patterns, solver_config)

    if builder.schema:
        schema_path = builder.save(
            schema_dir,
            solver_name=repo_path.name,
            schema_version=solver_config.schema_version
        )
        built_schemas.append((repo_path.name, schema_path))
        print(f"  ✅ Saved: {schema_path.name} ({len(builder.schema)} params)")

    # Step 3: Compose schemas
    if len(built_schemas) > 1:
        print(f"\n{'='*70}")
        print("Step 3: Composing Schemas")
        print("=" * 70)

        composer = SchemaComposer()
        schemas_to_compose = []
        dep_names = []

        # Load schemas in dependency order
        order = DependencyDiscovery.get_composition_order(deps)
        order.append(repo_path.name.lower())  # Add main repo at end

        print(f"\nComposition order: {' → '.join(order)}")

        for pkg_name in order:
            # Find the schema file for this package
            for name, path in built_schemas:
                if name.lower() == pkg_name.lower():
                    data = json.loads(path.read_text())
                    # Handle both wrapped and unwrapped schemas
                    params = data.get('parameters', data)
                    schemas_to_compose.append(params)
                    dep_names.append(name)
                    print(f"  ✅ Loaded {name}: {len(params)} parameters")
                    break

        # Compose
        composed = composer.compose(schemas_to_compose, solver_name=repo_path.name)

        # Save composed schema
        from datetime import datetime, timezone

        def _get_full_commit(path: Path) -> str:
            try:
                result = subprocess.run(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout.strip()
            except Exception:
                return "unknown"

        repo_commits = {}
        for dep in deps:
            if dep.commit:
                repo_commits[dep.name.lower()] = dep.commit
        repo_commits[repo_path.name.lower()] = _get_full_commit(repo_path)

        schema_version = solver_config.schema_version
        ordered_names = [name.lower() for name in dep_names]
        name_parts = []
        for name in ordered_names:
            commit = repo_commits.get(name, "unknown")
            name_parts.append(f"{name}{commit[:7]}")

        name_suffix = "_".join(name_parts)
        output_path = schema_dir / f"{repo_path.name.lower()}_complete_v{schema_version}_{name_suffix}.json"

        output_data = {
            "metadata": {
                "solver": repo_path.name,
                "schema_version": schema_version,
                "composed_from": dep_names,
                "composition_method": "auto-compose (gitmodules)",
                "total_parameters": len(composed),
                "repo_commits": repo_commits,
                "generated_at": datetime.now(timezone.utc).isoformat()
            },
            "parameters": composed
        }

        output_path.write_text(json.dumps(output_data, indent=2))

        print(f"\n{'='*70}")
        print("✅ Composition Complete")
        print("=" * 70)
        print(f"Composed schema: {output_path.name}")
        print(f"Total parameters: {len(composed)}")

        # Show parameter breakdown by namespace
        from collections import defaultdict
        by_namespace = defaultdict(int)
        for param in composed:
            namespace = param.split('.')[0]
            by_namespace[namespace] += 1

        print("\nBy namespace:")
        for ns, count in sorted(by_namespace.items(), key=lambda x: -x[1]):
            print(f"  {ns:20} {count:4} parameters")

        return output_path
    else:
        print("\n⚠️  Only one schema built - no composition needed")
        return built_schemas[0][1] if built_schemas else None


def main() -> None:
    """
    Run the schema generation CLI.

    Returns
    -------
    None
        Executes the CLI workflow.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate AMReX parameter schemas from C++ source (Input Writer: Schema Scraper)"
    )
    parser.add_argument(
        "repo_path",
        type=Path,
        help="Path to AMReX/Pele solver repository root"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("database/schemas"),
        help="Output directory for JSON schemas (default: database/schemas)"
    )
    parser.add_argument(
        "--solver",
        type=str,
        help="Solver name (pelec, warpx, etc.) - auto-detected if not provided"
    )

    args = parser.parse_args()

    # Validate repo path
    if not args.repo_path.exists():
        print(f"Error: Repository path not found: {args.repo_path}")
        sys.exit(1)

    # Build schema
    print(f"Building schema for: {args.repo_path}")
    builder = SchemaBuilder(args.repo_path)

    # Scan source code
    print("Scanning source code...")
    source_dirs = ['Source', 'Src', 'Source/Src_nd']
    builder.scan_source_code(source_dirs)

    # Load build config
    print("Loading build configuration...")
    build_config = builder.load_build_config()
    print(f"  Found {len(build_config)} build variables")

    # Determine solver name
    solver_name = args.solver
    if not solver_name:
        # Auto-detect from path
        repo_name = args.repo_path.name.lower()
        if 'pelec' in repo_name:
            solver_name = 'pelec'
        elif 'warpx' in repo_name:
            solver_name = 'warpx'
        elif 'erf' in repo_name:
            solver_name = 'erf'
        else:
            solver_name = 'amrex'

    # Save schema
    print(f"Saving schema for {solver_name}...")
    output_path = builder.save(args.output, solver_name)

    print(f"✅ Schema saved to: {output_path}")
    print(f"   Parameters extracted: {len(builder.schema)}")



if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Build schema from C++ source code',
        epilog='Examples:\\n'
               '  Single schema:  python build_schema.py ../PeleC\\n'
               '  Auto-compose:   python build_schema.py ../PeleC --auto-compose',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('repo_path', type=Path, help='Path to repository')
    parser.add_argument('--output', type=Path, default=Path('database/schemas'),
                       help='Output directory for schemas (default: database/schemas)')
    parser.add_argument('--solver', type=str,
                       help='Solver name (default: auto-detect from repo)')
    parser.add_argument('--auto-compose', action='store_true',
                       help='Auto-discover dependencies and compose complete schema')

    args = parser.parse_args()

    schema_dir = args.output
    schema_dir.mkdir(exist_ok=True, parents=True)

    if args.auto_compose:
        # Auto-discover and compose
        composed_path = build_with_auto_compose(args.repo_path, schema_dir)
        if composed_path:
            print(f"\\n{'='*70}")
            print("✅ Auto-compose complete!")
            print(f"{'='*70}")
            print(f"Schema: {composed_path}")
    else:
        # Single schema build
        print(f"Building schema for: {args.repo_path}")
        print("Scanning source code...")

        builder = SchemaBuilder(args.repo_path)

        # Load solver config based on repo name
        solver_config = _resolve_solver_config(args.repo_path)
        builder.scan_source_code(solver_config.schema_source_patterns, solver_config)

        solver_name = args.solver or args.repo_path.name
        schema_path = builder.save(schema_dir, solver_name=solver_name)

        print(f"\\n✅ Schema saved to: {schema_path}")
        print(f"   Parameters extracted: {len(builder.schema)}")
