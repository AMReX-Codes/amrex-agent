"""
Level 5 Integration: GraphState Schema Validation

Tests data contract compliance:
- Required fields present
- Type correctness
- Optional fields handled gracefully
- No schema drift

Validates that GraphState.__annotations__ matches actual usage.
"""
import pytest
from typing import get_type_hints, Optional, Dict, List, Any
from src.models import GraphState
from src.main import initialize_state
from src.config import AMReXAgentConfig


@pytest.mark.integration_full
class TestSchemaCompliance:
    """Level 5: Schema validation tests."""

    def test_schema_required_fields_exist(self):
        """
        Test 1: GraphState defines all critical fields

        Given: GraphState TypedDict definition
        When: We inspect type hints
        Then: All critical fields are defined
        """
        hints = get_type_hints(GraphState)

        critical_fields = [
            "user_requirement",
            "config",
            "plan",
            "baseline",
            "requirements",
            "inputs_path",
            "run_dir",
            "executable",
            "job_id",
            "review_analysis",
            "analysis_report",
            "visualization_images",
            "mode",
            "iteration",
            "max_iterations",
            "errors_active",
            "errors_found",
            "errors_fixed",
            "workflow_history",
            "history"
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
        - Optional fields are Optional[...]
        """
        hints = get_type_hints(GraphState)

        # Required string fields
        assert hints["user_requirement"] == str
        assert hints["mode"] == str
        assert hints["phase"] == str

        # Required int fields
        assert hints["iteration"] == int
        assert hints["max_iterations"] == int
        assert hints["loop_count"] == int

        # Required list fields
        assert hints["errors_active"] == List[str]
        assert hints["errors_found"] == List[str]
        assert hints["errors_fixed"] == List[str]
        assert hints["workflow_history"] == List[Dict[str, Any]]
        assert hints["history"] == List[str]

        # Optional fields
        import typing
        assert typing.get_origin(hints["plan"]) == typing.Union  # Optional is Union[X, None]
        assert typing.get_origin(hints["baseline"]) == typing.Union
        assert typing.get_origin(hints["job_id"]) == typing.Union

    def test_initialized_state_matches_schema(self, tmp_path):
        """
        Test 3: initialize_state() output matches schema

        Given: Default initialization
        When: State is created
        Then: All fields match their type annotations
        """
        config = AMReXAgentConfig(output_dir=tmp_path)
        state = initialize_state("Test prompt", config)

        # Verify types match schema
        assert isinstance(state["prompt"], str)
        assert isinstance(state["mode"], str)
        assert isinstance(state["iteration"], int)
        assert isinstance(state["retry_count"], int)
        assert isinstance(state["max_retries"], int)
        assert isinstance(state["workflow_history"], list)
        assert isinstance(state["errors_active"], list)

    def test_schema_no_missing_fields_in_practice(self, mock_baseline_dir, tmp_path):
        """
        Test 4: Real execution populates schema-defined fields

        Given: Full workflow execution
        When: Graph completes
        Then: All expected fields are populated
        """
        from unittest.mock import patch
        from src.main import run_agent

        config = AMReXAgentConfig(output_dir=tmp_path)

        # Run minimal workflow
        with patch("src.nodes.architect_node.ArchitectService") as MockArch, \
             patch("src.nodes.reviewer_node.ReviewerOrchestrator") as MockRev, \
             patch("src.services.run_superfacility.SuperfacilityRunner.submit") as MockSubmit, \
             patch("src.nodes.analysis_node.AnalysisService") as MockAnalysis:

            MockArch.return_value.create_plan_rag.return_value = {
                "selected_case": "Test",
                "modifications": []
            }
            MockRev.return_value.review_plan.return_value = {
                "approved": True,
                "errors": []
            }
            MockRev.return_value.estimate_resources.return_value = {
                "memory_gb": 1.0
            }
            MockSubmit.return_value = {"job_id": "test"}
            MockAnalysis.return_value.analyze_simulation.return_value = {
                "status": "success"
            }

            final_state = run_agent("Test", config)

        # Verify populated
        assert "prompt" in final_state
        assert "config" in final_state
        assert "workflow_history" in final_state
        assert len(final_state["workflow_history"]) > 0
