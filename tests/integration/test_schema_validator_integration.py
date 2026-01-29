import json
from pathlib import Path
from uuid import uuid4

import pytest

from src.config import AMReXAgentConfig
from src.services.validators.schema_validator import SchemaSyntaxValidator


@pytest.fixture
def amrex_schema_file() -> Path:
    config = AMReXAgentConfig()
    schema_dir = config.amrex_agent_root / "database/schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)

    schema_payload = {
        "parameters": {
            "amr.n_cell": {"type": "IntVect"},
            "amr.cfl": {"type": "Real"},
            "amr.regrid_on_restart": {"type": "bool"},
        }
    }

    filename = f"amrex_schema_test_{uuid4().hex}.json"
    schema_path = schema_dir / filename
    schema_path.write_text(json.dumps(schema_payload))
    schema_path.touch()

    yield schema_path

    try:
        schema_path.unlink()
    except FileNotFoundError:
        pass


def test_schema_validator_flags_unknown_parameter(amrex_schema_file: Path) -> None:
    config = AMReXAgentConfig()
    validator = SchemaSyntaxValidator(config)

    plan = {
        "baseline": {"code_name": "AMReX"},
        "modifications": [("amr.unknown_param", "1")],
    }
    violations = validator.validate(plan)

    assert any(v.rule_name == "SchemaExistence" for v in violations)


def test_schema_validator_flags_type_mismatch_and_syntax(amrex_schema_file: Path) -> None:
    config = AMReXAgentConfig()
    validator = SchemaSyntaxValidator(config)

    plan = {
        "baseline": {"code_name": "AMReX"},
        "modifications": [
            ("amr.n_cell", "64 64 x"),
            ("amr.regrid_on_restart", "yes"),
        ],
    }
    violations = validator.validate(plan)

    assert any(v.rule_name == "TypeMismatch" for v in violations)


def test_schema_validator_accepts_dict_modifications_and_baseline_code(amrex_schema_file: Path) -> None:
    config = AMReXAgentConfig()
    validator = SchemaSyntaxValidator(config)

    plan = {
        "baseline": {"code": "AMReX"},
        "modifications": {"amr.cfl": "0.5"},
    }
    violations = validator.validate(plan)

    assert violations == []
