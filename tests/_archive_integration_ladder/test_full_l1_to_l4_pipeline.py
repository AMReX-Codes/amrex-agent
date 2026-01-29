"""
Level 4 Integration: Complete L1→L2→L3→L4 Pipeline

Tests full workflow from Architect through Runner:
- Architect creates plan
- Reviewer approves
- InputWriter creates files
- Runner sets up job (dry_run)

This is the "Grand Integration Test" before L5 (full execution).

Mocked: LLM calls, ReviewerOrchestrator, actual job submission
Real: All nodes, state flow, file operations, job setup
"""
import pytest
from pathlib import Path
from unittest.mock import patch
from src.nodes.architect_node import architect_node
from src.nodes.reviewer_node import reviewer_node
from src.nodes.input_writer_node import input_writer_node
from src.nodes.runner_node import runner_node
from textwrap import dedent


@pytest.mark.integration_l4
class TestFullPipeline:
    """Level 4: Complete L1→L2→L3→L4 workflow."""

    def test_complete_l1_l2_l4_pipeline(self, mock_baseline_dir, tmp_path):
        """
        Test: Full pipeline from Architect to Runner

        Flow:
        1. L1: Architect creates plan
        2. L1: Reviewer approves
        3. L2: InputWriter creates files
        4. L4: Runner sets up job (dry_run)

        Validates state flows correctly and files are created.
        """
        from tests.integration.fixtures.sample_graph_states import get_l1_state

        state = get_l1_state()
        state["config"].output_dir = str(tmp_path)

        # === L1: Architect ===
        with patch("src.nodes.architect_node.ArchitectService") as MockArch:
            mock_arch_svc = MockArch.return_value
            mock_arch_svc.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/PMF",
                "modifications": [
                    {"section": "amr", "parameter": "n_cell", "value": "128 128 128"}
                ],
                "reasoning": "High resolution test",
                "case_candidates": [],
                "baseline_confidence": 0.95
            }

            state = {**state, **architect_node(state)}

        # Build plan for InputWriter
        state["plan"] = {
            "baseline": {
                "code": "PeleC",
                "path": state["selected_case"],
                "local_path": str(mock_baseline_dir)
            },
            "modifications": state["modifications"]
        }
        state["baseline"] = state["plan"]["baseline"]

        # === L1: Reviewer ===
        with patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:
            mock_rev = MockRev.return_value
            mock_rev.review_plan.return_value = {
                "approved": True,
                "errors": [],
                "warnings": []
            }
            mock_rev.estimate_resources.return_value = {
                "memory_gb": 8.0,
                "recommended_nodes": 2,
                "total_cells": 2097152
            }

            state = reviewer_node(state)

        assert state["mode"] == "proceed"  # Reviewer approved

        # === L2: InputWriter ===
        state = {**state, **input_writer_node(state)}

        assert "run_directory" in state
        assert Path(state["run_directory"]).exists()

        # === L4: Runner (dry_run) ===
        with patch("src.services.run_superfacility.SuperfacilityRunner.submit") as mock_submit:
            mock_submit.return_value = {
                "job_id": "pipeline_test_456",
                "method": "dry_run",
                "script_path": str(Path(state["run_directory"]) / "submit.sh")
            }

            state = {**state, **runner_node(state)}

        # === Verify Final State ===
        assert state["mode"] == "proceed"
        assert "executable" in state
        assert "job_id" in state
        assert state["job_id"] == "pipeline_test_456"

        # Verify run directory has all files
        run_dir = Path(state["run_directory"])
        assert (run_dir / "inputs").exists()

        # Verify workflow history complete
        history = state["workflow_history"]
        nodes_executed = [entry["node"] for entry in history]
        assert "architect" in nodes_executed
        assert "input_writer" in nodes_executed
        assert "runner" in nodes_executed
