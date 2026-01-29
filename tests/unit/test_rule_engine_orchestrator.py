"""
Input Writer: Rule Engine Orchestrator: Rule Engine Orchestrator Tests

Tests the orchestration of validation rules.
Bridges Input Writer: Rule Factory (rules) with runtime validation.

TDD: Tests written FIRST to define expected behavior.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pydantic import BaseModel, Field


# Fixtures

@pytest.fixture
def mock_config_model():
    """Simple Pydantic model for testing."""
    from pydantic import ConfigDict
    
    class TestConfig(BaseModel):
        model_config = ConfigDict(populate_by_name=True)
        
        amr_n_cell: list[int] = Field(alias="amr.n_cell")
        pelec_cfl: float = Field(alias="amr.cfl")
    
    return TestConfig(amr_n_cell=[64, 64, 64], pelec_cfl=0.9)


@pytest.fixture
def mock_solver_config():
    """Mock solver config with validation_rules."""
    config = Mock()
    config.validation_rules = ["GridConsistency", "BuildFlagDependency"]
    return config


# Tests

class TestRuleEngineValidate:
    """Test validate() method - runs rules and aggregates violations."""
    
    def test_validate_runs_all_solver_rules(self, mock_config_model, mock_solver_config):
        """
        Given: Solver config with multiple rules
        When:  RuleEngine.validate() called
        Then:  Should create and execute each rule
        
        Validates: Rule orchestration
        """
        from src.services.rule_engine import RuleEngine
        from src.services.rules import RuleViolation
        
        with patch('src.services.rule_engine.RuleFactory') as mock_factory:
            # Setup mocks for each rule
            mock_rule_a = Mock()
            mock_rule_a.check.return_value = []
            
            mock_rule_b = Mock()
            mock_rule_b.check.return_value = []
            
            mock_factory.create.side_effect = [mock_rule_a, mock_rule_b]
            
            # Act
            violations = RuleEngine.validate(
                mock_config_model,
                mock_solver_config,
                build_config={}
            )
            
            # Assert - both rules created
            assert mock_factory.create.call_count == 2
            mock_factory.create.assert_any_call("GridConsistency")
            mock_factory.create.assert_any_call("BuildFlagDependency")
            
            # Assert - both rules executed
            mock_rule_a.check.assert_called_once()
            mock_rule_b.check.assert_called_once()
    
    def test_validate_aggregates_violations(self, mock_config_model, mock_solver_config):
        """
        Given: Rules returning multiple violations
        When:  RuleEngine.validate() called
        Then:  Should aggregate all violations
        
        Validates: Violation aggregation
        """
        from src.services.rule_engine import RuleEngine
        from src.services.rules import RuleViolation
        
        with patch('src.services.rule_engine.RuleFactory') as mock_factory:
            # Rule A finds 1 violation
            mock_rule_a = Mock()
            violation_a = RuleViolation(
                rule_name="GridConsistency",
                severity="error",
                message="Issue A"
            )
            mock_rule_a.check.return_value = [violation_a]
            
            # Rule B finds 2 violations
            mock_rule_b = Mock()
            violation_b1 = RuleViolation(
                rule_name="BuildFlagDependency",
                severity="error",
                message="Issue B1"
            )
            violation_b2 = RuleViolation(
                rule_name="BuildFlagDependency",
                severity="warning",
                message="Issue B2"
            )
            mock_rule_b.check.return_value = [violation_b1, violation_b2]
            
            mock_factory.create.side_effect = [mock_rule_a, mock_rule_b]
            
            # Act
            violations = RuleEngine.validate(
                mock_config_model,
                mock_solver_config,
                build_config={}
            )
            
            # Assert - aggregated 3 violations
            assert len(violations) == 3
            assert violation_a in violations
            assert violation_b1 in violations
            assert violation_b2 in violations
    
    def test_validate_skips_unknown_rules(self, mock_config_model):
        """
        Given: Solver config with unknown rule name
        When:  RuleEngine.validate() called
        Then:  Should log warning and continue
        
        Validates: Robustness against config typos
        """
        from src.services.rule_engine import RuleEngine
        
        # Config with typo in rule name
        bad_config = Mock()
        bad_config.validation_rules = ["NonExistentRule"]
        
        with patch('src.services.rule_engine.RuleFactory') as mock_factory, \
             patch('src.services.rule_engine.logger') as mock_logger:
            
            # RuleFactory raises KeyError for unknown rule
            mock_factory.create.side_effect = KeyError("Unknown rule")
            
            # Act - should not crash
            violations = RuleEngine.validate(
                mock_config_model,
                bad_config,
                build_config={}
            )
            
            # Assert - returned empty (no crash)
            assert violations == []
            
            # Assert - logged warning
            mock_logger.warning.assert_called_once()
            assert "unknown" in mock_logger.warning.call_args[0][0].lower()
    
    def test_validate_passes_correct_context(self, mock_config_model, mock_solver_config):
        """
        Given: Config model with schema
        When:  Rule.check() called
        Then:  Should receive config, schema, and build_config
        
        Validates: Source truth context (Amendment D)
        """
        from src.services.rule_engine import RuleEngine
        
        build_config = {"USE_EB": "TRUE", "DIM": "3"}
        
        with patch('src.services.rule_engine.RuleFactory') as mock_factory:
            mock_rule = Mock()
            mock_rule.check.return_value = []
            mock_factory.create.return_value = mock_rule
            
            # Act
            RuleEngine.validate(
                mock_config_model,
                mock_solver_config,
                build_config=build_config
            )
            
            # Assert - check() received correct context
            call_args = mock_rule.check.call_args[0]
            assert call_args[0] == mock_config_model  # config
            assert isinstance(call_args[1], dict)  # schema
            assert call_args[2] == build_config  # build_config
    
    def test_validate_handles_missing_validation_rules(self, mock_config_model):
        """
        Given: Solver config without validation_rules attribute
        When:  RuleEngine.validate() called
        Then:  Should treat as empty list (no crash)
        
        Validates: Safe default behavior
        """
        from src.services.rule_engine import RuleEngine
        
        # Config without validation_rules
        incomplete_config = Mock(spec=[])  # No attributes
        
        # Act - should not crash
        violations = RuleEngine.validate(
            mock_config_model,
            incomplete_config,
            build_config={}
        )
        
        # Assert - empty list
        assert violations == []


class TestRuleEngineEnforce:
    """Test enforce() method - validate and auto-correct."""
    
    def test_enforce_auto_corrects_fixable(self, mock_config_model):
        """
        Given: Rule violation with auto_correctable=True
        When:  RuleEngine.enforce() called
        Then:  Should call auto_correct() and modify model
        
        Validates: Contextual Generation (Amendment C)
        """
        from src.services.rule_engine import RuleEngine
        from src.services.rules import RuleViolation
        
        solver_config = Mock()
        solver_config.validation_rules = ["GridConsistency"]
        
        with patch('src.services.rule_engine.RuleFactory') as mock_factory:
            mock_rule = Mock()
            
            # Rule finds auto-correctable violation
            violation = RuleViolation(
                rule_name="GridConsistency",
                severity="error",
                message="blocking_factor issue",
                auto_correctable=True
            )
            mock_rule.check.return_value = [violation]
            
            # Auto-correct modifies model
            corrected_model = mock_config_model
            corrected_model.amr_n_cell = [128, 128, 128]  # Simulated fix
            mock_rule.auto_correct.return_value = corrected_model
            
            mock_factory.create.return_value = mock_rule
            
            # Act
            result = RuleEngine.enforce(
                mock_config_model,
                solver_config,
                build_config={}
            )
            
            # Assert - auto_correct was called
            mock_rule.auto_correct.assert_called_once()
            
            # Assert - returned corrected model
            assert result.amr_n_cell == [128, 128, 128]
    
    def test_enforce_preserves_unfixable(self, mock_config_model):
        """
        Given: Rule violation with auto_correctable=False
        When:  RuleEngine.enforce() called
        Then:  Should NOT call auto_correct()
        
        Validates: Only fix what's safe to fix
        """
        from src.services.rule_engine import RuleEngine
        from src.services.rules import RuleViolation
        
        solver_config = Mock()
        solver_config.validation_rules = ["BuildFlagDependency"]
        
        with patch('src.services.rule_engine.RuleFactory') as mock_factory:
            mock_rule = Mock()
            
            # Rule finds unfixable violation
            violation = RuleViolation(
                rule_name="BuildFlagDependency",
                severity="error",
                message="Missing USE_EB",
                auto_correctable=False  # Cannot auto-fix
            )
            mock_rule.check.return_value = [violation]
            
            mock_factory.create.return_value = mock_rule
            
            # Act
            result = RuleEngine.enforce(
                mock_config_model,
                solver_config,
                build_config={}
            )
            
            # Assert - auto_correct NOT called
            mock_rule.auto_correct.assert_not_called()
            
            # Assert - model unchanged
            assert result == mock_config_model


# Input Writer: Rule Engine Orchestrator marker
pytestmark = pytest.mark.input_writer_rule_engine_orchestrator
