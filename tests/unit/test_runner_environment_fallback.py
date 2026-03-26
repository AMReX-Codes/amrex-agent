import importlib
from types import SimpleNamespace

runner_node_module = importlib.import_module("src.nodes.runner_node")


def test_effective_runtime_uses_intent_procs_when_config_default(monkeypatch) -> None:
    config = SimpleNamespace(environment="local", mpi_ranks=1, run_mode="full")
    state = {"execution_intent": {"total_procs": 4, "source": "prompt", "execution_config": {}}}

    monkeypatch.setattr("src.config.detect_environment", lambda: "local")
    runtime, adjustments = runner_node_module._effective_runtime_from_intent(config, state)

    assert runtime["total_procs"] == 4
    assert adjustments == []


def test_effective_runtime_prefers_config_procs_when_non_default(monkeypatch) -> None:
    config = SimpleNamespace(environment="local", mpi_ranks=8, run_mode="full")
    state = {"execution_intent": {"total_procs": 4, "source": "prompt", "execution_config": {}}}

    monkeypatch.setattr("src.config.detect_environment", lambda: "local")
    runtime, _ = runner_node_module._effective_runtime_from_intent(config, state)

    assert runtime["total_procs"] == 8


def test_perlmutter_unreachable_falls_back_to_local(monkeypatch) -> None:
    config = SimpleNamespace(environment="local", mpi_ranks=1, run_mode="full")
    state = {
        "execution_intent": {
            "environment": "perlmutter",
            "total_procs": 4,
            "source": "prompt",
            "execution_config": {},
        }
    }

    monkeypatch.setattr("src.config.detect_environment", lambda: "local")
    monkeypatch.setattr(runner_node_module, "_is_perlmutter_reachable", lambda cfg: (False, "missing_path"))
    runtime, adjustments = runner_node_module._effective_runtime_from_intent(config, state)

    assert runtime["environment"] == "local"
    assert "environment_fallback_perlmutter_unreachable" in adjustments
