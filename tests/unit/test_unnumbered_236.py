"""Session 130 tests for UNNUMBERED-236 error taxonomy normalization."""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from src.services.rules.base import RuleViolation

reviewer_node_module = importlib.import_module("src.nodes.reviewer_node")


class TestErrorTaxonomyNormalization:
    """BDD coverage for normalized reviewer terminal taxonomy payloads."""

    def test_review_validation_terminal_uses_normalized_taxonomy_contract(self, monkeypatch, mock_config):
        """
        GIVEN: Reviewer validation rejects while retry_count is already at max_retries
        WHEN: reviewer_node emits a terminal response
        THEN: final_error_taxonomy is normalized and mirrored into workflow history
        """
        mock_config.preconfirm_gate = False
        mock_config.preconfirm_gate_auto_approve = False
        mock_config.baseline_switch_after_retries = 3
        mock_config.retry_guidance_use_llm = False

        class FakeOrchestrator:
            def __init__(self, _config):
                pass

            def validate_plan(self, _plan):
                violation = RuleViolation("SchemaExistence", "error", "Parameter 'x.bad' not found.")
                return type(
                    "ValidationResult",
                    (),
                    {
                        "mode": "retry",
                        "violations": [violation],
                        "summary": "invalid",
                        "available_schema_params": [],
                    },
                )

        monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)

        state = {
            "config": mock_config,
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "PeleC/Exec/RegTests/PMF",
                        "modifications": [("amr.n_cell", "64 64 64")],
                        "baseline": {"code_name": "PeleC", "local_path": "cases/PMF"},
                    },
                }
            ],
            "iteration": 2,
            "retry_count": 3,
            "max_retries": 3,
            "errors_active": [],
            "errors_found": [],
            "errors_fixed": [],
        }

        updates = reviewer_node_module.reviewer_node(state)
        taxonomy = updates["final_error_taxonomy"]

        assert updates["mode"] == "terminal"
        assert updates["reviewer_failure_category"] == "review_validation_max_retries"
        assert taxonomy["version"] == "v1"
        assert taxonomy["stage"] == "reviewer"
        assert taxonomy["type"] == "retry_exhausted"
        assert taxonomy["category"] == "review_validation_max_retries"
        assert taxonomy["reason_code"] == "max_retries_exceeded_review_validation"
        assert taxonomy["reason"] == taxonomy["reason_code"]
        assert taxonomy["retry_count"] == 3
        assert taxonomy["max_retries"] == 3
        assert taxonomy["unresolved_parameters"] == []
        assert updates["workflow_history"][-1]["details"]["final_error_taxonomy"] == taxonomy

    def test_parameter_resolution_terminal_uses_same_normalized_taxonomy_contract(self, mock_config):
        """
        GIVEN: Input writer reports unresolved parameters and retries are exhausted
        WHEN: reviewer_node returns terminal
        THEN: taxonomy shape matches the same normalized contract with unresolved parameters
        """
        mock_config.preconfirm_gate = False
        mock_config.preconfirm_gate_auto_approve = False

        state = {
            "config": mock_config,
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "PeleC/Exec/RegTests/PMF",
                        "modifications": [("amr.n_cell", "64 64 64")],
                        "baseline": {"code_name": "PeleC", "local_path": "cases/PMF"},
                    },
                },
                {
                    "node": "input_writer",
                    "details": {
                        "requires_parameter_resolution": True,
                        "unresolved_parameters": [("pelec.bad_param", "1")],
                        "resolution_guidance": "Remap to a schema key.",
                        "available_schema_params": ["pelec.cfl"],
                        "suggested_params": {"pelec.bad_param": "pelec.cfl"},
                    },
                },
            ],
            "iteration": 3,
            "retry_count": 3,
            "max_retries": 3,
        }

        updates = reviewer_node_module.reviewer_node(state)
        taxonomy = updates["final_error_taxonomy"]

        assert updates["mode"] == "terminal"
        assert updates["reviewer_failure_category"] == "parameter_resolution_max_retries"
        assert taxonomy["version"] == "v1"
        assert taxonomy["stage"] == "reviewer"
        assert taxonomy["type"] == "retry_exhausted"
        assert taxonomy["category"] == "parameter_resolution_max_retries"
        assert taxonomy["reason_code"] == "max_retries_exceeded_parameter_resolution"
        assert taxonomy["reason"] == taxonomy["reason_code"]
        assert taxonomy["retry_count"] == 3
        assert taxonomy["max_retries"] == 3
        assert taxonomy["unresolved_parameters"] == ["pelec.bad_param"]
        assert updates["workflow_history"][-1]["details"]["final_error_taxonomy"] == taxonomy


def test_normalize_taxonomy_backfills_defaults() -> None:
    taxonomy = reviewer_node_module._normalize_error_taxonomy(  # pylint: disable=protected-access
        {
            "category": "custom",
            "reason": "custom_reason",
            "retry_count": "2",
            "max_retries": "5",
            "unresolved_parameters": "not-a-list",
        }
    )
    assert taxonomy["version"] == "v1"
    assert taxonomy["stage"] == "reviewer"
    assert taxonomy["type"] == "retry_exhausted"
    assert taxonomy["category"] == "custom"
    assert taxonomy["reason_code"] == "custom_reason"
    assert taxonomy["retry_count"] == 2
    assert taxonomy["max_retries"] == 5
    assert taxonomy["unresolved_parameters"] == []


def test_get_architect_plan_fallback_paths() -> None:
    from_history = reviewer_node_module.get_architect_plan(
        {"workflow_history": [{"node": "architect", "details": {"selected_case": "A"}}]}
    )
    assert from_history == {"selected_case": "A"}

    from_state = reviewer_node_module.get_architect_plan(
        {"workflow_history": [], "plan": {"selected_case": "B"}}
    )
    assert from_state == {"selected_case": "B"}

    assert reviewer_node_module.get_architect_plan({"workflow_history": []}) is None


def test_load_baseline_inputs_content_paths(monkeypatch, tmp_path) -> None:
    direct = reviewer_node_module._load_baseline_inputs_content(  # pylint: disable=protected-access
        {"baseline": {"metadata": {"inputs_content": {"amr": {"n_cell": "64"}}}}}
    )
    assert direct == {"amr": {"n_cell": "64"}}

    missing_solver = reviewer_node_module._load_baseline_inputs_content(  # pylint: disable=protected-access
        {"baseline": {"metadata": {"local_path": str(tmp_path)}}}
    )
    assert missing_solver == {}

    class FakeSolverConfig:
        code_name = "PeleC"

        def extract_metadata(self, _local_path: Path, repo_root=None):
            assert repo_root == Path("/tmp/repo")
            return {"inputs_content": {"pelec": {"cfl": "0.7"}}}

    monkeypatch.setattr(
        "database.configs.discover_code_configs",
        lambda: [FakeSolverConfig()],
    )
    discovered = reviewer_node_module._load_baseline_inputs_content(  # pylint: disable=protected-access
        {
            "baseline": {
                "code_name": "PeleC",
                "metadata": {"local_path": str(tmp_path), "repo_path": "/tmp/repo"},
            }
        }
    )
    assert discovered == {"pelec": {"cfl": "0.7"}}


def test_reviewer_node_cancel_and_compilation_terminal_paths(monkeypatch, mock_config) -> None:
    mock_config.preconfirm_gate = True
    mock_config.preconfirm_gate_auto_approve = False

    monkeypatch.setattr(
        reviewer_node_module,
        "run_preconfirm_gate",
        lambda **_kwargs: {"action": "cancel", "history_entry": {"node": "preconfirm"}},
    )
    canceled = reviewer_node_module.reviewer_node(
        {
            "config": mock_config,
            "workflow_history": [],
            "iteration": 1,
        }
    )
    assert canceled["mode"] == "terminal"
    assert "User canceled" in canceled["error"]
    assert canceled["workflow_history"][-1]["iteration"] == 1

    monkeypatch.setattr(
        reviewer_node_module,
        "run_preconfirm_gate",
        lambda **_kwargs: {"action": "proceed", "history_entry": None},
    )
    mock_config.preconfirm_gate = False
    compiled = reviewer_node_module.reviewer_node(
        {
            "config": mock_config,
            "workflow_history": [],
            "compilation_failed": True,
            "retry_count": 1,
            "max_retries": 3,
        }
    )
    assert compiled["mode"] == "terminal"
    assert compiled["reviewer_failure_category"] == "compilation_failed"
    assert compiled["final_error_taxonomy"]["reason_code"] == "compilation_failed"


def test_reviewer_node_schema_missing_terminal(monkeypatch, mock_config, tmp_path) -> None:
    mock_config.preconfirm_gate = False
    mock_config.preconfirm_gate_auto_approve = False
    mock_config.retry_guidance_use_llm = False
    mock_config.repositories = {"PeleC": tmp_path / "PeleC"}

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan):
            return SimpleNamespace(
                mode="retry",
                violations=[RuleViolation("SchemaMissing", "error", "schema absent")],
                summary="missing schema",
                available_schema_params=[],
            )

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    updates = reviewer_node_module.reviewer_node(
        {
            "config": mock_config,
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "PeleC/Test",
                        "modifications": [],
                        "baseline": {"code_name": "PeleC", "local_path": "cases/test"},
                    },
                }
            ],
            "iteration": 0,
            "retry_count": 0,
            "max_retries": 3,
            "errors_active": [],
            "errors_found": [],
            "errors_fixed": [],
        }
    )
    assert updates["mode"] == "terminal"
    assert "Schema missing for PeleC" in updates["errors_active"][-1]


def test_reviewer_node_schema_resolution_stalled_terminal(monkeypatch, mock_config, tmp_path) -> None:
    mock_config.preconfirm_gate = False
    mock_config.preconfirm_gate_auto_approve = False
    mock_config.retry_guidance_use_llm = False
    mock_config.amrex_agent_root = tmp_path
    mock_config.repositories = {"PeleC": tmp_path / "PeleC"}

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan):
            return SimpleNamespace(
                mode="retry",
                violations=[RuleViolation("SchemaExistence", "error", "Parameter 'pelec.bad' not found.", parameter="pelec.bad")],
                summary="schema unknown",
                available_schema_params=[],
            )

    class FakeSolverConfig:
        code_name = "PeleC"

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    monkeypatch.setattr("database.configs.discover_code_configs", lambda: [FakeSolverConfig()])
    monkeypatch.setattr(
        "src.services.config_model_factory.ConfigModelFactory.resolve_schema_path",
        lambda *_args, **_kwargs: tmp_path / "schema.json",
    )
    monkeypatch.setattr(
        "src.services.config_model_factory.ConfigModelFactory.build_parameter_resolution_feedback",
        lambda **_kwargs: {
            "unresolved_parameters": [("pelec.bad", "1")],
            "resolution_guidance": "Remap to existing field",
            "available_schema_params": ["pelec.cfl"],
            "suggested_params": {"pelec.bad": "pelec.cfl"},
            "remap_mapping": {"pelec.bad": "pelec.bad"},
        },
    )

    state = {
        "config": mock_config,
        "workflow_history": [
            {
                "node": "architect",
                "details": {
                    "selected_case": "PeleC/Test",
                    "modifications": [("pelec.bad", "1")],
                    "baseline": {"code_name": "PeleC", "local_path": str(tmp_path / "case")},
                    "build_config": {},
                },
            },
            {
                "node": "reviewer",
                "action": "parameter_resolution_retry",
                "details": {
                    "reason": "schema_resolution",
                    "unresolved_parameters": [("pelec.bad", "1")],
                },
            },
        ],
        "retry_count": 2,
        "max_retries": 3,
        "iteration": 2,
        "errors_active": [],
        "errors_found": [],
        "errors_fixed": [],
    }
    updates = reviewer_node_module.reviewer_node(state)
    assert updates["mode"] == "terminal"
    assert updates["reviewer_failure_category"] == "schema_resolution_stalled"
    assert updates["final_error_taxonomy"]["unresolved_parameters"] == ["pelec.bad"]


def test_reviewer_node_llm_retry_guidance_branch(monkeypatch, mock_config) -> None:
    mock_config.preconfirm_gate = False
    mock_config.preconfirm_gate_auto_approve = False
    mock_config.retry_guidance_use_llm = True
    mock_config.llm_model = "test-model"

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan):
            return SimpleNamespace(
                mode="retry",
                violations=[
                    RuleViolation(
                        "SchemaExistence",
                        "error",
                        "Parameter 'amr.n_cell' not found.",
                        parameter="amr.n_cell",
                    )
                ],
                summary="ok",
                available_schema_params=[],
            )

    class FakePromptConfig:
        @staticmethod
        def get_prompt_templates():
            return {
                "misc": {
                    "retry_guidance": (
                        "solver={solver} baseline={baseline_case} inputs={inputs_file} "
                        "current={errors_current} found={errors_all_found} fixed={errors_all_fixed} analysis={analysis_issues}"
                    )
                }
            }

    @contextmanager
    def fake_metrics_context(*_args, **_kwargs):
        yield

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    monkeypatch.setattr("src.config.get_llm_client", lambda _config: object())
    monkeypatch.setattr("database.configs.get_config_for_path", lambda _path: FakePromptConfig)
    monkeypatch.setattr("src.utils.metrics.metrics_context", fake_metrics_context)
    monkeypatch.setattr(
        "src.utils.llm_calls.call_llm",
        lambda *_args, **_kwargs: SimpleNamespace(
            inputs_base_action="switch",
            baseline_base_action="keep",
            rationale="LLM selected switch for inputs",
        ),
    )

    updates = reviewer_node_module.reviewer_node(
        {
            "config": mock_config,
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "PeleC/Test",
                        "modifications": [("amr.n_cell", "64 64 64")],
                        "baseline": {
                            "code_name": "PeleC",
                            "local_path": "cases/test",
                            "inputs_content": {"amr": {"n_cell": "32 32 32"}},
                        },
                    },
                }
            ],
            "iteration": 0,
            "retry_count": 0,
            "max_retries": 3,
            "errors_active": [],
            "errors_found": [],
            "errors_fixed": [],
        }
    )
    assert updates["mode"] == "proceed"
    assert updates["retry_guidance"]["inputs_base_action"] == "switch"


def test_parameter_resolution_retry_path(monkeypatch, mock_config) -> None:
    mock_config.preconfirm_gate = False
    mock_config.preconfirm_gate_auto_approve = False

    monkeypatch.setattr(
        reviewer_node_module,
        "run_preconfirm_gate",
        lambda **_kwargs: {"action": "proceed", "history_entry": {"node": "preconfirm", "details": {}}},
    )
    updates = reviewer_node_module.reviewer_node(
        {
            "config": mock_config,
            "workflow_history": [
                {
                    "node": "input_writer",
                    "details": {
                        "requires_parameter_resolution": True,
                        "unresolved_parameters": [("pelec.bad_param", "1")],
                        "resolution_guidance": "Try pelec.cfl",
                        "available_schema_params": ["pelec.cfl"],
                        "suggested_params": {"pelec.bad_param": "pelec.cfl"},
                    },
                }
            ],
            "iteration": 1,
            "retry_count": 0,
            "max_retries": 3,
        }
    )
    assert updates["mode"] == "retry"
    assert updates["retry_count"] == 1
    assert updates["parameter_resolution_feedback"]["suggested_params"]["pelec.bad_param"] == "pelec.cfl"


def test_schema_resolution_feedback_retry_path(monkeypatch, mock_config, tmp_path) -> None:
    mock_config.preconfirm_gate = False
    mock_config.preconfirm_gate_auto_approve = False
    mock_config.retry_guidance_use_llm = False
    mock_config.amrex_agent_root = tmp_path
    mock_config.repositories = {"PeleC": tmp_path / "PeleC"}
    mock_config.baseline_override = None

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan):
            return SimpleNamespace(
                mode="retry",
                violations=[RuleViolation("SchemaExistence", "error", "Parameter 'pelec.bad' not found.", parameter="pelec.bad")],
                summary="schema unknown",
                available_schema_params=[],
            )

    class FakeSolverConfig:
        code_name = "PeleC"

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    monkeypatch.setattr("database.configs.discover_code_configs", lambda: [FakeSolverConfig()])
    monkeypatch.setattr(
        "src.services.config_model_factory.ConfigModelFactory.resolve_schema_path",
        lambda *_args, **_kwargs: tmp_path / "schema.json",
    )
    monkeypatch.setattr(
        "src.services.config_model_factory.ConfigModelFactory.build_parameter_resolution_feedback",
        lambda **_kwargs: {
            "unresolved_parameters": [("pelec.bad", "1")],
            "resolution_guidance": "Remap to existing field",
            "available_schema_params": ["pelec.cfl"],
            "suggested_params": {"pelec.bad": "pelec.cfl"},
            "remap_mapping": {"pelec.bad": "pelec.bad"},
        },
    )

    updates = reviewer_node_module.reviewer_node(
        {
            "config": mock_config,
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "PeleC/Test",
                        "modifications": [("pelec.bad", "1")],
                        "baseline": {"code_name": "PeleC", "local_path": str(tmp_path / "case")},
                        "build_config": {},
                    },
                }
            ],
            "retry_count": 1,
            "max_retries": 3,
            "iteration": 1,
            "errors_active": [],
            "errors_found": [],
            "errors_fixed": [],
        }
    )
    assert updates["mode"] == "retry"
    assert updates["retry_count"] == 2
    assert updates["parameter_resolution_feedback"]["remap_success_count"] == 0


def test_reviewer_node_llm_retry_guidance_json_fallback(monkeypatch, mock_config) -> None:
    mock_config.preconfirm_gate = False
    mock_config.preconfirm_gate_auto_approve = False
    mock_config.retry_guidance_use_llm = True
    mock_config.llm_model = "test-model"

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan):
            return SimpleNamespace(
                mode="retry",
                violations=[
                    RuleViolation(
                        "SchemaExistence",
                        "error",
                        "Parameter 'amr.n_cell' not found.",
                        parameter="amr.n_cell",
                    )
                ],
                summary="ok",
                available_schema_params=[],
            )

    class FakePromptConfig:
        @staticmethod
        def get_prompt_templates():
            return {"misc": {"retry_guidance": "solver={solver} baseline={baseline_case} inputs={inputs_file} current={errors_current} found={errors_all_found} fixed={errors_all_fixed} analysis={analysis_issues}"}}

    @contextmanager
    def fake_metrics_context(*_args, **_kwargs):
        yield

    llm_result = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"inputs_base_action":"switch","baseline_base_action":"switch","rationale":"json rationale"}'
                )
            )
        ]
    )
    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    monkeypatch.setattr("src.config.get_llm_client", lambda _config: object())
    monkeypatch.setattr("database.configs.get_config_for_path", lambda _path: FakePromptConfig)
    monkeypatch.setattr("src.utils.metrics.metrics_context", fake_metrics_context)
    monkeypatch.setattr("src.utils.llm_calls.call_llm", lambda *_args, **_kwargs: llm_result)

    updates = reviewer_node_module.reviewer_node(
        {
            "config": mock_config,
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "PeleC/Test",
                        "modifications": [("amr.n_cell", "64 64 64")],
                        "baseline": {
                            "code_name": "PeleC",
                            "local_path": "cases/test",
                            "inputs_content": {"amr": {"n_cell": "32 32 32"}},
                        },
                    },
                }
            ],
            "iteration": 0,
            "retry_count": 0,
            "max_retries": 3,
            "errors_active": [],
            "errors_found": [],
            "errors_fixed": [],
        }
    )
    assert updates["retry_guidance"]["baseline_base_action"] == "switch"


def test_retry_guidance_switches_for_unknown_and_schema_missing(monkeypatch, mock_config) -> None:
    mock_config.preconfirm_gate = False
    mock_config.preconfirm_gate_auto_approve = False
    mock_config.retry_guidance_use_llm = False
    mock_config.baseline_override = None

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan):
            return SimpleNamespace(
                mode="retry",
                violations=[
                    RuleViolation("SchemaExistence", "error", "Parameter 'a.x' not found.", parameter="a.x"),
                    RuleViolation("SchemaExistence", "error", "Parameter 'b.y' not found.", parameter="b.y"),
                    RuleViolation("SchemaExistence", "error", "Parameter 'c.z' not found.", parameter="c.z"),
                    RuleViolation("SchemaMissing", "error", "schema missing"),
                ],
                summary="invalid",
                available_schema_params=[],
            )

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    updates = reviewer_node_module.reviewer_node(
        {
            "config": mock_config,
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "PeleC/Test",
                        "modifications": [("a.x", "1"), ("b.y", "2"), ("c.z", "3")],
                        "baseline": {},
                    },
                }
            ],
            "iteration": 2,
            "retry_count": 0,
            "max_retries": 3,
            "errors_active": ["stale-error"],
            "errors_found": [],
            "errors_fixed": [],
        }
    )
    assert updates["mode"] == "terminal"
    assert updates["retry_guidance"]["inputs_base_action"] == "switch"
    assert updates["retry_guidance"]["baseline_reason"] == "schema_missing_build_required"
