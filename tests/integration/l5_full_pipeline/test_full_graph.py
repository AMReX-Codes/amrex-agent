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


@pytest.mark.integration_full
@pytest.mark.slow
class TestVisualizationParameterExtraction:
    """
    Visualization parameter extraction end-to-end.

    Architecture: Prompt visualization language must
    flow through to inputs file plotfile variable list.
    These tests are expected to FAIL before Session 5.
    They define the acceptance criteria for Session 5.
    """

    DEFAULT_PLOT_VARS = ["density", "pressure"]

    def _plan(
        self,
        prompt: str,
        baseline_dir: Path,
        visualization: dict | None = None,
    ) -> SimulationPlan:
        return SimulationPlan(
            selected_solver="PeleC",
            selected_case="PeleC/Exec/RegTests/PMF",
            modifications=[],
            reasoning="Visualization extraction baseline test",
            baseline_confidence=0.9,
            prompt=prompt,
            baseline={
                "code_name": "PeleC",
                "repo_path": str(baseline_dir.parents[3]),
                "case_path": "Exec/RegTests/PMF",
                "local_path": str(baseline_dir),
            },
            visualization=visualization or {},
        )

    def _make_baseline_dir(self, tmp_path: Path) -> Path:
        baseline = tmp_path / "PeleC" / "Exec" / "RegTests" / "PMF"
        baseline.mkdir(parents=True, exist_ok=True)
        (baseline / "AMReX.ex").write_text("#!/bin/bash\nexit 0\n")
        (baseline / "inputs").write_text(
            "\n".join(
                [
                    "# Mock inputs file",
                    "amr.n_cell = 64 64 64",
                    "amr.max_level = 0",
                    f"amr.plot_vars = {' '.join(self.DEFAULT_PLOT_VARS)}",
                    "",
                ]
            )
        )
        return baseline

    def _run_pipeline(self, prompt: str, tmp_path: Path, visualization: dict | None = None) -> dict:
        baseline_dir = self._make_baseline_dir(tmp_path)
        config = AMReXAgentConfig()
        config.output_dir = tmp_path / "output"
        config.environment = "perlmutter"
        config.repositories = {"PeleC": baseline_dir.parents[3]}
        config.run_mode = "dry_run"
        config.dry_run = True

        class DummyEmbeddingService:
            embeddings = None

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
                    "job_id": "viz_gate_test_123",
                    "method": "sbatch",
                    "script_path": str(Path(run_directory) / "submit.sh"),
                    "job_status": "completed",
                }

        with patch("src.services.embedding_service_factory.get_embedding_service", return_value=DummyEmbeddingService()), \
             patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev, \
             patch("src.services.cases.AMReXCasesService", return_value=object()), \
             patch("src.nodes.runner_node.SuperfacilityRunner", DummyRunner), \
             patch("src.nodes.analysis_node.AnalysisService") as MockAnalysis:

            MockArch.return_value.execute_planning.return_value = self._plan(
                prompt=prompt,
                baseline_dir=baseline_dir,
                visualization=visualization,
            )

            MockRev.return_value.validate_plan.return_value = ValidationResult(
                mode="proceed",
                violations=[],
                summary="ok",
                available_schema_params=[],
            )

            MockAnalysis.return_value.analyze_simulation.return_value = {
                "status": "success",
                "total_steps": 100,
                "final_time": 1.0,
                "issues": [],
                "warnings": [],
                "completed": True,
            }

            return run_agent(user_requirement=prompt, config=config)

    def _read_inputs_text(self, final_state: dict) -> str:
        inputs_path = final_state.get("inputs_file_path")
        assert inputs_path, "inputs_file_path missing from final state"
        path = Path(inputs_path)
        assert path.exists(), f"inputs file missing at {path}"
        return path.read_text()

    def _plot_vars(self, inputs_text: str) -> list[str]:
        for line in inputs_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("amr.plot_vars"):
                _, rhs = stripped.split("=", maxsplit=1)
                return rhs.strip().split()
        return []

    def _baseline_plot_vars(self, baseline_inputs_path: Path) -> list[str]:
        return self._plot_vars(baseline_inputs_path.read_text())

    def test_temperature_in_prompt_produces_plotfile_var(
            self, tmp_path):
        """
        Given: Prompt requesting temperature visualization
        When:  Full pipeline runs in dry mode
        Then:  Generated inputs file contains temperature
               in amr.plot_vars

        EXPECTED: FAIL (Input Writer ignores viz params)
        """
        final_state = self._run_pipeline(
            prompt="Run a PMF case and visualize temperature as pseudocolor.",
            tmp_path=tmp_path,
            visualization={"quantities": ["temperature"]},
        )
        plot_vars = self._plot_vars(self._read_inputs_text(final_state))
        assert "temperature" in plot_vars

    def test_multiple_quantities_all_in_plotfile_vars(
            self, tmp_path):
        """
        Given: Prompt requesting temp, velocity, vorticity
        When:  Full pipeline runs in dry mode
        Then:  All three quantities in amr.plot_vars

        EXPECTED: FAIL
        """
        final_state = self._run_pipeline(
            prompt=(
                "Run PMF and plot temperature, velocity, and vorticity fields."
            ),
            tmp_path=tmp_path,
            visualization={
                "quantities": ["temperature", "velocity", "vorticity"],
            },
        )
        plot_vars = self._plot_vars(self._read_inputs_text(final_state))
        assert "temperature" in plot_vars
        assert "velocity" in plot_vars
        assert "vorticity" in plot_vars

    def test_log_scale_in_prompt_sets_viz_metadata(
            self, tmp_path):
        """
        Given: Prompt specifying log scale visualization
        When:  Full pipeline runs
        Then:  GraphState visualization config contains
               color_scale = logarithmic
        """
        final_state = self._run_pipeline(
            prompt="Visualize temperature with logarithmic color scale.",
            tmp_path=tmp_path,
            visualization={
                "quantities": ["temperature"],
                "color_scale": "logarithmic",
            },
        )
        assert "visualization_config" in final_state
        assert final_state["visualization_config"]["color_scale"] == "logarithmic"

    def test_no_visualization_prompt_preserves_baseline(
            self, tmp_path):
        """
        Given: Prompt with no visualization language
        When:  Full pipeline runs in dry mode
        Then:  inputs file preserves baseline plotfile vars
               exactly, if baseline defines them.
        """
        baseline_dir = self._make_baseline_dir(tmp_path)
        baseline_inputs = baseline_dir / "inputs"
        baseline_plot_vars = self._baseline_plot_vars(baseline_inputs)

        final_state = self._run_pipeline(
            prompt="Run PMF baseline with default settings.",
            tmp_path=tmp_path,
            visualization={},
        )

        inputs_text = self._read_inputs_text(final_state)
        plot_vars = self._plot_vars(self._read_inputs_text(final_state))
        if baseline_plot_vars:
            assert plot_vars == baseline_plot_vars
        else:
            assert "amr.plot_vars" not in inputs_text
            assert "plot_vars" not in inputs_text

    def test_squall_line_with_viz_params(self, tmp_path):
        """
        Given: Squall line prompt with visualization language
               "plot vertical velocity and temperature
                as pseudocolor, log scale"
        When:  Full pipeline runs in dry mode
        Then:  inputs file contains velocity and temperature
               in amr.plot_vars

        EXPECTED: FAIL
        """
        final_state = self._run_pipeline(
            prompt=(
                "Set up a squall line case; plot vertical velocity and "
                "temperature as pseudocolor, log scale."
            ),
            tmp_path=tmp_path,
            visualization={
                "quantities": ["vertical_velocity", "temperature"],
                "color_scale": "logarithmic",
            },
        )
        plot_vars = self._plot_vars(self._read_inputs_text(final_state))
        assert "vertical_velocity" in plot_vars
        assert "temperature" in plot_vars
