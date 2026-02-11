import builtins
import io
from contextlib import redirect_stdout

import pytest

import src.utils.gate as gate


def _require_gate_manager():
    if not hasattr(gate, "GateManager"):
        pytest.fail("GateManager not implemented (F3.1 control options).")
    if not hasattr(gate, "GateDecision"):
        pytest.fail("GateDecision not implemented (F3.1/F3.2 audit payload).")
    return gate.GateManager


def _input_sequence(monkeypatch, values):
    iterator = iter(values)
    monkeypatch.setattr(builtins, "input", lambda _: next(iterator))


def test_gate_manager_approve_records_decision(monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["a"])

    manager = GateManager(strategy="terminal", gate_points=["solver"])
    decision = manager.present_gate(
        gate_point="solver",
        selected="PeleC",
        confidence=0.91,
        reasoning="Long-form reasoning that should be shown to the user.",
        evidence={"source": "L0 index"},
        alternatives=[{"name": "PeleLMeX", "rejected_reason": "Low-Mach mismatch"}],
    )

    assert decision.user_action == "approved"
    assert decision.gate_point == "solver"
    assert decision.selected_option == "PeleC"


def test_gate_manager_manual_select_records_modification(monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["m", "2"])

    manager = GateManager(strategy="terminal", gate_points=["solver"])
    decision = manager.present_gate(
        gate_point="solver",
        selected="PeleC",
        confidence=0.88,
        reasoning="Reasoning details",
        evidence={"source": "L0 index"},
        alternatives=[
            {"name": "PeleC", "rejected_reason": "Baseline"},
            {"name": "ERF", "rejected_reason": "Atmospheric focus"},
        ],
    )

    assert decision.user_action == "modified"
    assert decision.selected_option == "ERF"
    assert decision.user_modification["manual_selection"] == "ERF"


def test_gate_manager_edit_mode_resource_validation(monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["e", "amr.n_cell", "256 512 32", "done", "y"])

    manager = GateManager(strategy="terminal", gate_points=["modifications"])
    decision = manager.present_gate(
        gate_point="modifications",
        selected="baseline",
        confidence=0.73,
        reasoning="Reasoning details",
        evidence={"source": "plan"},
        alternatives=[],
    )

    assert decision.user_action == "modified"
    assert decision.user_modification["parameters"]["amr.n_cell"] == "256 512 32"


def test_gate_manager_reject_records_decision(monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["r"])

    manager = GateManager(strategy="terminal", gate_points=["solver"])
    decision = manager.present_gate(
        gate_point="solver",
        selected="PeleC",
        confidence=0.55,
        reasoning="Reasoning details",
        evidence={"source": "L0 index"},
        alternatives=[{"name": "ERF", "rejected_reason": "Atmospheric focus"}],
    )

    assert decision.user_action == "rejected"
    assert decision.gate_point == "solver"


def test_gate_manager_skip_option(monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["s"])

    manager = GateManager(strategy="terminal", gate_points=["baseline"])
    decision = manager.present_gate(
        gate_point="baseline",
        selected="FlameSheet",
        confidence=0.6,
        reasoning="Reasoning details",
        evidence={"source": "L1 index"},
        alternatives=[],
    )

    assert decision.user_action == "skipped"
    assert decision.gate_point == "baseline"


def test_gate_manager_selective_strategy_filters_points(monkeypatch):
    GateManager = _require_gate_manager()
    manager = GateManager(strategy="selective", gate_points=["solver"])

    assert manager.should_gate("solver") is True
    assert manager.should_gate("baseline") is False


def test_gate_manager_auto_strategy_skips_all_points(monkeypatch):
    GateManager = _require_gate_manager()
    manager = GateManager(strategy="auto", gate_points=["solver", "baseline"])

    assert manager.should_gate("solver") is False
    assert manager.should_gate("baseline") is False
    assert manager.should_gate("execution") is False


def test_gate_manager_save_history_writes_gate_history(tmp_path, monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["a"])

    manager = GateManager(strategy="terminal", gate_points=["solver"])
    decision = manager.present_gate(
        gate_point="solver",
        selected="PeleC",
        confidence=0.91,
        reasoning="Reasoning details",
        evidence={"source": "L0 index"},
        alternatives=[],
    )
    manager.save_history(str(tmp_path))

    history_path = tmp_path / "gate_history.json"
    assert history_path.exists()
    payload = history_path.read_text()
    assert "gate_point" in payload
    assert "user_action" in payload
    assert "timestamp" in payload
    assert decision.selected_option in payload


def test_gate_manager_view_evidence_reprompts(monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["v", "a"])

    manager = GateManager(strategy="terminal", gate_points=["solver"])
    decision = manager.present_gate(
        gate_point="solver",
        selected="PeleC",
        confidence=0.91,
        reasoning="Reasoning details",
        evidence={"source": "L0 index"},
        alternatives=[],
    )

    assert decision.user_action == "approved"


def test_gate_manager_reject_refine_requires_feedback(monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["r", "Need different solver due to Mach regime"])

    manager = GateManager(strategy="terminal", gate_points=["solver"])
    decision = manager.present_gate(
        gate_point="solver",
        selected="PeleC",
        confidence=0.42,
        reasoning="Reasoning details",
        evidence={"source": "L0 index"},
        alternatives=[],
    )

    assert decision.user_action == "rejected"
    assert decision.user_modification["feedback"] == "Need different solver due to Mach regime"


def test_gate_manager_prints_reasoning_and_evidence(monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["a"])

    manager = GateManager(strategy="terminal", gate_points=["solver"])
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        manager.present_gate(
            gate_point="solver",
            selected="PeleC",
            confidence=0.91,
            reasoning="Reasoning details",
            evidence={"source": "L0 index"},
            alternatives=[],
        )

    output = buffer.getvalue()
    assert "Reasoning details" in output
    assert "L0 index" in output


def test_gate_manager_edit_mode_validates_resources(monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["e", "amr.n_cell", "256 512 32", "done", "n"])

    manager = GateManager(strategy="terminal", gate_points=["modifications"])
    with pytest.raises(Exception):
        manager.present_gate(
            gate_point="modifications",
            selected="baseline",
            confidence=0.73,
            reasoning="Reasoning details",
            evidence={"source": "plan"},
            alternatives=[],
        )


def test_gate_manager_edit_records_original_values(monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["e", "amr.n_cell", "256 512 32", "done", "y"])

    manager = GateManager(strategy="terminal", gate_points=["modifications"])
    decision = manager.present_gate(
        gate_point="modifications",
        selected="baseline",
        confidence=0.73,
        reasoning="Reasoning details",
        evidence={"source": "plan"},
        alternatives=[],
        current_parameters={"amr.n_cell": "128 256 16"},
    )

    assert decision.user_modification["original"]["amr.n_cell"] == "128 256 16"


def test_gate_history_records_original_parameters(tmp_path, monkeypatch):
    GateManager = _require_gate_manager()
    _input_sequence(monkeypatch, ["e", "amr.n_cell", "256 512 32", "done", "y"])

    manager = GateManager(strategy="terminal", gate_points=["modifications"])
    decision = manager.present_gate(
        gate_point="modifications",
        selected="baseline",
        confidence=0.73,
        reasoning="Reasoning details",
        evidence={"source": "plan"},
        alternatives=[],
    )
    decision.user_modification["original"] = {"amr.n_cell": "128 256 16"}
    manager.save_history(str(tmp_path))

    payload = (tmp_path / "gate_history.json").read_text()
    assert "original" in payload
