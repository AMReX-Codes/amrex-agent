"""
Unit coverage for ArchitectService._llm_fallback_structured.
"""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.services.architect import ArchitectService
from src.services.plan import SimulationPlan


def test_llm_fallback_structured_returns_plan_dict(tmp_path, monkeypatch):
    config = Mock()
    config.faiss_db_path = tmp_path
    config.llm_model = "test-model"

    architect = ArchitectService(config, Mock())
    architect.llm_client = Mock()

    baseline = {
        "metadata": {
            "solver": "AMReX",
            "inputs_content": {"amr.n_cell": "64 64 64"},
        },
        "score": 0.7,
    }
    baseline_case = "Tests/Amr/Advection_AmrCore"

    plan = SimulationPlan(
        selected_solver="WrongSolver",
        selected_case="WrongCase",
        modifications=[("amr.n_cell", "128 128 128")],
        reasoning="LLM output",
        solver_confidence=0.1,
        baseline_confidence=0.1,
        cbr_confidence=0.9,
    )

    class DummyCompletions:
        def create(self, **kwargs):
            return plan

    class DummyChat:
        completions = DummyCompletions()

    class DummyClient:
        chat = DummyChat()

    instructor_module = SimpleNamespace(from_openai=lambda client: DummyClient())
    monkeypatch.setitem(sys.modules, "instructor", instructor_module)

    result = architect._llm_fallback_structured("prompt", baseline, baseline_case)

    assert result["used_llm"] is True
    assert result["confidence"] == pytest.approx(0.9)
    assert result["modifications"] == [("amr.n_cell", "128 128 128")]

    full_plan = result["_full_plan"]
    assert full_plan.selected_solver == "AMReX"
    assert full_plan.selected_case == baseline_case
    assert full_plan.solver_confidence == pytest.approx(1.0)
    assert full_plan.baseline_confidence == pytest.approx(0.7)


def test_llm_fallback_structured_returns_none_on_error(tmp_path, monkeypatch):
    config = Mock()
    config.faiss_db_path = tmp_path
    config.llm_model = "test-model"

    architect = ArchitectService(config, Mock())
    architect.llm_client = Mock()

    baseline = {
        "metadata": {"solver": "AMReX", "inputs_content": {}},
        "score": 0.5,
    }
    baseline_case = "Tests/Amr/Advection_AmrCore"

    class DummyCompletions:
        def create(self, **kwargs):
            raise ValueError("bad response")

    class DummyChat:
        completions = DummyCompletions()

    class DummyClient:
        chat = DummyChat()

    instructor_module = SimpleNamespace(from_openai=lambda client: DummyClient())
    monkeypatch.setitem(sys.modules, "instructor", instructor_module)

    result = architect._llm_fallback_structured("prompt", baseline, baseline_case)

    assert result is None


def test_create_plan_accepts_reviewer_guidance_kwarg(tmp_path, monkeypatch):
    config = Mock()
    config.faiss_db_path = tmp_path

    architect = ArchitectService(config, Mock())

    monkeypatch.setattr(
        architect,
        "_extract_requirements",
        lambda _prompt: {"solver": "ERF"},
    )
    monkeypatch.setattr(
        architect,
        "_gather_knowledge",
        lambda _prompt, _requirements: {},
    )
    monkeypatch.setattr(
        architect,
        "_select_baseline",
        lambda **_kwargs: {"name": "ERF/Exec/ABL"},
    )
    monkeypatch.setattr(
        architect,
        "_plan_modifications",
        lambda **_kwargs: [],
    )

    plan = architect.create_plan(
        user_prompt="run ERF case",
        reviewer_guidance={"required_solver": "ERF"},
    )

    assert plan is not None


def test_create_plan_uses_structured_reviewer_guidance_required_solver(tmp_path, monkeypatch):
    config = Mock()
    config.faiss_db_path = tmp_path

    architect = ArchitectService(config, Mock())

    captured = {}

    monkeypatch.setattr(
        architect,
        "_extract_requirements",
        lambda _prompt: {"solver": "PeleC"},
    )
    monkeypatch.setattr(
        architect,
        "_gather_knowledge",
        lambda _prompt, _requirements: {},
    )
    monkeypatch.setattr(
        architect,
        "_select_baseline",
        lambda **_kwargs: {"name": "ERF/Exec/ABL"},
    )

    def _fake_plan_modifications(*, requirements, baseline, knowledge):
        captured["solver"] = requirements.get("solver")
        return []

    monkeypatch.setattr(architect, "_plan_modifications", _fake_plan_modifications)

    plan = architect.create_plan(
        user_prompt="run benchmark",
        reviewer_guidance={
            "feasible": False,
            "intent_consistent": False,
            "diagnosis": "solver mismatch from failed run",
            "guidance": {"required_solver": "ERF"},
        },
    )

    assert plan is not None
    assert captured["solver"] == "ERF"
    assert "Reviewer feasibility diagnosis:" in plan.reasoning


def test_create_plan_reasoning_differs_with_structured_reviewer_diagnosis(tmp_path, monkeypatch):
    config = Mock()
    config.faiss_db_path = tmp_path

    architect = ArchitectService(config, Mock())

    monkeypatch.setattr(
        architect,
        "_extract_requirements",
        lambda _prompt: {"solver": "ERF"},
    )
    monkeypatch.setattr(
        architect,
        "_gather_knowledge",
        lambda _prompt, _requirements: {},
    )
    monkeypatch.setattr(
        architect,
        "_select_baseline",
        lambda **_kwargs: {"name": "ERF/Exec/ABL"},
    )
    monkeypatch.setattr(
        architect,
        "_plan_modifications",
        lambda **_kwargs: [],
    )

    plan_without_guidance = architect.create_plan(user_prompt="run ERF")
    plan_with_guidance = architect.create_plan(
        user_prompt="run ERF",
        reviewer_guidance={
            "feasible": False,
            "intent_consistent": False,
            "diagnosis": "time-step setup appears infeasible",
            "guidance": {},
        },
    )

    assert plan_without_guidance.reasoning != plan_with_guidance.reasoning
    assert "time-step setup appears infeasible" in plan_with_guidance.reasoning


def test_create_plan_applies_required_assignments_from_feedback(tmp_path, monkeypatch):
    config = Mock()
    config.faiss_db_path = tmp_path

    architect = ArchitectService(config, Mock())

    monkeypatch.setattr(architect, "_extract_requirements", lambda _prompt: {"solver": "ERF"})
    monkeypatch.setattr(architect, "_gather_knowledge", lambda _prompt, _requirements: {})
    monkeypatch.setattr(architect, "_select_baseline", lambda **_kwargs: {"name": "ERF/Exec/ABL"})
    monkeypatch.setattr(
        architect,
        "_plan_modifications",
        lambda **_kwargs: [("max_step", "10")],
    )

    plan = architect.create_plan(
        user_prompt="run short test",
        parameter_resolution_feedback={
            "required_assignments": {"dt": "20"},
        },
    )

    assert ("dt", "20") in plan.modifications


def test_required_assignment_overrides_existing_dt_alias_value() -> None:
    mods = ArchitectService._apply_required_assignments(
        [("erf.fixed_dt", "0.1")],
        {"dt": "20"},
    )
    assert ("erf.fixed_dt", "20") in mods


def test_required_assignments_respect_schema_verified_flags() -> None:
    mods = ArchitectService._apply_required_assignments(
        [("max_step", "10")],
        {"dt": "20", "max_step": "12"},
        required_assignments_meta={
            "dt": {"schema_verified": False},
            "max_step": {"schema_verified": True},
        },
    )
    assert ("max_step", "12") in mods
    assert all(param != "dt" for param, _value in mods)
