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
        mp.setattr(architect_node_module, "ArchitectService", Mock(return_value=_mock_service_instance()))
        mp.setattr("src.services.embedding_service_factory.get_embedding_service", Mock(return_value=Mock()))
        updates = architect_node_module.architect_node(state)

    gate_manager.present_gate.assert_called()
    assert gate_manager.present_gate.call_args.kwargs["gate_point"] == "solver"
    history = updates.get("workflow_history", [])
    assert any(
        entry.get("node") == "preconfirm_gate" and entry.get("details", {}).get("gate_node") == "solver"
        for entry in history
    )


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
        mp.setattr(architect_node_module, "ArchitectService", Mock(return_value=_mock_service_instance()))
        mp.setattr("src.services.embedding_service_factory.get_embedding_service", Mock(return_value=Mock()))
        updates = architect_node_module.architect_node(state)

    gate_manager.present_gate.assert_called()
    assert gate_manager.present_gate.call_args.kwargs["gate_point"] == "baseline"
    history = updates.get("workflow_history", [])
    assert any(
        entry.get("node") == "preconfirm_gate" and entry.get("details", {}).get("gate_node") == "baseline"
        for entry in history
    )


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
        mp.setattr(architect_node_module, "ArchitectService", Mock(return_value=_mock_service_instance()))
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
        mp.setattr(architect_node_module, "ArchitectService", Mock(return_value=_mock_service_instance()))
        mp.setattr("src.services.embedding_service_factory.get_embedding_service", Mock(return_value=Mock()))
        updates = architect_node_module.architect_node(state)

    gate_manager.present_gate.assert_called()
    assert gate_manager.present_gate.call_args.kwargs["gate_point"] == "modifications"
    history = updates.get("workflow_history", [])
    assert any(
        entry.get("node") == "preconfirm_gate" and entry.get("details", {}).get("gate_node") == "modifications"
        for entry in history
    )


def test_architect_node_records_user_modification(monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.return_value = True
    gate_manager.present_gate.return_value = Mock(
        user_action="modified",
        selected_option="AMReX",
        user_modification={
            "parameters": {"amr.n_cell": "128 256 16"},
            "original": {"amr.n_cell": "64 64 64"},
        },
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
        mp.setattr(architect_node_module, "ArchitectService", Mock(return_value=_mock_service_instance()))
        mp.setattr("src.services.embedding_service_factory.get_embedding_service", Mock(return_value=Mock()))
        updates = architect_node_module.architect_node(state)

    history = updates.get("workflow_history", [])
    gate_entry = next(
        entry for entry in history
        if entry.get("node") == "preconfirm_gate" and entry.get("details", {}).get("gate_node") == "modifications"
    )
    assert gate_entry["details"]["user_modification"]["original"]["amr.n_cell"] == "64 64 64"


def test_solver_override_triggers_retry(monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.side_effect = lambda point: point == "solver"
    gate_manager.present_gate.return_value = Mock(
        user_action="modified",
        selected_option="ERF",
        user_modification={"manual_selection": "ERF"},
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
        mp.setattr(architect_node_module, "ArchitectService", Mock(return_value=_mock_service_instance()))
        mp.setattr("src.services.embedding_service_factory.get_embedding_service", Mock(return_value=Mock()))
        updates = architect_node_module.architect_node(state)

    assert updates["mode"] == "retry"
    assert updates["selected_solver"] == "ERF"


def test_solver_override_same_selection_no_retry(monkeypatch):
    GateManager = _require_gate_manager()
    gate_manager = Mock()
    gate_manager.should_gate.side_effect = lambda point: point == "solver"
    gate_manager.present_gate.return_value = Mock(
        user_action="modified",
        selected_option="AMReX",
        user_modification={"manual_selection": "AMReX"},
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
        mp.setattr(architect_node_module, "ArchitectService", Mock(return_value=_mock_service_instance()))
        mp.setattr("src.services.embedding_service_factory.get_embedding_service", Mock(return_value=Mock()))
        updates = architect_node_module.architect_node(state)

    assert updates["mode"] == "proceed"
