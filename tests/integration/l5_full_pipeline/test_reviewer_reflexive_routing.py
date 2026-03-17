"""Integration coverage for reviewer reflexive guidance and clarification routing."""

import importlib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.config import AMReXAgentConfig
from src.main import run_agent
from src.services.architect import ArchitectService
from src.services.plan import SimulationPlan
from src.services.rules.base import RuleViolation
from src.services.validation_result import ValidationResult


class DummyEmbeddingService:
    embeddings = None


class DummyInputWriterService:
    def __init__(self, _config):
        self.cases_svc = None

    def apply_plan(
        self,
        selected_case,
        modifications,
        baseline,
        reasoning,
        output_dir,
        requested_plot_vars=None,
        **_kwargs,
    ):
        run_dir = Path(output_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        inputs_path = run_dir / "inputs"
        inputs_path.write_text("# inputs", encoding="utf-8")
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
        return {"run_dir": output_dir, "executable": "AMReX.ex"}

    def submit(self, run_directory, nodes=None, run_mode=None, dry_run=None, case_dir=None):
        return {
            "job_id": "integration_test",
            "method": "sbatch",
            "script_path": str(Path(run_directory) / "submit.sh"),
            "job_status": "completed",
        }


def _plan(selected_case: str, selected_solver: str) -> SimulationPlan:
    return SimulationPlan(
        selected_solver=selected_solver,
        selected_case=selected_case,
        modifications=[("amr.n_cell", "64 64 64")],
        reasoning="integration test plan",
        baseline={
            "code_name": selected_solver,
            "local_path": selected_case,
            "inputs_file": "inputs",
        },
    )


def _validation_result(
    mode: str,
    *,
    errors: list[str] | None = None,
    required_solver: str | None = None,
    forbidden_path_patterns: list[str] | None = None,
    preferred_path_patterns: list[str] | None = None,
    excluded_cases: list[str] | None = None,
    schema_escalation_required: bool = False,
    replan_reason_codes: list[str] | None = None,
) -> ValidationResult:
    violations = [
        RuleViolation(rule_name="TestRule", severity="error", message=msg)
        for msg in (errors or [])
    ]
    return ValidationResult(
        mode=mode,
        violations=violations,
        summary="integration validation result",
        available_schema_params=[],
        required_solver=required_solver,
        forbidden_path_patterns=forbidden_path_patterns or [],
        preferred_path_patterns=preferred_path_patterns or [],
        excluded_cases=excluded_cases or [],
        schema_escalation_required=schema_escalation_required,
        replan_reason_codes=replan_reason_codes or [],
    )


def _base_config(tmp_path: Path) -> AMReXAgentConfig:
    config = AMReXAgentConfig(output_dir=tmp_path)
    config.environment = "perlmutter"
    config.repositories = {
        "ERF": tmp_path / "ERF",
        "PeleC": tmp_path / "PeleC",
    }
    (tmp_path / "ERF").mkdir(exist_ok=True)
    (tmp_path / "PeleC").mkdir(exist_ok=True)
    return config


@pytest.mark.integration_full
def test_reviewer_guidance_is_forwarded_to_architect_retry(tmp_path):
    """Reviewer guidance should constrain architect retry calls."""
    config = _base_config(tmp_path)

    with (
        patch("src.services.embedding_service_factory.get_embedding_service", return_value=DummyEmbeddingService()),
        patch("src.nodes.architect_node.ArchitectService") as mock_arch_cls,
        patch("src.nodes.reviewer_node.ReviewerOrchestrator") as mock_rev_cls,
        patch("src.services.cases.AMReXCasesService", return_value=object()),
        patch("src.nodes.input_writer_node.InputWriterService", DummyInputWriterService),
        patch("src.nodes.runner_node.SuperfacilityRunner", DummyRunner),
        patch("src.nodes.analysis_node.AnalysisService") as mock_analysis_cls,
    ):
        mock_arch_cls.return_value.execute_planning.side_effect = [
            _plan("Exec/DevTests/BadCase", "PeleC"),
            _plan("Exec/CanonicalFlows/SuperCell_3D", "ERF"),
        ]
        mock_rev_cls.return_value.validate_plan.side_effect = [
            _validation_result(
                "retry",
                errors=["solver mismatch"],
                required_solver="ERF",
                forbidden_path_patterns=["Exec/DevTests/"],
                preferred_path_patterns=["Exec/CanonicalFlows/"],
                excluded_cases=["Exec/DevTests/BadCase"],
                schema_escalation_required=True,
                replan_reason_codes=["solver_mismatch"],
            ),
            _validation_result("proceed"),
        ]
        mock_analysis_cls.return_value.analyze_simulation.return_value = {"status": "success"}

        final_state = run_agent("integration: reviewer guidance to architect", config)

    assert final_state["mode"] == "proceed"
    assert mock_arch_cls.return_value.execute_planning.call_count >= 2

    second_call = mock_arch_cls.return_value.execute_planning.call_args_list[1].kwargs
    assert second_call["reviewer_guidance"]["required_solver"] == "ERF"
    assert second_call["reviewer_guidance"]["schema_escalation_required"] is True
    assert "Exec/DevTests/BadCase" in second_call["excluded_cases"]
    assert second_call["parameter_resolution_feedback"]["schema_escalation_required"] is True


@pytest.mark.integration_full
def test_clarification_routes_only_on_intent_missing(tmp_path):
    """Clarification node should be visited only for intent_missing taxonomy."""
    config = _base_config(tmp_path)
    config.enable_clarification_subgraph = True
    config.clarification_route_on_intent_missing_only = True

    # Scenario A: intent_missing -> clarification should run
    with (
        patch("src.services.embedding_service_factory.get_embedding_service", return_value=DummyEmbeddingService()),
        patch("src.nodes.architect_node.ArchitectService") as mock_arch_cls,
        patch("src.nodes.reviewer_node.ReviewerOrchestrator") as mock_rev_cls,
        patch("src.services.cases.AMReXCasesService", return_value=object()),
        patch("src.nodes.input_writer_node.InputWriterService", DummyInputWriterService),
        patch("src.nodes.runner_node.SuperfacilityRunner", DummyRunner),
        patch("src.nodes.analysis_node.AnalysisService") as mock_analysis_cls,
        patch("src.main.clarification_node") as clarification_mock,
    ):
        mock_arch_cls.return_value.execute_planning.return_value = _plan(
            "Exec/CanonicalFlows/SquallLine_2D",
            "ERF",
        )
        mock_rev_cls.return_value.validate_plan.return_value = _validation_result(
            "retry",
            errors=["intent unclear"],
            replan_reason_codes=["intent_missing"],
        )
        clarification_mock.return_value = {
            "clarification_needed": False,
            "clarification_questions": [],
        }
        mock_analysis_cls.return_value.analyze_simulation.return_value = {"status": "success"}

        run_agent("integration: intent missing routes to clarification", config)

    assert clarification_mock.call_count == 1

    # Scenario B: non-intent retry reason -> clarification should not run
    with (
        patch("src.services.embedding_service_factory.get_embedding_service", return_value=DummyEmbeddingService()),
        patch("src.nodes.architect_node.ArchitectService") as mock_arch_cls,
        patch("src.nodes.reviewer_node.ReviewerOrchestrator") as mock_rev_cls,
        patch("src.services.cases.AMReXCasesService", return_value=object()),
        patch("src.nodes.input_writer_node.InputWriterService", DummyInputWriterService),
        patch("src.nodes.runner_node.SuperfacilityRunner", DummyRunner),
        patch("src.nodes.analysis_node.AnalysisService") as mock_analysis_cls,
        patch("src.main.clarification_node") as clarification_mock,
    ):
        mock_arch_cls.return_value.execute_planning.side_effect = [
            _plan("Exec/DevTests/BadCase", "PeleC"),
            _plan("Exec/CanonicalFlows/Channel_DNS", "ERF"),
        ]
        mock_rev_cls.return_value.validate_plan.side_effect = [
            _validation_result(
                "retry",
                errors=["solver mismatch"],
                replan_reason_codes=["solver_mismatch"],
            ),
            _validation_result("proceed"),
        ]
        mock_analysis_cls.return_value.analyze_simulation.return_value = {"status": "success"}

        run_agent("integration: non-intent retry stays in reflexive loop", config)

    assert clarification_mock.call_count == 0


@pytest.mark.integration_full
def test_post_execution_analysis_failure_routes_back_to_architect_before_new_input_writer(tmp_path):
    """Failed analysis should trigger post-execution reviewer retry and return to architect before any new input writer pass."""
    config = _base_config(tmp_path)

    with (
        patch("src.services.embedding_service_factory.get_embedding_service", return_value=DummyEmbeddingService()),
        patch("src.nodes.architect_node.ArchitectService") as mock_arch_cls,
        patch("src.nodes.reviewer_node.ReviewerOrchestrator") as mock_rev_cls,
        patch("src.services.cases.AMReXCasesService", return_value=object()),
        patch("src.nodes.input_writer_node.InputWriterService", DummyInputWriterService),
        patch("src.nodes.runner_node.SuperfacilityRunner", DummyRunner),
        patch("src.nodes.analysis_node.AnalysisService") as mock_analysis_cls,
    ):
        mock_arch_cls.return_value.execute_planning.side_effect = [
            _plan("Exec/CanonicalFlows/SquallLine_2D", "ERF"),
            _plan("Exec/CanonicalFlows/Channel_DNS", "ERF"),
        ]
        mock_rev_cls.return_value.validate_plan.side_effect = [
            _validation_result("proceed"),
            _validation_result("proceed"),  # post-exec pass should still be forced to retry by context
            _validation_result("proceed"),
        ]
        mock_analysis_cls.return_value.analyze_simulation.side_effect = [
            {"status": "failed", "issues": ["runtime crash"]},
            {"status": "success"},
        ]

        final_state = run_agent("integration: post-execution failure returns to architect", config)

    assert final_state["mode"] == "proceed"
    history = final_state["workflow_history"]

    analysis_failed_idx = next(
        i for i, entry in enumerate(history)
        if entry.get("node") == "analysis" and entry.get("action") == "analysis_failed"
    )
    reviewer_post_idx = next(
        i for i, entry in enumerate(history[analysis_failed_idx + 1 :], start=analysis_failed_idx + 1)
        if entry.get("node") == "reviewer"
        and entry.get("details", {}).get("review_context") == "post_execution"
    )
    architect_retry_idx = next(
        i for i, entry in enumerate(history[reviewer_post_idx + 1 :], start=reviewer_post_idx + 1)
        if entry.get("node") == "architect"
    )

    no_input_writer_between = all(
        entry.get("node") != "input_writer"
        for entry in history[reviewer_post_idx + 1 : architect_retry_idx]
    )
    assert no_input_writer_between


@pytest.mark.integration_full
def test_post_execution_structured_feasibility_guidance_is_forwarded_to_architect(tmp_path):
    """Post-exec reviewer feasibility fields must be present in reviewer_guidance forwarded to architect."""
    config = _base_config(tmp_path)
    config.retry_guidance_use_llm = False
    config.llm_model = "test-model"

    with (
        patch("src.services.embedding_service_factory.get_embedding_service", return_value=DummyEmbeddingService()),
        patch("src.nodes.architect_node.ArchitectService") as mock_arch_cls,
        patch("src.nodes.reviewer_node.ReviewerOrchestrator") as mock_rev_cls,
        patch("src.services.cases.AMReXCasesService", return_value=object()),
        patch("src.nodes.input_writer_node.InputWriterService", DummyInputWriterService),
        patch("src.nodes.runner_node.SuperfacilityRunner", DummyRunner),
        patch("src.nodes.analysis_node.AnalysisService") as mock_analysis_cls,
        patch("src.config.get_llm_client", return_value=object()),
        patch(
            "src.utils.llm_calls.call_llm",
            return_value=type(
                "FeasibilityResult",
                (),
                {
                    "feasible": False,
                    "intent_consistent": False,
                    "diagnosis": "Execution failed due to infeasible setup",
                    "guidance": {"required_solver": "ERF", "excluded_cases": ["Exec/DevTests/BadCase"]},
                },
            )(),
        ),
    ):
        mock_arch_cls.return_value.execute_planning.side_effect = [
            _plan("Exec/DevTests/BadCase", "ERF"),
            _plan("Exec/CanonicalFlows/Channel_DNS", "ERF"),
        ]
        mock_rev_cls.return_value.validate_plan.side_effect = [
            _validation_result("proceed"),
            _validation_result("proceed"),
            _validation_result("proceed"),
        ]
        mock_analysis_cls.return_value.analyze_simulation.side_effect = [
            {"status": "failed", "issues": ["runtime crash"]},
            {"status": "success"},
        ]

        final_state = run_agent("integration: structured reviewer feasibility guidance forwarding", config)

    assert final_state["mode"] == "proceed"
    assert mock_arch_cls.return_value.execute_planning.call_count >= 2
    second_call = mock_arch_cls.return_value.execute_planning.call_args_list[1].kwargs
    guidance = second_call["reviewer_guidance"]
    assert guidance["feasible"] is False
    assert guidance["intent_consistent"] is False
    assert guidance["diagnosis"] == "Execution failed due to infeasible setup"
    assert isinstance(guidance["guidance"], dict)
    assert guidance["required_solver"] == "ERF"
    assert "Exec/DevTests/BadCase" in guidance["excluded_cases"]


@pytest.mark.integration_full
def test_architect_plan_differs_with_structured_reviewer_guidance(tmp_path, monkeypatch):
    """Architect create_plan should produce observably different output when structured reviewer guidance is present."""
    config = _base_config(tmp_path)
    service = ArchitectService(config, DummyEmbeddingService())

    captured_solvers: list[str | None] = []

    monkeypatch.setattr(service, "_extract_requirements", lambda _prompt: {"solver": "PeleC"})
    monkeypatch.setattr(service, "_gather_knowledge", lambda _prompt, _requirements: {})
    monkeypatch.setattr(service, "_select_baseline", lambda **_kwargs: {"name": "ERF/Exec/ABL"})

    def _fake_plan_modifications(*, requirements, baseline, knowledge):
        captured_solvers.append(requirements.get("solver"))
        return []

    monkeypatch.setattr(service, "_plan_modifications", _fake_plan_modifications)

    no_guidance_plan = service.create_plan("integration reviewer guidance baseline")
    with_guidance_plan = service.create_plan(
        "integration reviewer guidance constrained",
        reviewer_guidance={
            "feasible": False,
            "intent_consistent": False,
            "diagnosis": "infeasible with current solver choice",
            "guidance": {"required_solver": "ERF"},
        },
    )

    assert captured_solvers[0] == "PeleC"
    assert captured_solvers[1] == "ERF"
    assert no_guidance_plan.reasoning != with_guidance_plan.reasoning
    assert "Reviewer feasibility diagnosis: infeasible with current solver choice" in with_guidance_plan.reasoning


@pytest.mark.integration_full
def test_flags_off_regression_keeps_retry_loop_without_clarification(tmp_path):
    """With clarification gating disabled, intent_missing should not route to clarification."""
    config = _base_config(tmp_path)
    config.enable_clarification_subgraph = True
    config.clarification_route_on_intent_missing_only = False
    config.reviewer_reflexive_guidance_enabled = False

    with (
        patch("src.services.embedding_service_factory.get_embedding_service", return_value=DummyEmbeddingService()),
        patch("src.nodes.architect_node.ArchitectService") as mock_arch_cls,
        patch("src.nodes.reviewer_node.ReviewerOrchestrator") as mock_rev_cls,
        patch("src.services.cases.AMReXCasesService", return_value=object()),
        patch("src.nodes.input_writer_node.InputWriterService", DummyInputWriterService),
        patch("src.nodes.runner_node.SuperfacilityRunner", DummyRunner),
        patch("src.nodes.analysis_node.AnalysisService") as mock_analysis_cls,
        patch("src.main.clarification_node") as clarification_mock,
    ):
        mock_arch_cls.return_value.execute_planning.side_effect = [
            _plan("Exec/CanonicalFlows/SquallLine_2D", "ERF"),
            _plan("Exec/CanonicalFlows/Channel_DNS", "ERF"),
        ]
        mock_rev_cls.return_value.validate_plan.side_effect = [
            _validation_result("retry", errors=["intent unclear"], replan_reason_codes=["intent_missing"]),
            _validation_result("proceed"),
        ]
        mock_analysis_cls.return_value.analyze_simulation.return_value = {"status": "success"}

        final_state = run_agent("integration: flags-off clarification regression guard", config)

    assert final_state["mode"] == "proceed"
    assert clarification_mock.call_count == 0


@pytest.mark.integration_full
def test_preexec_retry_exhaustion_routes_to_clarification_when_enabled(tmp_path, monkeypatch):
    """Pre-exec intent/parameter retry exhaustion should route to clarification when enabled."""
    config = _base_config(tmp_path)
    config.enable_clarification_subgraph = True
    config.preexec_route_to_clarification_on_retry_exhausted = True
    config.max_iterations = 0

    with (
        patch("src.services.embedding_service_factory.get_embedding_service", return_value=DummyEmbeddingService()),
        patch("src.nodes.architect_node.ArchitectService") as mock_arch_cls,
        patch("src.nodes.reviewer_node.ReviewerOrchestrator") as mock_rev_cls,
        patch("src.services.cases.AMReXCasesService", return_value=object()),
        patch("src.nodes.input_writer_node.InputWriterService", DummyInputWriterService),
        patch("src.nodes.runner_node.SuperfacilityRunner", DummyRunner),
        patch("src.nodes.analysis_node.AnalysisService") as mock_analysis_cls,
        patch("src.main.clarification_node") as clarification_mock,
    ):
        mock_arch_cls.return_value.execute_planning.return_value = _plan(
            "Exec/CanonicalFlows/SquallLine_2D",
            "ERF",
        )
        mock_rev_cls.return_value.validate_plan.return_value = _validation_result("proceed")
        mock_analysis_cls.return_value.analyze_simulation.return_value = {"status": "success"}
        clarification_mock.return_value = {
            "clarification_needed": False,
            "clarification_questions": [],
        }

        class FakeIntentCoverageAuditService:
            def __init__(self, _config):
                pass

            def audit(self, prompt, plan):
                del prompt, plan
                return {
                    "requires_intent_resolution": True,
                    "unresolved_requests": [("dt", "20")],
                    "resolution_guidance": "Include requested dt",
                    "suggested_modifications": {"dt": "20"},
                    "reason_code": "intent_missing",
                }

        reviewer_module = importlib.import_module("src.nodes.reviewer_node")
        monkeypatch.setattr(
            reviewer_module,
            "IntentCoverageAuditService",
            FakeIntentCoverageAuditService,
        )

        final_state = run_agent(
            "integration: force intent retry exhaustion to clarification",
            config,
        )

    assert clarification_mock.call_count >= 1
    assert final_state["mode"] == "proceed"
