from src.nodes.execution_intent_node import (
    build_execution_intent,
    resolve_execution_intent,
)


def test_build_execution_intent_from_prompt_runtime_fields() -> None:
    intent = build_execution_intent(
        prompt="Run on perlmutter with 4 procs in dry run for 2 hours.",
        resolved_config={},
        prior_intent=None,
    )

    assert intent.environment == "perlmutter"
    assert intent.total_procs == 4
    assert intent.run_mode == "dry"
    assert intent.walltime == "02:00:00"
    assert intent.source == "prompt"


def test_build_execution_intent_prefers_resolved_config_values() -> None:
    intent = build_execution_intent(
        prompt="Run local with 4 procs",
        resolved_config={"execution": {"environment": "mcp", "run_mode": "submit", "run_ntasks": 8}},
        prior_intent=None,
    )

    assert intent.environment == "mcp"
    assert intent.run_mode == "submit"
    assert intent.total_procs == 8
    assert intent.source == "clarification"


def test_resolve_execution_intent_accepts_existing_payload() -> None:
    state = {
        "execution_intent": {
            "environment": "local",
            "run_mode": "full",
            "total_procs": 2,
            "source": "prompt",
            "adjustments": [],
            "execution_config": {"total_procs": 2},
        }
    }
    resolved = resolve_execution_intent(state)

    assert resolved["environment"] == "local"
    assert resolved["total_procs"] == 2


def test_build_execution_intent_rejects_non_positive_proc_values() -> None:
    intent = build_execution_intent(
        prompt="run with 0 procs",
        resolved_config={},
        prior_intent=None,
    )

    assert intent.total_procs is None
