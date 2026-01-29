"""
Level 3 Integration: Complete L1→L2→L3 Pipeline

Tests full state flow from Architect through Analysis:
- Architect → Reviewer → InputWriter → Analysis
- Mock Runner output injected at L3 boundary
- State flows correctly through all stages

Mocked: LLM calls, ReviewerOrchestrator, Runner execution
Real: All nodes, state transitions, Analysis parsing
"""
import pytest
from pathlib import Path
from unittest.mock import patch
from src.nodes.architect_node import architect_node
from src.nodes.reviewer_node import reviewer_node
from src.nodes.input_writer_node import input_writer_node
from src.nodes.analysis_node import analysis_node


@pytest.mark.integration_l3
class TestPostprocessingFlow:
    """Level 3: Full L1→L2→L3 pipeline."""

    def test_full_l1_l2_l3_pipeline(self, tmp_path, sample_simulation_output):
        """
        Test: Complete pipeline from Architect to Analysis

        Flow:
        1. L1: Architect creates plan
        2. L1: Reviewer approves
        3. L2: InputWriter creates files
        4. L3: Analysis reads mock output

        Validates state flows correctly through all stages.
        """
        from tests.integration.fixtures.sample_graph_states import get_l1_state

        state = get_l1_state()
        state["config"].output_dir = str(tmp_path)
        state["run_directory"] = str(tmp_path)

        # === L1: Architect ===
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/PMF",
                "modifications": [
                    {"section": "amr", "parameter": "n_cell", "value": "64 64 64"}
                ],
                "reasoning": "Test reasoning",
                "case_candidates": [],
                "baseline_confidence": 0.9
            }

            state = {**state, **architect_node(state)}

        # Build plan for InputWriter
        state["plan"] = {
            "baseline": {"code": "PeleC", "path": state["selected_case"]},
            "modifications": state["modifications"]
        }

        # === L1: Reviewer ===
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
                "total_cells": 262144
            }

            state = reviewer_node(state)

        assert state["mode"] == "proceed"  # Reviewer approved (transitions to proceed)

        # === L2: InputWriter ===
        state = {**state, **input_writer_node(state)}

        assert "run_directory" in state
        assert Path(state["run_directory"]).exists()

        # === Mock L3 boundary: Inject simulation output ===
        # In real workflow, Runner would execute and create output
        # Here we inject pre-created mock output
        state["run_directory"] = str(sample_simulation_output)

        # === L3: Analysis ===
        state = analysis_node(state)

        # Verify final state
        assert "analysis_report" in state
        report = state["analysis_report"]

        assert report["status"] == "success"
        assert "total_steps" in report
        assert len(state["history"]) >= 2  # Reviewer, Analysis (mocked nodes don't add history)

    def test_pipeline_handles_analysis_failure(self, tmp_path, failed_simulation_output):
        """
        Test: Pipeline detects analysis failure

        Given: Failed simulation output
        When: Pipeline runs through L3
        Then: Analysis detects failure, error_logs populated
        """
        from tests.integration.fixtures.sample_graph_states import get_l2_state

        state = get_l2_state(tmp_path)
        state["config"].output_dir = str(tmp_path)

        # === L2: InputWriter ===
        state = {**state, **input_writer_node(state)}

        # === Mock L3 boundary: Inject failed output ===
        state["run_dir"] = str(failed_simulation_output)

        # === L3: Analysis ===
        state = analysis_node(state)

        # Verify failure detected
        assert state["analysis_report"]["status"] == "failed"
        assert "error_logs" in state
        assert len(state["error_logs"]) > 0
