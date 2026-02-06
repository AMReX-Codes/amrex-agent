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
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import AMReXAgentConfig
from src.main import create_amrex_agent_graph, initialize_state, run_agent
from src.services.plan import SimulationPlan
from src.services.rules.base import RuleViolation
from src.services.validation_result import ValidationResult


@pytest.mark.integration_full
@pytest.mark.slow
class TestFullGraphExecution:
    """Level 5: Complete graph execution tests."""

    def _plan(self, selected_case: str, selected_solver: str, modifications: list[tuple[str, str]]):
        return SimulationPlan(
            selected_solver=selected_solver,
            selected_case=selected_case,
            modifications=modifications,
            reasoning="Test reasoning",
            baseline_confidence=0.9,
        )

    def _validation_result(self, mode: str, errors: list[str] | None = None) -> ValidationResult:
        violations = [
            RuleViolation(
                rule_name="TestRule",
                severity="error",
                message=msg,
            )
            for msg in (errors or [])
        ]
        return ValidationResult(
            mode=mode,
            violations=violations,
            summary="test",
            available_schema_params=[],
        )

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
        config.environment = "perlmutter"
        config.repositories = {"PeleC": tmp_path / "PeleC"}
        (tmp_path / "PeleC").mkdir(exist_ok=True)

        # Mock all heavy components
        class DummyEmbeddingService:
            embeddings = None

        class DummyInputWriterService:
            def __init__(self, _config):
                self.cases_svc = None

            def apply_plan(self, selected_case, modifications, baseline, reasoning, output_dir):
                run_dir = Path(output_dir)
                run_dir.mkdir(parents=True, exist_ok=True)
                inputs_path = run_dir / "inputs"
                inputs_path.write_text("# inputs")
                return {
                    "run_dir": str(run_dir),
                    "inputs_path": str(inputs_path),
                    "inputs_file_selected": str(inputs_path),
                    "inputs_file_strategy": "newest",
                    "inputs_file_override": None,
                    "inputs_candidates": [],
                    "status": "success",
                }

        class DummyRunner:
            def __init__(self, _config):
                pass

            def setup_job(self, output_dir, case_dir, inputs_path=None):
                return {
                    "run_dir": output_dir,
                    "executable": "AMReX.ex",
                }

            def submit(self, run_directory, nodes=None, run_mode=None, dry_run=None, case_dir=None):
                return {
                    "job_id": "full_test_123",
                    "method": "sbatch",
                    "script_path": str(Path(run_directory) / "submit.sh"),
                    "job_status": "completed",
                }

        with patch("src.services.embedding_service_factory.get_embedding_service", return_value=DummyEmbeddingService()), \
             patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev, \
             patch("src.services.cases.AMReXCasesService", return_value=object()), \
             patch("src.nodes.input_writer_node.InputWriterService", DummyInputWriterService), \
             patch("src.nodes.runner_node.SuperfacilityRunner", DummyRunner), \
             patch("src.nodes.analysis_node.AnalysisService") as MockAnalysis:

            MockArch.return_value.execute_planning.return_value = self._plan(
                selected_case="PeleC/Exec/RegTests/PMF",
                selected_solver="PeleC",
                modifications=[("amr.n_cell", "64 64 64")],
            )

            MockRev.return_value.validate_plan.return_value = self._validation_result("proceed")

            MockAnalysis.return_value.analyze_simulation.return_value = {
                "status": "success",
                "total_steps": 100,
                "final_time": 1.0,
                "issues": [],
                "warnings": [],
                "completed": True,
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

        with patch("src.services.embedding_service_factory.get_embedding_service", return_value=object()), \
             patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:

            MockArch.return_value.execute_planning.return_value = self._plan(
                selected_case="PeleC/Test",
                selected_solver="PeleC",
                modifications=[],
            )

            MockRev.return_value.validate_plan.return_value = self._validation_result(
                "retry",
                errors=["Permanent error"],
            )

            # Execute
            final_state = run_agent(
                user_requirement="Test recursion limit",
                config=config
            )

        # Verify failure mode
        assert final_state["mode"] in {"terminal", "fail"}

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
