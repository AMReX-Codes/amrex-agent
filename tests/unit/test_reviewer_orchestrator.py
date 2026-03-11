"""
Reviewer Service: Reviewer Orchestrator: Reviewer Orchestrator Tests

TDD Approach: RED → GREEN → Refactor
This file contains tests that SHOULD FAIL initially.
"""
import importlib
import pytest
from unittest.mock import Mock, patch
from src.services.reviewer import ReviewerOrchestrator
from src.services.rules.base import RuleViolation

reviewer_node_module = importlib.import_module("src.nodes.reviewer_node")


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


class TestReviewerNodeFinalTaxonomy:

    def test_terminal_taxonomy_after_review_max_retries(self, monkeypatch, mock_config):
        """
        GIVEN: Reviewer violations and retry_count already at max_retries
        WHEN: reviewer_node() completes validation
        THEN: terminal response includes standardized final taxonomy/category
        """
        mock_config.preconfirm_gate = False
        mock_config.preconfirm_gate_auto_approve = False
        mock_config.baseline_switch_after_retries = 3
        mock_config.retry_guidance_use_llm = False

        class FakeOrchestrator:
            def __init__(self, _config):
                pass

            def validate_plan(self, _plan):
                violation = RuleViolation("SchemaExistence", "error", "Parameter 'x.bad' not found.")
                return type(
                    "ValidationResult",
                    (),
                    {
                        "mode": "retry",
                        "violations": [violation],
                        "summary": "invalid",
                        "available_schema_params": [],
                    },
                )

        monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)

        state = {
            "config": mock_config,
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "PeleC/Exec/RegTests/PMF",
                        "modifications": [("amr.n_cell", "64 64 64")],
                        "baseline": {"code_name": "PeleC", "local_path": "cases/PMF"},
                    },
                }
            ],
            "iteration": 2,
            "retry_count": 3,
            "max_retries": 3,
            "errors_active": [],
            "errors_found": [],
            "errors_fixed": [],
        }

        updates = reviewer_node_module.reviewer_node(state)
        taxonomy = updates["final_error_taxonomy"]

        assert updates["mode"] == "terminal"
        assert updates["reviewer_failure_category"] == "review_validation_max_retries"
        assert taxonomy["type"] == "retry_exhausted"
        assert taxonomy["category"] == "review_validation_max_retries"
        assert updates["workflow_history"][-1]["details"]["final_error_taxonomy"] == taxonomy

    def test_terminal_taxonomy_after_parameter_resolution_max_retries(self, mock_config):
        """
        GIVEN: Input writer requires parameter resolution and retries are exhausted
        WHEN: reviewer_node() runs
        THEN: terminal response includes standardized final taxonomy/category
        """
        mock_config.preconfirm_gate = False
        mock_config.preconfirm_gate_auto_approve = False

        state = {
            "config": mock_config,
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "PeleC/Exec/RegTests/PMF",
                        "modifications": [("amr.n_cell", "64 64 64")],
                        "baseline": {"code_name": "PeleC", "local_path": "cases/PMF"},
                    },
                },
                {
                    "node": "input_writer",
                    "details": {
                        "requires_parameter_resolution": True,
                        "unresolved_parameters": [("pelec.bad_param", "1")],
                        "resolution_guidance": "Remap to a schema key.",
                        "available_schema_params": ["pelec.cfl"],
                        "suggested_params": {"pelec.bad_param": "pelec.cfl"},
                    },
                },
            ],
            "iteration": 3,
            "retry_count": 3,
            "max_retries": 3,
        }

        updates = reviewer_node_module.reviewer_node(state)
        taxonomy = updates["final_error_taxonomy"]

        assert updates["mode"] == "terminal"
        assert updates["reviewer_failure_category"] == "parameter_resolution_max_retries"
        assert taxonomy["type"] == "retry_exhausted"
        assert taxonomy["category"] == "parameter_resolution_max_retries"
        assert updates["workflow_history"][-1]["details"]["final_error_taxonomy"] == taxonomy
