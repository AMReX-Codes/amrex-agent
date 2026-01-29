"""
Level 2 Integration: Plan → Files State Handoff

Tests L1 → L2 state transition:
- State fields updated correctly
- Workflow history preserved
- Ready flags set
- Mode transitions

Mocked: LLM calls
Real: State transitions, field updates
"""
import pytest
from pathlib import Path
from unittest.mock import patch
from src.nodes.architect_node import architect_node
from src.nodes.reviewer_node import reviewer_node
from src.nodes.input_writer_node import input_writer_node
from src.services.validation_result import ValidationResult


@pytest.mark.integration_l2
class TestPlanToFilesHandoff:
    """Level 2: L1 → L2 state handoff validation."""

    def test_state_keys_updated_for_runner(self, ladder_state, tmp_path):
        """
        Test 1: InputWriter updates state with required fields for Runner

        Given: L2 state with plan
        When: InputWriterNode executes
        Then: State has run_directory, inputs_file_path, ready_to_run
        """
        state = ladder_state
        state["config"].output_dir = str(tmp_path)

        # Execute
        updates = input_writer_node(state)

        # Verify required fields for L3 (Runner)
        assert "run_directory" in updates
        assert "inputs_file_path" in updates
        assert "ready_to_run" in updates
        assert updates["ready_to_run"] is True

        # Verify mode progression
        assert "mode" in updates
        assert updates["mode"] == "proceed"

    def test_full_l1_to_l2_flow(self, tmp_path):
        """
        Test 2: Complete L1 → L2 pipeline

        Flow:
        1. Architect creates plan
        2. Reviewer approves
        3. InputWriter creates files
        4. State correctly flows through all stages
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
                    {"section": "amr", "parameter": "n_cell", "value": "64 64 64"}
                ],
                "reasoning": "Test case",
                "case_candidates": [],
                "baseline_confidence": 0.9
            }

            state = {**state, **architect_node(state)}

        # Verify Architect output
        # Plan field is present (canonical state from L1)
        assert "plan" in state
        assert state["plan"]["selected_case"] == state["selected_case"]
        assert state["selected_case"] == "PeleC/Exec/RegTests/PMF"

        # Reconstruct plan for InputWriter (temporary bridge)
        state["plan"] = {
            "baseline": {
                "code": "PeleC",
                "path": state["selected_case"]
            },
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

        # Verify Reviewer output
        assert state["mode"] == "initial"  # Approved

        # === L2: InputWriter ===
        state = {**state, **input_writer_node(state)}

        # Verify final state
        assert "run_directory" in state
        assert "inputs_file_path" in state
        assert Path(state["run_directory"]).exists()
        assert Path(state["inputs_file_path"]).exists()

    def test_workflow_history_preserved(self, ladder_state, tmp_path):
        """
        Test 3: InputWriter preserves and appends to workflow_history

        Given: State with existing workflow_history from L1
        When: InputWriterNode executes
        Then: History is preserved and new entry added
        """
        state = ladder_state
        state["config"].output_dir = str(tmp_path)

        # Add fake L1 history
        state["workflow_history"] = [
            {"node": "architect", "action": "plan_created", "iteration": 1},
            {"node": "reviewer", "action": "approved", "iteration": 1}
        ]

        initial_history_len = len(state["workflow_history"])

        # Execute
        updates = input_writer_node(state)

        # Verify history preserved and appended
        new_history = updates["workflow_history"]
        assert len(new_history) == initial_history_len + 1

        # Verify new entry structure
        latest_entry = new_history[-1]
        assert latest_entry["node"] == "input_writer"
        assert latest_entry["action"] == "files_written"
        assert "timestamp" in latest_entry
        assert "run_directory" in latest_entry

    def test_error_handling_sets_retry_mode(self, tmp_path):
        """
        Test 4: InputWriter errors set mode=retry for Architect feedback

        Given: Service returns validation error
        When: InputWriterNode processes error result
        Then: mode=retry and errors_active populated
        """
        from tests.integration.fixtures.sample_graph_states import get_l2_state

        state = get_l2_state(tmp_path)
        state["config"].output_dir = str(tmp_path / "nonexistent")

        # Patch service to return error
        with patch("src.nodes.input_writer_node.InputWriterService") as MockSvc:
            mock_svc = MockSvc.return_value
            mock_svc.apply_plan.return_value = {
                "status": "error",
                "error": "Validation failed: missing parameter amr.max_level",
                "errors": ["missing parameter amr.max_level"],
                "run_dir": None
            }

            updates = input_writer_node(state)

        # Verify error handling
        assert updates["mode"] == "retry"
        assert updates["ready_to_run"] is False
        assert "errors_active" in updates
        assert len(updates["errors_active"]) > 0
