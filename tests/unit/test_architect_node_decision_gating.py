import importlib
from unittest.mock import Mock

import pytest

from src.services.plan import SimulationPlan


architect_node_module = importlib.import_module("src.nodes.architect_node")


def _require_gate_manager():
    if not hasattr(architect_node_module, "GateManager"):
        pytest.fail("GateManager not wired into architect_node.")
    return architect_node_module.GateManager


def _mock_service_instance():
    instance = Mock()
    instance.execute_planning.return_value = SimulationPlan(
        selected_solver="AMReX",
        selected_case="AMReX/Tests/Amr/Advection_AmrCore",
        modifications=[("amr.n_cell", "64 64 64")],
        reasoning="Selected Advection_AmrCore",
        baseline_confidence=0.95,
        indexing_strategy="simple",
        case_candidates=[],
    )
    return instance


def test_architect_node_solver_gate_invoked(monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.return_value = True
    gate_manager.present_gate.return_value = Mock(
        user_action="approved",
        selected_option="AMReX",
        user_modification=None,
    )
    monkeypatch.setattr(architect_node_module, "GateManager", Mock(return_value=gate_manager))

    config = Mock(
        repositories={"AMReX": "/tmp/amrex"},
        preconfirm_gate=False,
        preconfirm_gate_auto_approve=False,
        gate_strategy="terminal",
        gate_points=["solver"],
    )
    state = {"config": config, "prompt": "test prompt", "workflow_history": []}

    with monkeypatch.context() as mp:
        mp.setattr("src.nodes.architect_node.ArchitectService", Mock(return_value=_mock_service_instance()))
        mp.setattr("src.services.embedding_service_factory.get_embedding_service", Mock(return_value=Mock()))
        architect_node_module.architect_node(state)

    gate_manager.present_gate.assert_called()
    assert gate_manager.present_gate.call_args.kwargs["gate_point"] == "solver"


def test_architect_node_baseline_gate_invoked(monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.return_value = True
    gate_manager.present_gate.return_value = Mock(
        user_action="approved",
        selected_option="AMReX/Tests/Amr/Advection_AmrCore",
        user_modification=None,
    )
    monkeypatch.setattr(architect_node_module, "GateManager", Mock(return_value=gate_manager))

    config = Mock(
        repositories={"AMReX": "/tmp/amrex"},
        preconfirm_gate=False,
        preconfirm_gate_auto_approve=False,
        gate_strategy="terminal",
        gate_points=["baseline"],
    )
    state = {"config": config, "prompt": "test prompt", "workflow_history": []}

    with monkeypatch.context() as mp:
        mp.setattr("src.nodes.architect_node.ArchitectService", Mock(return_value=_mock_service_instance()))
        mp.setattr("src.services.embedding_service_factory.get_embedding_service", Mock(return_value=Mock()))
        architect_node_module.architect_node(state)

    gate_manager.present_gate.assert_called()
    assert gate_manager.present_gate.call_args.kwargs["gate_point"] == "baseline"


def test_architect_node_auto_strategy_skips_gates(monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.return_value = False
    monkeypatch.setattr(architect_node_module, "GateManager", Mock(return_value=gate_manager))

    config = Mock(
        repositories={"AMReX": "/tmp/amrex"},
        preconfirm_gate=False,
        preconfirm_gate_auto_approve=False,
        gate_strategy="auto",
        gate_points=[],
    )
    state = {"config": config, "prompt": "test prompt", "workflow_history": []}

    with monkeypatch.context() as mp:
        mp.setattr("src.nodes.architect_node.ArchitectService", Mock(return_value=_mock_service_instance()))
        mp.setattr("src.services.embedding_service_factory.get_embedding_service", Mock(return_value=Mock()))
        architect_node_module.architect_node(state)

    gate_manager.present_gate.assert_not_called()


def test_architect_node_modifications_gate_invoked(monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.return_value = True
    gate_manager.present_gate.return_value = Mock(
        user_action="approved",
        selected_option="AMReX",
        user_modification=None,
    )
    monkeypatch.setattr(architect_node_module, "GateManager", Mock(return_value=gate_manager))

    config = Mock(
        repositories={"AMReX": "/tmp/amrex"},
        preconfirm_gate=False,
        preconfirm_gate_auto_approve=False,
        gate_strategy="terminal",
        gate_points=["modifications"],
    )
    state = {"config": config, "prompt": "test prompt", "workflow_history": []}

    with monkeypatch.context() as mp:
        mp.setattr("src.nodes.architect_node.ArchitectService", Mock(return_value=_mock_service_instance()))
        mp.setattr("src.services.embedding_service_factory.get_embedding_service", Mock(return_value=Mock()))
        architect_node_module.architect_node(state)

    gate_manager.present_gate.assert_called()
    assert gate_manager.present_gate.call_args.kwargs["gate_point"] == "modifications"
