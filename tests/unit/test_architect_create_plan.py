"""
Unit coverage for ArchitectService.create_plan (legacy simple pipeline).
"""

from unittest.mock import Mock

import pytest

from src.services.architect import ArchitectService


def test_create_plan_uses_baseline_and_modifications(tmp_path, monkeypatch):
    config = Mock()
    config.faiss_db_path = tmp_path
    config.faiss_semantic_weight = 0.0
    config.environment = "local"

    architect = ArchitectService(config, Mock())

    requirements = {"solver": "AMReX", "user_prompt": "2D advection"}
    baseline = {
        "code_name": "AMReX",
        "path": "Tests/Amr/Advection_AmrCore",
        "name": "AMReX/Tests/Amr/Advection_AmrCore",
        "match_score": 0.92,
    }
    modifications = [("amr.n_cell", "64 64 64")]

    monkeypatch.setattr(architect, "_extract_requirements", Mock(return_value=requirements))
    monkeypatch.setattr(architect, "_gather_knowledge", Mock(return_value={}))
    monkeypatch.setattr(architect, "_select_baseline", Mock(return_value=baseline))
    monkeypatch.setattr(architect, "_plan_modifications", Mock(return_value=modifications))
    monkeypatch.setattr(architect, "_plan_visualization", Mock(return_value={"enabled": True}))
    monkeypatch.setattr(architect, "_plan_analysis", Mock(return_value={"enabled": True}))

    plan = architect.create_plan("run advection")

    assert plan.selected_solver == "AMReX"
    assert plan.selected_case == "Tests/Amr/Advection_AmrCore"
    assert plan.modifications == modifications
    assert plan.baseline_confidence == pytest.approx(0.92)
    assert plan.used_llm is False


def test_create_plan_raises_when_no_baseline(tmp_path, monkeypatch):
    config = Mock()
    config.faiss_db_path = tmp_path
    config.faiss_semantic_weight = 0.0
    config.environment = "local"

    architect = ArchitectService(config, Mock())

    monkeypatch.setattr(architect, "_extract_requirements", Mock(return_value={"solver": "AMReX"}))
    monkeypatch.setattr(architect, "_gather_knowledge", Mock(return_value={}))
    monkeypatch.setattr(architect, "_select_baseline", Mock(return_value=None))

    with pytest.raises(ValueError):
        architect.create_plan("no baseline")
