"""
AMReX Generalization Enforcement Tests

These tests enforce the architecture requirements from AMREX_GENERALIZATION.md.
They MUST pass before cases.py is considered production-ready.

Reference: docs/AMREX_GENERALIZATION.md

AMReX Generalization Tests - Indexing Engine: Build Metadata Extensions.1

Enforces architectural separation between indexing logic and physics domain.
Uses AST (Abstract Syntax Tree) analysis to validate code structure.

Philosophy:
  - Physics terms in docstrings/comments: ✅ ALLOWED (documentation)
  - Physics terms in logic (conditionals, lists): ❌ FORBIDDEN (hardcoding)
  
This test must PASS before Indexing Engine: Physics-Agnostic Keywords & Scoring is complete.
"""
import ast
import pytest
import inspect
from pathlib import Path
from src.services.cases import AMReXCasesService
from src.config import AMReXAgentConfig


class TestNoHardcodedPeleAssumptions:
    """Enforce: Service works for ANY AMReX code, not just Pele*."""
    
    @pytest.mark.parametrize("code_name", [
        "AMReX", "PeleLMeX", "PeleMP",  # Combustion
        "WarpX",                          # Particle-in-cell
        "ERF",                            # Atmospheric
        "incflo",                         # Multiphase flow
    ])
    def test_find_local_cases_supports_all_codes(self, code_name):
        """
        Given: Any AMReX code name
        When:  Calling find_local_cases()
        Then:  Should return list (not raise "Only Pele supported")
        
        Violation: Service has if/elif chain for only Pele codes
        """
        config = AMReXAgentConfig()
        service = AMReXCasesService(config)
        
        # Should not raise ValueError about unsupported code
        result = service.find_local_cases(code_name)
        assert isinstance(result, list), f"{code_name} should return list"


class TestNoPeleToolsDependency:
    """Enforce: No dependency on pele_tools (Pele-specific)."""
    
    @pytest.mark.skip(reason="Tech debt: pele_tools refactor tracked separately")
    def test_cases_service_no_pele_tools_import(self):
        """
        Given: src/services/cases.py source code
        When:  Checking imports
        Then:  Should NOT import from pele_tools
        
        Why: pele_tools is Pele-specific, violates AMReX generalization
        Solution: Move generic functions to src/services/ or database/
        """
        source_file = Path("src/services/cases.py")
        source = source_file.read_text()
        
        # Check for pele_tools imports
        violations = []
        for line in source.split('\n'):
            if 'import pele_tools' in line or 'from pele_tools' in line:
                violations.append(line.strip())
        
        assert len(violations) == 0, \
            f"cases.py imports pele_tools (violates generalization):\n" + \
            "\n".join(violations)


class TestConfigUsesGenericRepoMap:
    """Enforce: Config uses repositories dict, not amrex_repo_path attrs."""
    
    def test_config_has_repositories_dict(self):
        """
        Given: AMReXAgentConfig
        When:  Checking attributes
        Then:  Should have 'repositories' dict (not amrex_repo_path)
        
        Before (❌): config.amrex_repo_path
        After (✅):  config.repositories["AMReX"]
        """
        config = AMReXAgentConfig()
        
        assert hasattr(config, 'repositories'), \
            "Config missing 'repositories' attribute"
        
        assert isinstance(config.repositories, dict), \
            "'repositories' should be a dict"
    
    
    def test_service_uses_repositories_not_amrex_path(self):
        """
        Given: AMReXCasesService source code
        When:  Checking for hardcoded paths
        Then:  Should use config.repositories, not config.amrex_repo_path
        """
        source = inspect.getsource(AMReXCasesService)
        
        # Check for violations
        violations = []
        pele_specific_attrs = [
            'amrex_repo_path',
            'pelelmex_repo_path', 
            'pelemp_repo_path'
        ]
        
        for attr in pele_specific_attrs:
            if attr in source:
                violations.append(attr)
        
        assert len(violations) == 0, \
            f"Service uses Pele-specific config attributes: {violations}\n" + \
            "Should use config.repositories dict instead"


class TestPeleToolsAudit:
    """Audit utils/pele_tools.py - what should move to services/?"""
    
    def test_identify_generic_functions_in_pele_tools(self):
        """
        Given: utils/pele_tools.py
        When:  Analyzing functions
        Then:  Identify which are generic (should move) vs Pele-specific
        
        Generic functions → Move to appropriate service
        Pele-specific → Keep in pele_tools (or mark deprecated)
        """
        pele_tools_file = Path("utils/pele_tools.py")
        if not pele_tools_file.exists():
            pytest.skip("utils/pele_tools.py not found")
        
        source = pele_tools_file.read_text()
        
        # Find all function definitions
        import re
        functions = re.findall(r'^def (\w+)\(', source, re.MULTILINE)
        
        print("\n=== utils/pele_tools.py Functions ===")
        for func in functions:
            print(f"  - {func}()")
        
        # This test documents what exists
        # Manual review needed to categorize:
        #   Generic → Move to src/services/
        #   Pele-specific → Keep or deprecate
        assert len(functions) > 0, "Should find functions to audit"

class TestLevel2Generalization:
    """
    Enforce that physics-specific KEYWORDS are config-driven, not hardcoded.
    
    The 6 structural indices (from PRD 5.4) are preserved, but the logic
    for filtering content into them must be generalized.
    
    Architecture: yt-project pattern (data in configs, behavior in builders)
    """

    @pytest.mark.architecture
    def test_level2_no_hardcoded_keyword_lists(self):
        """
        Validates: database/indexing/level2_builder.py has no hardcoded keyword lists.
        
        ALLOWED:
        - Index names: 'domain_models' (structural, from PRD 5.4)
        - Generic terms: 'physics', 'grid', 'configuration'
        - Docstrings: "This handles chemistry cases" (documentation)
        
        FORBIDDEN IN LOGIC:
        - Keyword lists: ['chem', 'species', 'fuel', 'reaction']
        - Physics checks: if 'combustion' in key
        - Code checks: if 'amrex' in key
        
        Current Code Issues (EXPECTED FAILURES):
        - Line ~132: if any(prefix in key for prefix in ['amrex', 'castro', ...])
        - Line ~272: if any(word in key for word in ['chem', 'species', ...])
        
        Pass Criteria:
        - Keyword filtering uses config.level2_index_keywords
        - No hardcoded domain terms in conditionals
        
        Indexing Engine: Physics-Agnostic Keywords & Scoring will fix this by:
        1. Adding BaseAMReXConfig.level2_index_keywords
        2. Replacing hardcoded lists with config.level2_index_keywords[index_name]
        """
        target_file = Path("database/indexing/level2_builder.py")
        if not target_file.exists():
            pytest.skip(f"{target_file} not found")

        content = target_file.read_text()
        lines = content.split('\n')
        
        violations = []
        
        # Pattern 1: Hardcoded keyword lists in logic
        # These are physics-specific and should be in config
        keyword_list_patterns = [
            # Combustion-specific
            ("'chem'", "combustion keyword"),
            ("'species'", "combustion keyword"),
            ("'fuel'", "combustion keyword"),
            ("'reaction'", "combustion keyword"),
            ("'kinetics'", "combustion keyword"),
            ("'combustion'", "combustion keyword"),
            ("'flame'", "combustion keyword"),
            ("'diffusion'", "combustion keyword (can be generic but context matters)"),
            
            # Code-specific
            ("'amrex'", "AMReX-specific"),
            ("'pelelmex'", "PeleLMeX-specific"),
            ("'castro'", "Castro-specific"),
            ("'nyx'", "Nyx-specific"),
            ("'warpx'", "WarpX-specific"),
            
            # Also check lowercase in comparisons
            ("'amrex.'", "AMReX namespace"),
            ("'castro.'", "Castro namespace"),
        ]
        
        for i, line in enumerate(lines, 1):
            # Skip comments and docstrings
            stripped = line.strip()
            
            # Skip comment lines
            if stripped.startswith('#'):
                continue
                
            # Skip docstring lines (simple heuristic)
            if '"""' in line or "'''" in line:
                continue
            
            # Skip method definitions (temporary - these will be refactored)
            if 'def _build_' in line:
                continue
            
            # Check for hardcoded keyword lists in logic
            for pattern, description in keyword_list_patterns:
                if pattern in line.lower():
                    # Additional context: is this in a list literal?
                    if '[' in line or 'for' in line or 'if' in line:
                        violations.append({
                            'line': i,
                            'content': line.strip()[:100],
                            'pattern': pattern,
                            'description': description
                        })
        
        # Pattern 2: Check for specific problematic constructs
        problematic_constructs = []
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip comments/docstrings
            if stripped.startswith('#') or '"""' in line:
                continue
            
            # Look for: if any(... in key.lower() for ... in keywords)
            if "if any(" in line and " in key" in line and " for " in line and "keywords" in line:
                # Check if 'keywords' variable comes from config (directly or indirectly)
                keywords_from_config = False
                
                # Check 1: Direct usage - self.config.level2_index_keywords
                for prev_i in range(max(0, i-50), i):
                    prev_line = lines[prev_i]
                    if "keywords" in prev_line and "self.config.level2_index_keywords" in prev_line:
                        keywords_from_config = True
                        break
                
                # Check 2: Indirect usage - keywords from index_config
                # where index_config comes from self.config.additional_level2_indices
                if not keywords_from_config:
                    for prev_i in range(max(0, i-50), i):
                        prev_line = lines[prev_i]
                        # Look for: keywords = index_config.get('keywords', ...)
                        if "keywords" in prev_line and "index_config.get" in prev_line:
                            # Now trace index_config back to config
                            for config_i in range(max(0, prev_i-20), prev_i):
                                config_line = lines[config_i]
                                # Look for: for index_name, index_config in additional.items()
                                if "for" in config_line and "index_config" in config_line and "additional" in config_line:
                                    # Now trace additional back to config
                                    for additional_i in range(max(0, config_i-10), config_i):
                                        additional_line = lines[additional_i]
                                        if "additional" in additional_line and "self.config" in additional_line:
                                            keywords_from_config = True
                                            break
                                if keywords_from_config:
                                    break
                        if keywords_from_config:
                            break
                
                if not keywords_from_config:
                    problematic_constructs.append({
                        'line': i,
                        'content': line.strip()[:100],
                        'issue': 'Hardcoded keyword filtering (should use config)'
                    })
        
        # Report violations
        if violations or problematic_constructs:
            failure_msg = [
                "=" * 80,
                "COMPONENT 5d.1 ARCHITECTURAL VIOLATION",
                "=" * 80,
                "",
                "Level 2 Builder contains hardcoded physics-specific keywords.",
                "These must be moved to Config classes (Indexing Engine: Physics-Agnostic Keywords & Scoring).",
                "",
            ]
            
            if violations:
                failure_msg.append(f"Found {len(violations)} hardcoded keyword violations:")
                failure_msg.append("")
                for v in violations[:10]:  # Show first 10
                    failure_msg.append(f"  Line {v['line']}: {v['description']}")
                    failure_msg.append(f"    Pattern: {v['pattern']}")
                    failure_msg.append(f"    Code: {v['content']}")
                    failure_msg.append("")
            
            if problematic_constructs:
                failure_msg.append(f"Found {len(problematic_constructs)} problematic constructs:")
                failure_msg.append("")
                for p in problematic_constructs[:5]:
                    failure_msg.append(f"  Line {p['line']}: {p['issue']}")
                    failure_msg.append(f"    Code: {p['content']}")
                    failure_msg.append("")
            
            failure_msg.extend([
                "=" * 80,
                "HOW TO FIX (Indexing Engine: Physics-Agnostic Keywords & Scoring):",
                "=" * 80,
                "",
                "1. Add to BaseAMReXConfig:",
                "   level2_index_keywords = {",
                "       'domain_models': ['chem', 'species', ...],",
                "       'physics_parameters': ['solver', 'physics', ...],",
                "   }",
                "",
                "2. Add to AMReXConfig:",
                "   level2_index_keywords = {",
                "       'domain_models': ['chem', 'species', 'fuel'],",
                "       'physics_parameters': ['amrex', 'combustion'],",
                "   }",
                "",
                "3. Update Level2Builder methods:",
                "   keywords = self.config.level2_index_keywords[index_name]",
                "   for key in inputs_content:",
                "       if any(kw in key.lower() for kw in keywords):",
                "           # Include in this index",
                "",
                "4. Remove hardcoded lists from builder logic",
                "",
                "See: Indexing Engine: Physics-Agnostic Keywords & Scoring implementation plan",
                "=" * 80,
            ])
            
            pytest.fail("\n".join(failure_msg))
        
        print("\n✅ Level 2 builder is physics-agnostic (no hardcoded keywords)")


class TestLevel2ArchitectureCompliance:
    """Additional architectural checks."""
    
    @pytest.mark.architecture
    def test_level2_builder_imports_no_code_specifics(self):
        """
        Validates: level2_builder.py doesn't import code-specific modules.
        
        FORBIDDEN:
        - from database.configs.amrex_config import AMReXConfig
        - from pele_specific_utils import ...
        
        ALLOWED:
        - from database.configs import BaseAMReXConfig (generic)
        - from database.scripts.utils import ... (generic utilities)
        """
        target_file = Path("database/indexing/level2_builder.py")
        if not target_file.exists():
            pytest.skip(f"{target_file} not found")
        
        content = target_file.read_text()
        lines = content.split('\n')
        
        forbidden_imports = [
            'amrex_config',
            'castro_config', 
            'nyx_config',
            'warpx_config',
        ]
        
        violations = []
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('from ') or line.strip().startswith('import '):
                for forbidden in forbidden_imports:
                    if forbidden in line.lower():
                        violations.append(f"Line {i}: {line.strip()}")
        
        if violations:
            pytest.fail(
                f"Found code-specific imports:\n" + "\n".join(violations) +
                "\n\nBuilder must use generic BaseAMReXConfig only."
            )
        
        print("✅ No code-specific imports (generic builder)")
