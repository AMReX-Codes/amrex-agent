from pathlib import Path

from src.config import AMReXAgentConfig
from src.services.validators.schema_validator import SchemaSyntaxValidator


def test_schema_validator_unknown_solver_returns_critical() -> None:
    """PRD Amendment D.3; GraphState baseline fields in src/models/graph_state_canonical.py."""
    config = AMReXAgentConfig()
    validator = SchemaSyntaxValidator(config)
    validator.code_configs = {}

    plan = {"baseline": {"code_name": "UnknownSolver"}}
    violations = validator.validate(plan)

    assert violations
    assert violations[0].severity == "critical"


def test_schema_validator_missing_schema_returns_critical(tmp_path: Path, monkeypatch) -> None:
    """Reviewer contract anchor: tests/contracts/reviewer_node_contract.json (validation errors)."""
    config = AMReXAgentConfig()
    validator = SchemaSyntaxValidator(config)

    class _Solver:
        code_name = "ERF"

    validator.code_configs = {"ERF": _Solver}

    missing_path = tmp_path / "missing_schema.json"
    monkeypatch.setattr(
        "src.services.validators.schema_validator.ConfigModelFactory.resolve_schema_path",
        lambda *_args, **_kwargs: missing_path,
    )

    plan = {"baseline": {"code_name": "ERF"}}
    violations = validator.validate(plan)

    assert violations
    assert violations[0].severity == "critical"


def test_schema_validator_allows_auxiliary_params(tmp_path: Path, monkeypatch) -> None:
    """PRD Amendment D.3; auxiliary allow-list from SchemaSyntaxValidator._is_known_auxiliary()."""
    config = AMReXAgentConfig()
    validator = SchemaSyntaxValidator(config)

    class _Solver:
        code_name = "ERF"

    validator.code_configs = {"ERF": _Solver}

    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}")
    monkeypatch.setattr(
        "src.services.validators.schema_validator.ConfigModelFactory.resolve_schema_path",
        lambda *_args, **_kwargs: schema_path,
    )

    plan = {
        "baseline": {"code_name": "ERF"},
        "modifications": [("amr.plot_vars.1", "density")],
    }
    violations = validator.validate(plan)

    assert violations == []
