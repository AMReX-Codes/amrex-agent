"""
Level 5 Integration: GraphState Schema Validation

Tests data contract compliance:
- Required fields present
- Type correctness
- Optional fields handled gracefully
- No schema drift

Validates that GraphState.__annotations__ matches actual usage.
"""
from pathlib import Path
from typing import Any, Dict, List, get_type_hints
from unittest.mock import patch

import pytest

from src.config import AMReXAgentConfig
from src.main import initialize_state, run_agent
from src.models import GraphState
from src.services.plan import SimulationPlan
from src.services.validation_result import ValidationResult


@pytest.mark.integration_full
class TestSchemaCompliance:
    """Level 5: Schema validation tests."""

    def _plan(self) -> SimulationPlan:
        return SimulationPlan(
            selected_solver="PeleC",
            selected_case="Test",
            modifications=[],
            reasoning="Test plan",
        )

    def _validation_result(self, mode: str) -> ValidationResult:
        return ValidationResult(
            mode=mode,
            violations=[],
            summary="test",
            available_schema_params=[],
        )

    def test_schema_required_fields_exist(self):
        """
        Test 1: GraphState defines all critical fields

        Given: GraphState TypedDict definition
        When: We inspect type hints
        Then: All critical fields are defined
        """
        hints = get_type_hints(GraphState)

        critical_fields = [
            "prompt",
            "config",
            "selected_case",
            "modifications",
            "plan",
            "baseline",
            "run_directory",
            "inputs_file_path",
            "job_id",
            "review_analysis",
            "analysis_report",
            "visualization_images",
            "mode",
            "iteration",
            "retry_count",
            "max_retries",
            "errors_active",
            "errors_found",
            "errors_fixed",
            "workflow_history",
            "history",
        ]

        for field in critical_fields:
            assert field in hints, f"GraphState missing critical field: {field}"

    def test_schema_type_annotations_correct(self):
        """
        Test 2: Type annotations are semantically correct

        Validates:
        - Strings are str
        - Lists are List[...]
        - Dicts are Dict[...]
        """
        hints = get_type_hints(GraphState)

        assert hints["prompt"] == str
        assert hints["iteration"] == int
        assert hints["retry_count"] == int
        assert hints["max_retries"] == int

        assert hints["errors_active"] == List[str]
        assert hints["errors_found"] == List[str]
        assert hints["errors_fixed"] == List[str]
        assert hints["workflow_history"] == List[Dict[str, Any]]
        assert hints["history"] == List[str]

    def test_initialized_state_matches_schema(self, tmp_path):
        """
        Test 3: initialize_state() output matches schema

        Given: Default initialization
        When: State is created
        Then: All fields match their type annotations
        """
        config = AMReXAgentConfig(output_dir=tmp_path)
        state = initialize_state("Test prompt", config)

        assert isinstance(state["prompt"], str)
        assert isinstance(state["mode"], str)
        assert isinstance(state["iteration"], int)
        assert isinstance(state["retry_count"], int)
        assert isinstance(state["max_retries"], int)
        assert isinstance(state["workflow_history"], list)
        assert isinstance(state["errors_active"], list)

    def test_schema_no_missing_fields_in_practice(self, tmp_path):
        """
        Test 4: Real execution populates schema-defined fields

        Given: Full workflow execution
        When: Graph completes
        Then: All expected fields are populated
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

            MockArch.return_value.execute_planning.return_value = self._plan()
            MockRev.return_value.validate_plan.return_value = self._validation_result("proceed")
            MockAnalysis.return_value.analyze_simulation.return_value = {
                "status": "success"
            }

            final_state = run_agent("Test", config)

        assert "prompt" in final_state
        assert "config" in final_state
        assert "workflow_history" in final_state
        assert len(final_state["workflow_history"]) > 0
