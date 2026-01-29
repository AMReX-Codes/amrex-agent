"""
Reviewer Service Integration Tests (Q9 Priority Tests)

Tests #1, #2, #6 from extensibility specification.
"""
import pytest
from database.configs.pelec_config import PeleCConfig
from database.configs.pelelmex_config import PeleLMeXConfig


class TestSolverExtensibility:
    """Q9 Priority: Tests for solver-specific validation."""
    
    def test_pelec_config_explicit_rules(self):
        """
        TEST #1 (Q9 BLOCKING)
        
        GIVEN: PeleCConfig
        WHEN: Check validation_rules attribute
        THEN: Contains CFLStabilityRule (explicit solver)
        """
        assert hasattr(PeleCConfig, 'validation_rules')
        assert 'CFLStabilityRule' in PeleCConfig.validation_rules, \
            "PeleC (explicit) must enforce CFL stability"
    
    def test_pelelmex_excludes_cfl(self):
        """
        TEST #2 (Q9 BLOCKING)
        
        GIVEN: PeleLMeXConfig  
        WHEN: Check validation_rules attribute
        THEN: Does NOT contain CFLStabilityRule (implicit solver)
        """
        assert hasattr(PeleLMeXConfig, 'validation_rules')
        assert 'CFLStabilityRule' not in PeleLMeXConfig.validation_rules, \
            "PeleLMeX (implicit) should not enforce CFL limits"
    
    def test_base_config_has_universal_rules(self):
        """
        GIVEN: BaseAMReXConfig
        WHEN: Check validation_rules
        THEN: Contains universal rules (SchemaExistence, etc.)
        """
        from database.configs.base_amrex_config import BaseAMReXConfig
        
        assert hasattr(BaseAMReXConfig, 'validation_rules')
        assert 'SchemaExistence' in BaseAMReXConfig.validation_rules
        assert 'BuildFlagDependency' in BaseAMReXConfig.validation_rules

    def test_rule_registry_filters(self):
        """
        TEST #6 (Q9 BLOCKING)
        
        GIVEN: Plan targeting specific solver
        WHEN: PhysicsValidator runs
        THEN: Only rules in solver's validation_rules are executed
        
        This ensures RuleEngine respects config policy (Q4).
        """
        from src.services.validators.physics_validator import PhysicsValidator
        from src.config import AMReXAgentConfig
        
        config = AMReXAgentConfig()
        validator = PhysicsValidator(config)
        
        # Plan targeting PeleLMeX - Use FLATTENED structure to match schema
        plan = {
            'selected_solver': 'PeleLMeX',
            'baseline': {
                'pelelmex.cfl': 1.5  # Flattened to match schema
            },
            'modifications': [],
            'schema': {
                'pelelmex.cfl': {
                    'type': 'Real',
                    'default': 0.7
                }
            },
            'build_config': {'DIM': '3'}
        }
        
        violations = validator.validate(plan)
        
        # Filter ONLY for CFLStabilityRule violations
        cfl_stability_violations = [
            v for v in violations 
            if v.rule_name == 'CFLStabilityRule'
        ]
        
        # PeleLMeX should NOT trigger CFLStabilityRule
        assert len(cfl_stability_violations) == 0, \
            f"PeleLMeX should not run CFLStabilityRule, but got: {cfl_stability_violations}"
    
    def test_pelec_does_check_cfl(self):
        """
        Counterpart to test_rule_registry_filters.
        
        GIVEN: Plan targeting PeleC with high CFL
        WHEN: PhysicsValidator runs
        THEN: CFLStabilityRule DOES fire (it's in PeleCConfig.validation_rules)
        """
        from src.services.validators.physics_validator import PhysicsValidator
        from src.config import AMReXAgentConfig
        
        config = AMReXAgentConfig()
        validator = PhysicsValidator(config)
        
        # Plan targeting PeleC - Use FLATTENED structure
        plan = {
            'selected_solver': 'PeleC',
            'baseline': {
                'pelec.cfl': 1.5  # Flattened key - unstable for explicit solver!
            },
            'modifications': [],
            'schema': {
                'pelec.cfl': {
                    'type': 'Real',
                    'default': 0.5
                }
            },
            'build_config': {'DIM': '3'}
        }
        
        violations = validator.validate(plan)
        
        # Debug output
        print(f"\nAll violations for PeleC:")
        for v in violations:
            print(f"  {v.rule_name}: {v.message}")
        
        # Filter by rule name
        cfl_stability_violations = [
            v for v in violations 
            if v.rule_name == 'CFLStabilityRule'
        ]
        
        # PeleC SHOULD trigger CFLStabilityRule
        assert len(cfl_stability_violations) > 0, \
            f"PeleC should run CFLStabilityRule, but got violations: {[v.rule_name for v in violations]}"
        
        # Check severity
        assert cfl_stability_violations[0].severity in ['error', 'critical'], \
            f"CFL violation should be error/critical, got: {cfl_stability_violations[0].severity}"
