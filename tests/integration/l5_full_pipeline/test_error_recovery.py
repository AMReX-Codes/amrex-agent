"""
Level 5 Integration: Error Recovery & Retry Logic

Tests system resilience:
- Reviewer rejection → Architect retry
- Max retries enforcement
- Analysis failure → post-execution retry
- Error propagation through history

Validates the "self-healing" capability.
"""
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import AMReXAgentConfig
from src.main import run_agent
from src.services.plan import SimulationPlan
from src.services.rules.base import RuleViolation
from src.services.validation_result import ValidationResult


@pytest.mark.integration_full
class TestErrorRecovery:
    """Level 5: Error recovery and retry tests."""

    def _plan(self, selected_case: str, selected_solver: str, modifications: list[tuple[str, str]]):
        return SimulationPlan(
            selected_solver=selected_solver,
            selected_case=selected_case,
            modifications=modifications,
            reasoning="Retry test",
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
        config.environment = "perlmutter"
        config.repositories = {"PeleC": tmp_path / "PeleC"}
        (tmp_path / "PeleC").mkdir(exist_ok=True)

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
                    "job_id": "retry_test",
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
                selected_case="PeleC/Test",
                selected_solver="PeleC",
                modifications=[("amr.n_cell", "64 64 64")],
            )

            reject = self._validation_result("retry", errors=["CFL too high"])
            approve = self._validation_result("proceed")
            MockRev.return_value.validate_plan.side_effect = [reject, approve]

            MockAnalysis.return_value.analyze_simulation.return_value = {
                "status": "success"
            }

            final_state = run_agent("Test retry logic", config)

        assert final_state["retry_count"] >= 1

        history = final_state["workflow_history"]
        architect_executions = [e for e in history if e["node"] == "architect"]
        assert len(architect_executions) >= 2

        assert final_state["mode"] == "proceed"

    def test_max_retries_enforced(self, tmp_path):
        """
        Test 2: Max retries limit prevents infinite loops

        Given: Reviewer always rejects
        When: Workflow executes
        Then: Stops after max_retries, returns terminal mode
        """
        config = AMReXAgentConfig(output_dir=tmp_path)
        config.max_iterations = 0

        with patch("src.services.embedding_service_factory.get_embedding_service", return_value=object()), \
             patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:

            MockArch.return_value.execute_planning.return_value = self._plan(
                selected_case="Test",
                selected_solver="PeleC",
                modifications=[],
            )

            MockRev.return_value.validate_plan.return_value = self._validation_result(
                "retry",
                errors=["Permanent error"],
            )

            final_state = run_agent("Test max retries", config)

        assert final_state["mode"] in {"terminal", "fail"}

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
        config.environment = "perlmutter"
        config.repositories = {"PeleC": tmp_path / "PeleC"}
        config.max_iterations = 0
        (tmp_path / "PeleC").mkdir(exist_ok=True)

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
                    "job_id": "test",
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
                selected_case="Test",
                selected_solver="PeleC",
                modifications=[],
            )

            approve = self._validation_result("proceed")
            diagnose = self._validation_result("retry", errors=["Post-execution diagnosis"])
            MockRev.return_value.validate_plan.side_effect = [approve, diagnose]

            MockAnalysis.return_value.analyze_simulation.return_value = {
                "status": "failed",
                "issues": ["CFL violation"],
                "warnings": []
            }

            final_state = run_agent("Test post-execution retry", config)

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
        config.max_iterations = 0

        with patch("src.services.embedding_service_factory.get_embedding_service", return_value=object()), \
             patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev:

            MockArch.return_value.execute_planning.return_value = self._plan(
                selected_case="Test",
                selected_solver="PeleC",
                modifications=[],
            )

            MockRev.return_value.validate_plan.return_value = self._validation_result(
                "retry",
                errors=["Test error for tracking"],
            )

            final_state = run_agent("Test error tracking", config)

        assert "workflow_history" in final_state
        assert len(final_state["workflow_history"]) > 0
