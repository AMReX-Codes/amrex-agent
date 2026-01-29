"""
Level 1 Integration: State Field Transitions

Tests specific GraphState field updates and data contracts:
- errors_active feedback to Architect
- errors_found/errors_fixed tracking (Phase 2)
- Iteration/retry counter logic
- State schema compliance

Mocked: LLM calls, ReviewerOrchestrator
Real: State field updates, feedback mechanism
"""
import pytest
from unittest.mock import Mock, patch
from src.nodes.architect_node import architect_node
from src.nodes.reviewer_node import reviewer_node


@pytest.mark.integration_l1
class TestStateTransitions:
    """Field-level state transition tests."""

    def test_errors_active_feedback_to_architect(self, ladder_state):
        """
        Test 3: Verify errors_active is passed to Architect as feedback

        Scenario:
        1. Reviewer rejected previous attempt
        2. State has errors_active = ["Error message"]
        3. Architect receives this as previous_feedback
        """
        # Setup state as if Reviewer just rejected
        state = ladder_state
        state["mode"] = "retry"
        state["errors_active"] = ["Missing parameter: amr.n_cell"]
        state["retry_count"] = 1
        state["iteration"] = 1
        state["selected_case"] = "PeleC/Exec/RegTests/PMF"

        # Spy on ArchitectService to verify it receives feedback
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/PMF",
                "modifications": [
                    {"section": "amr", "parameter": "n_cell", "value": "64 64 64"}
                ],
                "reasoning": "Added missing parameter"
            }

            # Execute Architect
            architect_node(state)

            # Verify create_plan_rag was called with feedback
            call_args = mock_arch_svc.create_plan_rag.call_args
            assert call_args is not None

            # Check previous_feedback argument
            feedback = call_args.kwargs.get("previous_feedback")
            assert feedback is not None
            assert "errors" in feedback
            assert "Missing parameter: amr.n_cell" in feedback["errors"]
            assert feedback["retry_count"] == 1
            assert feedback["rejected_baseline"] == "PeleC/Exec/RegTests/PMF"

    def test_error_progress_tracking(self, ladder_state):
        """
        Test 5: Verify errors_found/errors_fixed tracking (Phase 2)

        Scenario:
        1. First review finds 2 errors
        2. Second review finds 1 error (1 fixed)
        3. errors_fixed should contain the fixed error
        """
        state = ladder_state

        # === Attempt 1: Find initial errors ===
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/PMF",
                "modifications": [],
                "reasoning": "Initial plan"
            }
            state = {**state, **architect_node(state)}

        with patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:
            mock_rev = MockRev.return_value
            mock_rev.review_plan.return_value = {
                "approved": False,
                "errors": ["Error A", "Error B"],
                "warnings": []
            }
            mock_rev.suggest_fixes.return_value = {"modifications": []}

            state = reviewer_node(state)

        # Verify initial error tracking
        assert len(state["errors_active"]) == 2
        assert len(state["errors_found"]) == 2
        assert len(state["errors_fixed"]) == 0

        # === Attempt 2: Fix one error ===
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/PMF",
                "modifications": [{"fix": "for Error A"}],
                "reasoning": "Fixed Error A"
            }
            state = {**state, **architect_node(state)}

        with patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:
            mock_rev = MockRev.return_value
            mock_rev.review_plan.return_value = {
                "approved": False,
                "errors": ["Error B"],  # Error A fixed
                "warnings": []
            }
            mock_rev.suggest_fixes.return_value = {"modifications": []}

            state = reviewer_node(state)

        # Verify error progress
        assert len(state["errors_active"]) == 1
        assert "Error B" in state["errors_active"]
        assert "Error A" in state["errors_fixed"]
        assert len(state["errors_found"]) == 2  # Cumulative

    def test_iteration_counter_logic(self, ladder_state):
        """
        Test 6: Verify iteration and retry_count increment correctly

        Rules:
        - iteration always increments
        - retry_count only increments when mode == "retry"
        """
        state = ladder_state

        # Initial state
        assert state["iteration"] == 0
        assert state.get("retry_count", 0) == 0

        # === Attempt 1: mode = "initial" ===
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/Sedov",
                "modifications": [],
                "reasoning": "Test"
            }

            state = {**state, **architect_node(state)}

        # iteration increments, retry_count stays 0 (mode was "initial")
        assert state["iteration"] == 1
        assert state["retry_count"] == 0

        # Reviewer rejects
        state["mode"] = "retry"
        state["errors_active"] = ["Test error"]

        # === Attempt 2: mode = "retry" ===
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/Sedov",
                "modifications": [],
                "reasoning": "Retry"
            }

            state = {**state, **architect_node(state)}

        # Both increment (mode was "retry")
        assert state["iteration"] == 2
        assert state["retry_count"] == 1

    def test_state_schema_compliance(self, ladder_state):
        """
        Test 7: Verify nodes produce GraphState-compliant output

        Checks that all expected fields exist and have correct types.
        """
        state = ladder_state

        # Run full cycle
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/Sedov",
                "modifications": [{"section": "amr", "parameter": "max_level", "value": "2"}],
                "reasoning": "Test",
                "case_candidates": [],
                "baseline_confidence": 0.85
            }

            state = {**state, **architect_node(state)}

        # Verify Architect output schema
        assert "selected_case" in state
        assert isinstance(state["selected_case"], str)
        assert "modifications" in state
        assert isinstance(state["modifications"], list)
        assert "iteration" in state
        assert isinstance(state["iteration"], int)
        assert "workflow_history" in state
        assert isinstance(state["workflow_history"], list)
        assert "errors_active" in state
        assert isinstance(state["errors_active"], list)

        # Run Reviewer
        with patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:
            mock_rev = MockRev.return_value
            mock_rev.review_plan.return_value = {
                "approved": True,
                "errors": [],
                "warnings": []
            }
            mock_rev.estimate_resources.return_value = {
                "memory_gb": 8.0,
                "recommended_nodes": 1,
                "total_cells": 64000
            }

            state = reviewer_node(state)

        # Verify Reviewer output schema
        assert "review_analysis" in state
        assert isinstance(state["review_analysis"], dict)
        assert "errors_found" in state
        assert isinstance(state["errors_found"], list)
        assert "errors_fixed" in state
        assert isinstance(state["errors_fixed"], list)
        assert "mode" in state
        assert state["mode"] in ["initial", "retry", "fail", "proceed"]
