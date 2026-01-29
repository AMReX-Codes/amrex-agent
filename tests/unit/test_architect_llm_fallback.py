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
