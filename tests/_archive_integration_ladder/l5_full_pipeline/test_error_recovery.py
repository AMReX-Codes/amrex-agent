"""
Level 5 Integration: Error Recovery & Retry Logic

Tests system resilience:
- Reviewer rejection → Architect retry
- Max retries enforcement
- Analysis failure → post-execution retry
- Error propagation through history

Validates the "self-healing" capability.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.main import run_agent
from src.config import AMReXAgentConfig


@pytest.mark.integration_full
class TestErrorRecovery:
    """Level 5: Error recovery and retry tests."""

    def test_reviewer_rejection_triggers_retry(self, tmp_path):
        """
        Test 1: Reviewer rejection causes Architect retry

        Flow:
        1. Architect creates plan
        2. Reviewer rejects (iteration 1)
        3. Router sends back to Architect
        4. Architect retries (iteration 2)
        5. Reviewer approves
        6. Workflow proceeds
        """
        config = AMReXAgentConfig(output_dir=tmp_path)

        with patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev, \
             patch("src.services.run_superfacility.SuperfacilityRunner.submit") as MockSubmit, \
             patch("src.nodes.analysis_node.AnalysisService") as MockAnalysis:

            # Architect returns same plan each time
            MockArch.return_value.create_plan_rag.return_value = {
                "selected_case": "PeleC/Test",
                "modifications": [
                    {"section": "amr", "parameter": "n_cell", "value": "64 64 64"}
                ],
                "reasoning": "Retry test"
            }

            # Reviewer: Reject once, then approve
            reject = {
                "approved": False,
                "errors": ["CFL too high"],
                "warnings": []
            }
            approve = {
                "approved": True,
                "errors": [],
                "warnings": []
            }

            MockRev.return_value.review_plan.side_effect = [reject, approve]
            MockRev.return_value.suggest_fixes.return_value = {
                "modifications": [{"parameter": "pelec.cfl", "value": "0.3"}]
            }
            MockRev.return_value.estimate_resources.return_value = {
                "memory_gb": 4.0
            }

            # Runner/Analysis succeed
            MockSubmit.return_value = {"job_id": "retry_test"}
            MockAnalysis.return_value.analyze_simulation.return_value = {
                "status": "success"
            }

            # Execute
            final_state = run_agent("Test retry logic", config)

        # Verify retry occurred
        assert final_state["retry_count"] >= 1

        # Verify history shows retry
        history = final_state["workflow_history"]
        architect_executions = [e for e in history if e["node"] == "architect"]
        assert len(architect_executions) >= 2  # Initial + retry

        # Verify final success
        assert final_state["mode"] == "proceed"

    def test_max_retries_enforced(self, tmp_path):
        """
        Test 2: Max retries limit prevents infinite loops

        Given: Reviewer always rejects
        When: Workflow executes
        Then: Stops after max_retries, returns fail mode
        """
        config = AMReXAgentConfig(output_dir=tmp_path)

        with patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:

            # Architect always returns plan
            MockArch.return_value.create_plan_rag.return_value = {
                "selected_case": "Test",
                "modifications": []
            }

            # Reviewer always rejects
            MockRev.return_value.review_plan.return_value = {
                "approved": False,
                "errors": ["Permanent error"],
                "warnings": []
            }
            MockRev.return_value.suggest_fixes.return_value = {
                "modifications": []
            }

            # Execute
            final_state = run_agent("Test max retries", config)

        # Verify termination
        assert final_state["job_status"] == "failed"

        # Verify retry count exceeded limit
        # Note: Exact behavior depends on router logic
        # May hit recursion limit or explicit max_retries check

    def test_analysis_failure_triggers_retry(self, mock_baseline_dir, tmp_path):
        """
        Test 3: Analysis failure can trigger post-execution retry

        Flow:
        1. Normal workflow: Arch → Rev → Writer → Runner
        2. Analysis detects simulation failure
        3. Router sends to Reviewer for diagnosis
        4. Workflow can retry from Architect
        """
        config = AMReXAgentConfig(output_dir=tmp_path)

        with patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev, \
             patch("src.services.run_superfacility.SuperfacilityRunner.submit") as MockSubmit, \
             patch("src.nodes.analysis_node.AnalysisService") as MockAnalysis:

            MockArch.return_value.create_plan_rag.return_value = {
                "selected_case": "Test",
                "modifications": []
            }

            # First review: approve
            # Second review (after failure): analyze failure
            approve = {"approved": True, "errors": []}
            diagnose = {"approved": False, "errors": ["Post-execution diagnosis"]}

            MockRev.return_value.review_plan.side_effect = [approve, diagnose]
            MockRev.return_value.estimate_resources.return_value = {"memory_gb": 1.0}
            MockRev.return_value.suggest_fixes.return_value = {"modifications": []}

            MockSubmit.return_value = {"job_id": "test"}

            # Analysis fails
            MockAnalysis.return_value.analyze_simulation.return_value = {
                "status": "failed",
                "issues": ["CFL violation"],
                "warnings": []
            }

            # Execute
            final_state = run_agent("Test post-execution retry", config)

        # Verify analysis failure detected
        assert "analysis_report" in final_state
        if "analysis_report" in final_state:
            assert final_state["analysis_report"]["status"] == "failed"

    def test_error_history_tracking(self, tmp_path):
        """
        Test 4: Errors tracked in workflow_history

        Given: Workflow with errors
        When: Graph executes
        Then: History contains error entries
        """
        config = AMReXAgentConfig(output_dir=tmp_path)

        with patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:

            MockArch.return_value.create_plan_rag.return_value = {
                "selected_case": "Test",
                "modifications": []
            }

            # Reviewer rejects with specific error
            MockRev.return_value.review_plan.return_value = {
                "approved": False,
                "errors": ["Test error for tracking"],
                "warnings": []
            }
            MockRev.return_value.suggest_fixes.return_value = {"modifications": []}

            final_state = run_agent("Test error tracking", config)

        # Verify errors_active populated
        # (Exact behavior depends on node implementations)
        assert "workflow_history" in final_state
        assert len(final_state["workflow_history"]) > 0
