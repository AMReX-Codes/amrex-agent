"""
Reviewer Service: Reviewer Orchestrator: Reviewer Orchestrator Tests

TDD Approach: RED → GREEN → Refactor
This file contains tests that SHOULD FAIL initially.
"""
import pytest
from unittest.mock import Mock, patch
from src.services.reviewer import ReviewerOrchestrator
from src.services.rules.base import RuleViolation


class TestReviewerOrchestrator:

    def test_orchestrator_initialization(self, mock_config):
        """
        GIVEN: A valid config object
        WHEN: ReviewerOrchestrator is instantiated
        THEN: All 4 sub-validators are initialized with that config
        """
        with patch("src.services.reviewer.SchemaSyntaxValidator") as MockSchema, \
             patch("src.services.reviewer.BuildDependencyValidator") as MockBuild, \
             patch("src.services.reviewer.PhysicsValidator") as MockPhysics, \
             patch("src.services.reviewer.ResourceValidator") as MockResource:

            orchestrator = ReviewerOrchestrator(mock_config)

            # Verify all were called with config
            MockSchema.assert_called_once_with(mock_config)
            MockBuild.assert_called_once_with(mock_config)
            MockPhysics.assert_called_once_with(mock_config)
            MockResource.assert_called_once_with(mock_config)
            
            # Verify internal list is populated
            assert len(orchestrator.validators) == 4

    def test_validate_all_pass(self, mock_config, sample_plan):
        """
        GIVEN: Plan dict, mocked validators return empty lists (no violations)
        WHEN: validate_plan() is called
        THEN: Returns ValidationResult with mode='proceed'
        """
        with patch("src.services.reviewer.SchemaSyntaxValidator") as MockSchema, \
             patch("src.services.reviewer.BuildDependencyValidator") as MockBuild, \
             patch("src.services.reviewer.PhysicsValidator") as MockPhysics, \
             patch("src.services.reviewer.ResourceValidator") as MockResource:
            
            # Setup mocks to return empty lists
            MockSchema.return_value.validate.return_value = []
            MockBuild.return_value.validate.return_value = []
            MockPhysics.return_value.validate.return_value = []
            MockResource.return_value.validate.return_value = []

            orchestrator = ReviewerOrchestrator(mock_config)
            result = orchestrator.validate_plan(sample_plan)

            assert result.mode == "proceed"
            assert len(result.violations) == 0
            assert "pass" in result.summary.lower()

    def test_aggregate_multiple_errors(self, mock_config, sample_plan):
        """
        GIVEN: Validator A returns 1 error, Validator B returns 1 error
        WHEN: validate_plan() is called
        THEN: Result contains both violations, mode='retry'
        """
        v1 = RuleViolation("RuleA", "error", "MsgA")
        v2 = RuleViolation("RuleB", "error", "MsgB")

        with patch("src.services.reviewer.SchemaSyntaxValidator") as MockSchema, \
             patch("src.services.reviewer.BuildDependencyValidator") as MockBuild, \
             patch("src.services.reviewer.PhysicsValidator") as MockPhysics, \
             patch("src.services.reviewer.ResourceValidator") as MockResource:

            # Schema validator returns v1, Physics returns v2
            MockSchema.return_value.validate.return_value = [v1]
            MockBuild.return_value.validate.return_value = []
            MockPhysics.return_value.validate.return_value = [v2]
            MockResource.return_value.validate.return_value = []

            orchestrator = ReviewerOrchestrator(mock_config)
            result = orchestrator.validate_plan(sample_plan)

            assert result.mode == "retry"
            assert len(result.violations) == 2
            assert v1 in result.violations
            assert v2 in result.violations

    def test_fail_on_critical_error(self, mock_config, sample_plan):
        """
        GIVEN: First validator returns a 'critical' violation
        WHEN: validate_plan() is called
        THEN: mode='fail', subsequent validators are NOT called (short-circuit)
        """
        critical_v = RuleViolation("FatalRule", "critical", "Missing executable")

        with patch("src.services.reviewer.SchemaSyntaxValidator") as MockSchema, \
             patch("src.services.reviewer.BuildDependencyValidator") as MockBuild:
            
            # First validator fails critically
            MockSchema.return_value.validate.return_value = [critical_v]
            
            orchestrator = ReviewerOrchestrator(mock_config)
            # Ensure we only have these 2 for this test to simplify mocking
            orchestrator.validators = [MockSchema.return_value, MockBuild.return_value]
            
            result = orchestrator.validate_plan(sample_plan)

            assert result.mode == "fail"
            assert critical_v in result.violations
            
            # VERIFY SHORT CIRCUIT: Second validator should NOT be called
            MockBuild.return_value.validate.assert_not_called()

    def test_max_retries_termination(self, mock_config, sample_plan, sample_violation):
        """
        GIVEN: Violations exist, retry_count equals max_iterations
        WHEN: validate_plan() is called
        THEN: mode='fail' (stop loop)
        """
        with patch("src.services.reviewer.SchemaSyntaxValidator") as MockSchema:
            MockSchema.return_value.validate.return_value = [sample_violation]
            
            orchestrator = ReviewerOrchestrator(mock_config)
            # Only use one validator
            orchestrator.validators = [MockSchema.return_value]

            # Pass retry_count = 3 (matches config.max_iterations)
            result = orchestrator.validate_plan(sample_plan, retry_count=3)

            assert result.mode == "fail"
            assert "Max retries" in result.summary

    def test_validator_crash_handled_gracefully(self, mock_config, sample_plan):
        """
        GIVEN: A sub-validator raises an unhandled exception
        WHEN: validate_plan() is called
        THEN: Caught by orchestrator, returns mode='fail', exception in summary
        """
        with patch("src.services.reviewer.SchemaSyntaxValidator") as MockSchema:
            # Simulate a bug in the validator
            MockSchema.return_value.validate.side_effect = ValueError("Unexpected crash")
            
            orchestrator = ReviewerOrchestrator(mock_config)
            orchestrator.validators = [MockSchema.return_value]

            result = orchestrator.validate_plan(sample_plan)

            assert result.mode == "fail"
            assert "Unexpected crash" in result.summary
