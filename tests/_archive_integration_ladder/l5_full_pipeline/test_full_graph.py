"""
Level 5 Integration: Full Graph Execution

Tests complete workflow execution:
- Happy path: START → Architect → Reviewer → InputWriter → Runner → Analysis → Viz → END
- All nodes communicate correctly
- State flows through entire pipeline
- Files created and output artifacts produced

Mocked: LLM calls, ReviewerOrchestrator, actual job submission, visualization
Real: Graph orchestration, all nodes, state flow, file I/O
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.main import create_amrex_agent_graph, run_agent, initialize_state
from src.config import AMReXAgentConfig
from langgraph.graph import END


@pytest.mark.integration_full
@pytest.mark.slow
class TestFullGraphExecution:
    """Level 5: Complete graph execution tests."""

    def test_happy_path_full_workflow(self, mock_baseline_dir, tmp_path):
        """
        Test 1: Full workflow from start to finish (happy path)

        Flow:
        START → Architect → Reviewer (approve) → InputWriter → 
        Runner (dry_run) → Analysis (success) → Visualization → END

        Validates:
        - All nodes execute in order
        - State updated at each stage
        - workflow_history tracks full journey
        - Final mode = "proceed"
        """
        config = AMReXAgentConfig()
        config.output_dir = tmp_path

        # Mock all heavy components
        with patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev, \
             patch("src.services.run_superfacility.SuperfacilityRunner.submit") as MockSubmit, \
             patch("src.nodes.analysis_node.AnalysisService") as MockAnalysis, \
             patch("src.nodes.visualization_node.VisualizationService") as MockViz:

            # Architect returns valid plan
            MockArch.return_value.create_plan_rag.return_value = {
                "selected_case": "PeleC/Exec/RegTests/PMF",
                "modifications": [
                    {"section": "amr", "parameter": "n_cell", "value": "64 64 64"}
                ],
                "reasoning": "Test reasoning",
                "case_candidates": [],
                "baseline_confidence": 0.9
            }

            # Reviewer approves
            MockRev.return_value.review_plan.return_value = {
                "approved": True,
                "errors": [],
                "warnings": []
            }
            MockRev.return_value.estimate_resources.return_value = {
                "memory_gb": 4.0,
                "recommended_nodes": 1,
                "total_cells": 262144
            }

            # Runner submits successfully
            MockSubmit.return_value = {
                "job_id": "full_test_123",
                "method": "dry_run",
                "script_path": str(tmp_path / "run_001" / "submit.sh")
            }

            # Analysis succeeds
            MockAnalysis.return_value.analyze_simulation.return_value = {
                "status": "success",
                "total_steps": 100,
                "final_time": 1.0,
                "issues": [],
                "warnings": [],
                "completed": True
            }

            # Visualization succeeds
            MockViz.return_value.generate_visualizations.return_value = {
                "status": "success",
                "images": [str(tmp_path / "viz_001.png")],
                "backend": "matplotlib"
            }

            # Execute full workflow
            final_state = run_agent(
                user_requirement="Run a test simulation",
                config=config
            )

        # Verify final state
        assert final_state["mode"] == "proceed"
        assert final_state.get("job_id") == "full_test_123"

        # Verify all nodes executed
        history = final_state["workflow_history"]
        nodes_executed = [entry["node"] for entry in history]

        assert "architect" in nodes_executed
        assert "reviewer" in nodes_executed
        assert "input_writer" in nodes_executed
        assert "runner" in nodes_executed
        assert "analysis" in nodes_executed
        assert "visualization" in nodes_executed

        # Verify order
        arch_idx = next(i for i, e in enumerate(history) if e["node"] == "architect")
        rev_idx = next(i for i, e in enumerate(history) if e["node"] == "reviewer")
        writer_idx = next(i for i, e in enumerate(history) if e["node"] == "input_writer")

        assert arch_idx < rev_idx < writer_idx

    def test_graph_handles_recursion_limit(self, tmp_path):
        """
        Test 2: Graph respects recursion limit

        Given: Reviewer always rejects (infinite loop scenario)
        When: Graph executes
        Then: GraphRecursionError caught, returns fail status
        """
        config = AMReXAgentConfig()
        config.output_dir = tmp_path

        with patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:

            # Architect always returns plan
            MockArch.return_value.create_plan_rag.return_value = {
                "selected_case": "PeleC/Test",
                "modifications": [],
                "reasoning": "Test"
            }

            # Reviewer always rejects (infinite loop)
            MockRev.return_value.review_plan.return_value = {
                "approved": False,
                "errors": ["Permanent error"],
                "warnings": []
            }
            MockRev.return_value.suggest_fixes.return_value = {
                "modifications": []
            }

            # Execute
            final_state = run_agent(
                user_requirement="Test recursion limit",
                config=config
            )

        # Verify failure mode
        assert final_state["job_status"] == "failed"
        assert "recursion" in final_state["error"].lower()

    def test_graph_compilation_success(self):
        """
        Test 3: Graph compiles without errors

        Given: Default graph creation
        When: create_amrex_agent_graph() is called
        Then: Returns compilable StateGraph
        """
        graph = create_amrex_agent_graph()

        # Verify it's a StateGraph
        from langgraph.graph import StateGraph
        assert isinstance(graph, StateGraph)

        # Verify it compiles
        app = graph.compile()
        assert app is not None

    def test_state_initialization(self, tmp_path):
        """
        Test 4: State properly initialized

        Given: User requirement and config
        When: initialize_state() is called
        Then: All required fields populated
        """
        config = AMReXAgentConfig(output_dir=tmp_path)
        state = initialize_state("Test prompt", config)

        # Verify required fields
        assert state["prompt"] == "Test prompt"
        assert state["config"] == config
        assert state["mode"] == "initial"
        assert state["iteration"] == 0
        assert state["retry_count"] == 0
        assert state["max_retries"] == 3
        assert isinstance(state["workflow_history"], list)
        assert isinstance(state["errors_active"], list)
