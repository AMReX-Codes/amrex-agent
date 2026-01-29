"""
Level 1 Integration: Architect + Reviewer State Flow

Tests macro-level control flow without filesystem I/O:
- Happy path: Architect → Reviewer (approve) → proceed
- Retry loop: Architect → Reviewer (reject) → Architect (fix) → proceed
- Max retries: Loop termination

Mocked: LLM calls, filesystem
Real: State transitions, retry logic, routing
"""
import pytest
from unittest.mock import Mock, patch
from src.nodes.architect_node import architect_node
from src.nodes.reviewer_node import reviewer_node
from src.router_func import route_after_reviewer
from src.services.rules.base import RuleViolation
from src.services.validation_result import ValidationResult
from langgraph.graph import END


@pytest.mark.integration_l1
class TestArchitectReviewerFlow:
    """Level 1: State-only integration tests."""

    def test_happy_path_initial_to_proceed(self, ladder_state):
        """
        Test 1: Happy Path - Architect → Reviewer (approve) → proceed

        Flow:
        1. Architect creates plan
        2. Reviewer approves
        3. Mode = "proceed"
        4. Router sends to input_writer
        """
        state = ladder_state

        # Mock ArchitectService
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/Sedov",
                "modifications": [
                    {"section": "amr", "parameter": "max_level", "value": "2"}
                ],
                "reasoning": "Test reasoning",
                "case_candidates": [],
                "baseline_confidence": 0.9
            }

            # 1. Run Architect
            updates_arch = architect_node(state)
            state = {**state, **updates_arch}

        # Verify Architect output
        assert state["selected_case"] == "PeleC/Exec/RegTests/Sedov"
        assert len(state["modifications"]) == 1
        assert state["iteration"] == 1
        assert state["mode"] == "proceed"  # Optimistic

        # Mock ReviewerOrchestrator
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

            # 2. Run Reviewer
            state = reviewer_node(state)

        # Verify final state
        assert state["mode"] == "proceed"  # Reviewer transitions to proceed on approval
        assert state["errors_active"] == []
        assert state["review_analysis"]["approved"] is True

        # 3. Test routing
        next_node = route_after_reviewer(state)
        assert next_node == "input_writer"

    def test_retry_loop_single_iteration(self, ladder_state):
        """
        Test 2: Retry Loop - Single retry then succeed

        Flow:
        1. Architect creates plan (iteration 0)
        2. Reviewer rejects with error
        3. Mode = "retry", Router → architect
        4. Architect retries (iteration 1)
        5. Reviewer approves
        6. Mode = "initial", Router → input_writer
        """
        state = ladder_state

        # === Attempt 1: Initial Plan ===
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value

            # First attempt - bad plan
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/PMF",
                "modifications": [
                    {"section": "pelec", "parameter": "cfl", "value": "1.5"}  # Too high
                ],
                "reasoning": "Initial attempt"
            }

            state = {**state, **architect_node(state)}

        assert state["iteration"] == 1
        assert state["retry_count"] == 0  # Not incremented yet (mode was 'initial')

        # Reviewer rejects
        with patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:
            mock_rev = MockRev.return_value
            violation = RuleViolation(
                rule_name="CFLRule",
                severity="error",
                message="CFL 1.5 exceeds safe limit 0.9"
            )
            mock_rev.review_plan.return_value = {
                "approved": False,
                "errors": ["CFL 1.5 exceeds safe limit 0.9"],
                "warnings": []
            }
            mock_rev.suggest_fixes.return_value = {
                "modifications": [{"parameter": "pelec.cfl", "value": "0.5"}]
            }

            state = reviewer_node(state)

        # Verify retry state
        assert state["mode"] == "retry"
        assert len(state["errors_active"]) == 1
        assert "CFL" in state["errors_active"][0]

        # Router sends back to architect
        next_node = route_after_reviewer(state)
        assert next_node == "architect"

        # === Attempt 2: Fixed Plan ===
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value

            # Second attempt - fixed plan
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/PMF",
                "modifications": [
                    {"section": "pelec", "parameter": "cfl", "value": "0.5"}  # Fixed
                ],
                "reasoning": "Retry with corrected CFL"
            }

            state = {**state, **architect_node(state)}

        # Verify retry counters incremented
        assert state["iteration"] == 2
        assert state["retry_count"] == 1  # Now incremented (mode was 'retry')
        assert state["errors_active"] == []  # Architect clears errors

        # Reviewer approves
        with patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:
            mock_rev = MockRev.return_value
            mock_rev.review_plan.return_value = {
                "approved": True,
                "errors": [],
                "warnings": []
            }
            mock_rev.estimate_resources.return_value = {
                "memory_gb": 4.0,
                "recommended_nodes": 1,
                "total_cells": 32000
            }

            state = reviewer_node(state)

        # Verify success
        assert state["mode"] == "initial"
        assert state["errors_active"] == []

        # Router proceeds
        next_node = route_after_reviewer(state)
        assert next_node == "input_writer"

    def test_max_retries_termination(self, ladder_state):
        """
        Test 3: Max Retries - Loop terminates after limit

        Flow:
        1. Reviewer always rejects
        2. Loop runs max_retries times
        3. Architect returns mode="fail" when limit exceeded
        4. Router sends to END
        """
        state = ladder_state
        state["max_retries"] = 2  # Limit to 2 retries for test speed

        # Mock services
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/Sedov",
                "modifications": [],
                "reasoning": "Stubborn bad plan"
            }

            with patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:
                mock_rev = MockRev.return_value
                # Always reject
                mock_rev.review_plan.return_value = {
                    "approved": False,
                    "errors": ["Unfixable error"],
                    "warnings": []
                }
                mock_rev.suggest_fixes.return_value = {"modifications": []}

                # Loop until termination
                for attempt in range(5):  # Arbitrary high number
                    # Run Architect
                    state = {**state, **architect_node(state)}

                    # Check if Architect itself terminated
                    if state.get("mode") == "fail":
                        break

                    # Run Reviewer
                    state = reviewer_node(state)

                    # Check routing
                    if route_after_reviewer(state) == END:
                        break

        # Verify termination
        assert state["retry_count"] > state["max_retries"]
        assert state["mode"] == "fail"
        assert route_after_reviewer(state) == END

    def test_workflow_history_tracking(self, ladder_state):
        """
        Test 4: Workflow history is appended correctly

        Validates that both Architect and Reviewer add structured entries
        to workflow_history during a retry loop.
        """
        state = ladder_state

        # Initial history should be empty
        assert len(state.get("workflow_history", [])) == 0

        # Mock services
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/Sedov",
                "modifications": [{"section": "amr", "parameter": "max_level", "value": "3"}],
                "reasoning": "Test reasoning for history"
            }

            # Run Architect
            state = {**state, **architect_node(state)}

        # Verify Architect history entry
        history = state["workflow_history"]
        assert len(history) == 1
        assert history[0]["node"] == "architect"
        assert history[0]["action"] == "plan_created"
        assert history[0]["iteration"] == 1
        assert "timestamp" in history[0]

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

        # Verify Reviewer history entry
        history = state["workflow_history"]
        assert len(history) == 2
        assert history[1]["node"] == "reviewer"
        assert history[1]["action"] == "approved"
        assert history[1]["iteration"] == 1
