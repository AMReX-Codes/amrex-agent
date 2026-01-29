"""
Unit tests for PhysicsValidator (Reviewer Service: Physics Validator).
"""

from types import SimpleNamespace
import pytest

from src.config import AMReXAgentConfig
from src.services.validators.physics_validator import PhysicsValidator
from src.services.rules.base import RuleViolation


class TestPhysicsValidator:
    def test_skips_when_no_selected_solver(self):
        validator = PhysicsValidator(AMReXAgentConfig())
        assert validator.validate({}) == []

    def test_rejects_multiple_solvers(self):
        validator = PhysicsValidator(AMReXAgentConfig())
        violations = validator.validate({"selected_solver": ["AMReX", "PeleC"]})
        assert len(violations) == 1
        assert violations[0].rule_name == "SingleSolverEnforcement"

    def test_rejects_unknown_solver(self):
        validator = PhysicsValidator(AMReXAgentConfig())
        violations = validator.validate({"selected_solver": "NotARealSolver"})
        assert len(violations) == 1
        assert violations[0].rule_name == "SolverRegistry"

    def test_model_creation_error_is_reported(self, monkeypatch):
        validator = PhysicsValidator(AMReXAgentConfig())
        monkeypatch.setattr(validator, "code_configs", {"AMReX": object()})

        def boom(*_args, **_kwargs):
            raise ValueError("bad schema")

        monkeypatch.setattr("src.services.validators.physics_validator.ConfigModelFactory.create_from_schema", boom)

        violations = validator.validate({
            "selected_solver": "AMReX",
            "schema": {"amr.n_cell": {"type": "int"}},
            "baseline": {},
            "modifications": [],
        })

        assert len(violations) == 1
        assert violations[0].rule_name == "ModelCreation"

    def test_rule_engine_error_is_reported(self, monkeypatch):
        validator = PhysicsValidator(AMReXAgentConfig())
        monkeypatch.setattr(validator, "code_configs", {"AMReX": object()})

        class FakeModel:
            pass

        def fake_create_from_schema(*_args, **_kwargs):
            return FakeModel

        monkeypatch.setattr(
            "src.services.validators.physics_validator.ConfigModelFactory.create_from_schema",
            fake_create_from_schema,
        )

        def boom(*_args, **_kwargs):
            raise RuntimeError("rule engine failed")

        monkeypatch.setattr(validator.rule_engine, "validate", boom)

        violations = validator.validate({
            "selected_solver": "AMReX",
            "schema": {},
            "baseline": {},
            "modifications": [],
        })

        assert len(violations) == 1
        assert violations[0].rule_name == "RuleEngineError"

    def test_merge_config_expands_dot_notation(self):
        validator = PhysicsValidator(AMReXAgentConfig())
        baseline = {"geometry": {"prob_lo": "0 0 0"}}
        modifications = [
            ("amr.n_cell", "32 32 32"),
            {"parameter": "geometry.prob_hi", "new_value": "1 1 1"},
        ]

        merged = validator._merge_config(baseline, modifications)

        assert merged["geometry"]["prob_lo"] == "0 0 0"
        assert merged["geometry"]["prob_hi"] == "1 1 1"
        assert merged["amr"]["n_cell"] == "32 32 32"
