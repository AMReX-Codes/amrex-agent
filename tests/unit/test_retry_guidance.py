from datetime import datetime as real_datetime

import pytest

import importlib

reviewer_node_module = importlib.import_module("src.nodes.reviewer_node")
analysis_node_module = importlib.import_module("src.nodes.analysis_node")


class DummyConfig:
    def __init__(self, output_dir="."):
        self.output_dir = output_dir
        self.retry_guidance_use_llm = False
        self.llm_model = None
        self.repositories = {}
        self.amrex_agent_root = None
        self.baseline_switch_after_retries = 3


class FixedDateTime:
    @classmethod
    def now(cls):
        return real_datetime(2025, 1, 1, 12, 0, 0)

    @classmethod
    def utcnow(cls):
        return real_datetime(2025, 1, 1, 12, 0, 0)


def _base_state():
    return {
        "config": DummyConfig(),
        "workflow_history": [
            {
                "node": "architect",
                "details": {
                    "selected_case": "PeleC/Exec/RegTests/PMF",
                    "modifications": [("amr.n_cell", "64 64 64")],
                    "baseline": {"local_path": "cases/PMF", "code_name": "PeleC"},
                    "reasoning": "baseline test",
                },
            }
        ],
        "review": {},
        "errors_found": [],
        "errors_fixed": [],
        "errors_active": [],
        "retry_count": 1,
    }


def _fake_validation_result(violations, mode="retry"):
    return type(
        "ValidationResult",
        (),
        {
            "violations": violations,
            "mode": mode,
            "summary": "summary",
            "available_schema_params": [],
        },
    )


class DummyViolation:
    def __init__(self, rule_name, severity="error", message="", parameter=None, suggested_fix=None):
        self.rule_name = rule_name
        self.severity = severity
        self.message = message
        self.parameter = parameter
        self.suggested_fix = suggested_fix


def test_retry_guidance_switch_inputs_on_persistent_unknowns(monkeypatch):
    violations = [
        DummyViolation(
            "SchemaExistence",
            message="Parameter 'pelec.bad_param' not found in PeleC source code schema.",
            parameter=None,
        ),
        DummyViolation(
            "SchemaExistence",
            message="Parameter 'amr.bad2' not found in PeleC source code schema.",
            parameter=None,
        ),
    ]

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan, retry_count=0):
            return _fake_validation_result(violations)

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(reviewer_node_module, "datetime", FixedDateTime)

    state = _base_state()
    state["errors_found"] = [
        "Parameter 'pelec.bad_param' not found in source code schema.",
        "Parameter 'amr.bad2' not found in source code schema.",
    ]
    state["errors_fixed"] = []

    updates = reviewer_node_module.reviewer_node(state)
    guidance = updates.get("retry_guidance", {})

    assert guidance.get("inputs_base_action") == "switch"
    assert "persistent_unknown" in guidance.get("inputs_reason", "")


def test_retry_guidance_switch_baseline_on_schema_missing(monkeypatch):
    violations = [
        DummyViolation(
            "SchemaMissing",
            severity="critical",
            message="Schema not found for PeleC.",
        )
    ]

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan, retry_count=0):
            return _fake_validation_result(violations, mode="fail")

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(reviewer_node_module, "datetime", FixedDateTime)

    state = _base_state()
    updates = reviewer_node_module.reviewer_node(state)
    guidance = updates.get("retry_guidance", {})

    assert updates["mode"] == "terminal"
    assert guidance.get("baseline_base_action") == "keep"
    assert guidance.get("baseline_reason") == "schema_missing_build_required"


def test_analysis_retry_guidance_from_issues(monkeypatch):
    monkeypatch.setattr(analysis_node_module, "datetime", FixedDateTime)

    class FakeAnalysisService:
        def __init__(self, _config):
            pass

        def analyze_simulation(self, run_dir, include_visual=False):
            return {
                "status": "failed",
                "issues": ["Input file parse error: unknown key", "Baseline case missing file"],
                "warnings": [],
                "metrics": {},
            }

    monkeypatch.setattr(analysis_node_module, "AnalysisService", FakeAnalysisService)

    state = {
        "config": DummyConfig(),
        "workflow_history": [],
        "run_directory": "fake_run",
    }
    updates = analysis_node_module.analysis_node(state)
    guidance = updates.get("retry_guidance", {})

    assert guidance.get("inputs_base_action") == "switch"
    assert guidance.get("baseline_base_action") == "switch"
