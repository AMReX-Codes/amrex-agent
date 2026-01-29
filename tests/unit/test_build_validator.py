from src.config import AMReXAgentConfig
from src.services.validators.build_validator import BuildDependencyValidator


def test_build_validator_flags_and_dim(monkeypatch) -> None:
    """PRD Amendment D.3; GraphState plan.modifications in src/models/graph_state_canonical.py."""
    config = AMReXAgentConfig()
    validator = BuildDependencyValidator(config)

    schema = {
        "geometry.prob_lo": {"build_flags": []},
        "eb2.max_level": {"build_flags": ["AMREX_USE_EB"]},
    }
    monkeypatch.setattr(validator, "_load_schema", lambda _solver: schema)

    plan = {
        "selected_solver": "PeleC",
        "baseline_metadata": {"DIM": "3", "AMREX_USE_EB": "FALSE"},
        "modifications": [
            ("geometry.prob_lo", "0.0 0.0"),
            ("eb2.max_level", "1"),
        ],
    }

    violations = validator.validate(plan)
    messages = [v.message for v in violations]

    assert any("DIM=3" in msg for msg in messages)
    assert any("AMREX_USE_EB=TRUE" in msg for msg in messages)
