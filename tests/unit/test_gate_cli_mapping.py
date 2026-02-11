from types import SimpleNamespace

import pytest

from src.config import AMReXAgentConfig


def _require_apply_gate_cli_settings():
    try:
        from src.main import apply_gate_cli_settings
    except ImportError as exc:
        pytest.fail(f"apply_gate_cli_settings not implemented: {exc}")
    return apply_gate_cli_settings


def test_preconfirm_only_sets_node_gate():
    apply_gate_cli_settings = _require_apply_gate_cli_settings()
    config = AMReXAgentConfig()
    args = SimpleNamespace(preconfirm=True, gate_strategy=None, gate_points=None)

    apply_gate_cli_settings(config, args)

    assert config.preconfirm_gate is True
    assert config.gate_strategy == "auto"
    assert config.gate_points == []


def test_gate_points_without_strategy_defaults_selective():
    apply_gate_cli_settings = _require_apply_gate_cli_settings()
    config = AMReXAgentConfig()
    args = SimpleNamespace(
        preconfirm=False,
        gate_strategy=None,
        gate_points="solver,baseline",
    )

    apply_gate_cli_settings(config, args)

    assert config.preconfirm_gate is False
    assert config.gate_strategy == "selective"
    assert config.gate_points == ["solver", "baseline"]


def test_gate_strategy_and_preconfirm_are_independent():
    apply_gate_cli_settings = _require_apply_gate_cli_settings()
    config = AMReXAgentConfig()
    args = SimpleNamespace(
        preconfirm=True,
        gate_strategy="terminal",
        gate_points=None,
    )

    apply_gate_cli_settings(config, args)

    assert config.preconfirm_gate is True
    assert config.gate_strategy == "terminal"
    assert config.gate_points == []
