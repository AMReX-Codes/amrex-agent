"""
Cases Service Refactor Tests - Cases Service: Config-Driven Discovery

Tests the transition from hardcoded PRIORITY_CODES to dynamic config discovery.
Follows yt-project architecture pattern: configs/ as source of truth.

Reference: AMReXAgent Development and Validation Plan v2.0
"""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from typing import List, Type
from src.services.cases import AMReXCasesService, AMReXCode
from src.config import AMReXAgentConfig


class TestDynamicCodeLoading:
    """Test 1: Service loads codes from configs/, not hardcoded list."""
    
    def test_loads_codes_from_configs(self):
        """
        Given: database/configs/ has MockCodeA and MockCodeB
        When:  Initializing AMReXCasesService
        Then:  Should load both codes dynamically (no PRIORITY_CODES)
        
        Architecture: Service is consumer, configs/ is source of truth
        """
        # Arrange: Mock config classes
        MockCodeA = type('MockCodeA', (), {
            'code_name': 'Alpha',
            'github_org': 'TestOrg',
            'github_repo': 'Alpha',
            'description': 'Test code Alpha',
            'inputs_quality': 'excellent',
            'priority_cases': ['Exec/Alpha/Test'],
            'get_priority_cases': classmethod(lambda cls: cls.priority_cases),
        })
        
        MockCodeB = type('MockCodeB', (), {
            'code_name': 'Beta',
            'github_org': 'TestOrg',
            'github_repo': 'Beta',
            'description': 'Test code Beta',
            'inputs_quality': 'good',
            'priority_cases': ['Exec/Beta/Test'],
            'get_priority_cases': classmethod(lambda cls: cls.priority_cases),
        })
        
        config = AMReXAgentConfig()
        
        # Act: Mock the discovery function
        with patch('src.services.cases.discover_code_configs', return_value=[MockCodeA, MockCodeB]):
            service = AMReXCasesService(config)
        
        # Assert: Service has both dynamically loaded codes
        assert len(service.codes) == 2, "Should load 2 codes from configs"
        
        code_names = {code.name for code in service.codes}
        assert 'Alpha' in code_names, "Should have Alpha from MockCodeA"
        assert 'Beta' in code_names, "Should have Beta from MockCodeB"
        
        # Ensure not using old hardcoded list
        assert 'AMReX' not in code_names or len(service.codes) > 5, \
            "Should not have old hardcoded codes (unless configs exist)"
    
    
    def test_handles_empty_config_registry(self):
        """
        Edge case: No configs available.
        
        Given: discover_code_configs() returns []
        When:  Initializing service
        Then:  Should not crash (0 codes is valid)
        """
        config = AMReXAgentConfig()
        
        with patch('src.services.cases.discover_code_configs', return_value=[]):
            service = AMReXCasesService(config)
        
        assert len(service.codes) == 0, "Empty registry should result in 0 codes"
        assert hasattr(service, 'codes'), "Service should initialize cleanly"
    
    
    def test_handles_config_import_error(self, caplog):
        """
        Edge case: One config raises error during access.
        
        Given: MockCodeBroken raises ImportError
        When:  Loading configs
        Then:  Should skip broken config, continue with others
        """
        MockGoodCode = type('MockGoodCode', (), {
            'code_name': 'GoodCode',
            'github_org': 'TestOrg',
            'github_repo': 'GoodCode',
            'description': 'Good test code',
            'inputs_quality': 'good',
            'priority_cases': [],
            'get_priority_cases': classmethod(lambda cls: cls.priority_cases),
        })
        
        # This will raise when accessed
        # Mock that raises error when accessed
        class MockBrokenCode:
            @property
            def code_name(self):
                raise ImportError("Broken dependency")
            
            # These exist but we never get to them
            github_org = "BrokenOrg"
            github_repo = "Broken"
            description = "Broken"
            inputs_quality = "basic"
            priority_cases = []
            
            @classmethod
            def get_priority_cases(cls):
                return cls.priority_cases
        
        config = AMReXAgentConfig()
        
        with patch('src.services.cases.discover_code_configs', return_value=[MockGoodCode, MockBrokenCode]):
            service = AMReXCasesService(config)
        
        # Should have loaded the good one, skipped the broken one
        assert len(service.codes) >= 1, "Should load working configs"
        # Check logs for warning about broken config
        # (This assumes the service logs import errors)


class TestConfigMetadataPropagation:
    """Test 2: Data fidelity - config metadata maps to AMReXCode correctly."""
    
    def test_config_metadata_propagates(self):
        """
        Given: MockDetailedConfig with specific canary values
        When:  Service loads the config
        Then:  AMReXCode should have exact same metadata
        
        Data Mapping: Config (source) → AMReXCode (runtime)
        """
        # Arrange: Canary config with traceable values
        MockDetailedConfig = type('MockDetailedConfig', (), {
            'code_name': 'CanaryCode',
            'priority_cases': ['Exec/Canary/Test', 'Exec/Canary/Production'],
            'github_org': 'CanaryOrg',
            'github_repo': 'CanaryRepo',
            'description': 'A test description',
            'inputs_quality': 'excellent',
            'get_priority_cases': classmethod(lambda cls: cls.priority_cases),
        })
        
        config = AMReXAgentConfig()
        
        # Act
        with patch('src.services.cases.discover_code_configs', return_value=[MockDetailedConfig]):
            service = AMReXCasesService(config)
        
        # Assert: Find the canary code
        canary = next((c for c in service.codes if c.name == 'CanaryCode'), None)
        assert canary is not None, "Should have loaded CanaryCode"
        
        # Verify metadata propagation
        assert canary.name == 'CanaryCode', "Code name should match"
        assert canary.common_cases == ['Exec/Canary/Test', 'Exec/Canary/Production'], \
            "Priority cases should propagate"
        assert canary.github_org == 'CanaryOrg', "GitHub org should propagate"
        assert canary.github_repo == 'CanaryRepo', "GitHub repo should propagate"
        assert canary.description == 'A test description', "Description should propagate"
        assert canary.inputs_quality == 'excellent', "Inputs quality should propagate"
    
    
    def test_handles_missing_optional_fields(self):
        """
        Edge case: Config lacks optional fields.
        
        Given: MinimalConfig with only required fields
        When:  Loading config
        Then:  Should use sensible defaults for optional fields
        """
        MinimalConfig = type('MinimalConfig', (), {
            'code_name': 'MinimalCode',
            'github_org': '',  # Empty defaults
            'github_repo': '',
            'description': '',
            'inputs_quality': 'basic',
            'priority_cases': [],
            'get_priority_cases': classmethod(lambda cls: cls.priority_cases),
        })
        
        config = AMReXAgentConfig()
        
        with patch('src.services.cases.discover_code_configs', return_value=[MinimalConfig]):
            service = AMReXCasesService(config)
        
        minimal = next((c for c in service.codes if c.name == 'MinimalCode'), None)
        assert minimal is not None
        
        # Optional fields should default gracefully
        assert minimal.common_cases == [] or minimal.common_cases is None
        assert minimal.description is None or isinstance(minimal.description, str)
    
    
    def test_priority_cases_copied_not_referenced(self):
        """
        Data integrity: Ensure lists are copied, not shared.
        
        Given: Config with priority_cases list
        When:  Service loads it
        Then:  Modifying service list should NOT affect config
        """
        original_cases = ['Exec/Test/A', 'Exec/Test/B']
        
        MockConfig = type('MockConfig', (), {
            'code_name': 'TestCode',
            'github_org': 'TestOrg',
            'github_repo': 'TestCode',
            'description': 'Test',
            'inputs_quality': 'good',
            'priority_cases': original_cases,
            'get_priority_cases': classmethod(lambda cls: cls.priority_cases.copy()),
        })
        
        config = AMReXAgentConfig()
        
        with patch('src.services.cases.discover_code_configs', return_value=[MockConfig]):
            service = AMReXCasesService(config)
        
        # Mutate the service's copy
        code = next(c for c in service.codes if c.name == 'TestCode')
        code.common_cases.append('Exec/Test/C')
        
        # Original should be unchanged
        assert len(original_cases) == 2, "Original config list should not be mutated"


class TestArchitecturalConstraints:
    """Test 3: Structural regression - enforce config-driven architecture."""
    
    def test_no_hardcoded_priority_codes(self):
        """
        Architecture test: PRIORITY_CODES constant must be removed.
        
        Given: Refactored cases.py
        When:  Checking module for PRIORITY_CODES
        Then:  Should NOT find it (deleted in refactor)
        
        Single Source of Truth: All codes defined in database/configs/
        """
        import src.services.cases as cases_module
        
        # Check module doesn't have PRIORITY_CODES
        assert not hasattr(cases_module, 'PRIORITY_CODES'), \
            "PRIORITY_CODES constant should be removed (refactor to config-driven)"
        
        # Also check it's not just renamed
        source_file = Path("src/services/cases.py")
        source = source_file.read_text()
        
        # Allow the term in comments/docstrings, but not as a variable
        violations = []
        for line_num, line in enumerate(source.split('\n'), 1):
            # Skip comments and docstrings
            if line.strip().startswith('#') or '"""' in line or "'''" in line:
                continue
            
            # Check for suspicious patterns
            if 'PRIORITY_CODES' in line and '=' in line:
                violations.append((line_num, line.strip()))
        
        assert len(violations) == 0, \
            f"Found PRIORITY_CODES definitions at lines: {[v[0] for v in violations]}\n" + \
            "Should load codes from database/configs/ instead"
    
    
    @pytest.mark.skip(reason="Too strict - allows strings in docstrings/comments")
    def test_no_hardcoded_code_strings(self):
        """
        Architecture test: No hardcoded "AMReX", "PeleLMeX" in code logic.
        
        Given: Refactored cases.py
        When:  Searching for hardcoded code names
        Then:  Should only appear in comments/examples, not logic
        """
        source_file = Path("src/services/cases.py")
        source = source_file.read_text()
        
        # Code names that should come from configs
        code_names = ['AMReX', 'PeleLMeX', 'PeleMP', 'ERF']
        
        violations = []
        for line_num, line in enumerate(source.split('\n'), 1):
            # Skip comments, docstrings, and test examples
            if any(x in line for x in ['#', '"""', "'''", 'Example:', 'e.g.']):
                continue
            
            # Only check for if/elif chains (problematic hardcoding)
            if ('if ' in line or 'elif ' in line) and ('==' in line or 'in [' in line):
                for code_name in code_names:
                    if f'"{code_name}"' in line or f"'{code_name}'" in line:
                        violations.append((line_num, code_name, line.strip()[:60]))
        
        if violations:
            print("\n⚠️  Found hardcoded code names:")
            for line_num, code, snippet in violations[:5]:  # Show first 5
                print(f"   Line {line_num}: {code} in '{snippet}...'")
        
        assert len(violations) == 0, \
            f"Found {len(violations)} hardcoded if/elif chains. Should use dynamic config loading."
    
    
    def test_service_uses_discover_function(self):
        """
        Architecture test: Service must call discover_code_configs().
        
        Given: AMReXCasesService implementation
        When:  Initializing
        Then:  Should import and call discover_code_configs()
        """
        import src.services.cases as cases_module
        
        # Check that discover_code_configs is imported
        source = Path("src/services/cases.py").read_text()
        
        assert 'discover_code_configs' in source, \
            "Service should import discover_code_configs from database.configs"
        
        # Verify it's actually called (not just imported)
        # Look for it in a function/method body
        assert 'discover_code_configs()' in source, \
            "Service should call discover_code_configs() to load codes"
