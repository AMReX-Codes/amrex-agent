"""
Unit tests for ConfigValidator (Reviewer Service: Physics Validator).
"""

from types import SimpleNamespace
import pytest

from src.config import AMReXAgentConfig
from src.services.validators.config_validator import ConfigValidator


class TestConfigValidator:
    def test_skips_when_no_selected_solver(self):
        validator = ConfigValidator(AMReXAgentConfig())
        assert validator.validate({}) == []

    def test_rejects_multiple_solvers(self):
        validator = ConfigValidator(AMReXAgentConfig())
        violations = validator.validate({"selected_solver": ["AMReX", "PeleC"]})
        assert len(violations) == 1
        assert violations[0].rule_name == "SingleSolverEnforcement"

    def test_rejects_unknown_solver(self):
        validator = ConfigValidator(AMReXAgentConfig())
        violations = validator.validate({"selected_solver": "NotARealSolver"})
        assert len(violations) == 1
        assert violations[0].rule_name == "SolverRegistry"

    def test_merge_inputs_and_modifications_expands_namespaces(self):
        validator = ConfigValidator(AMReXAgentConfig())
        inputs = {
            "geometry.prob_lo": "0 0 0",
            "amr.n_cell": "32 32 32",
        }
        modifications = [
            ("geometry.prob_hi", "1 1 1"),
            {"parameter": "amr.max_grid_size", "value": "32"},
            {"parameter": "amr.blocking_factor", "new_value": "8"},
        ]

        merged = validator._merge_inputs_with_mods(inputs, modifications)

        assert merged["geometry"]["prob_lo"] == "0 0 0"
        assert merged["geometry"]["prob_hi"] == "1 1 1"
        assert merged["amr"]["n_cell"] == "32 32 32"
        assert merged["amr"]["max_grid_size"] == "32"
        assert merged["amr"]["blocking_factor"] == "8"

    def test_validate_delegates_to_solver_config(self, monkeypatch):
        validator = ConfigValidator(AMReXAgentConfig())

        captured = {}

        def fake_validate(config_dict):
            captured["config"] = config_dict
            return []

        fake_config = SimpleNamespace(validate_config=fake_validate)
        monkeypatch.setattr(validator, "code_configs", {"AMReX": fake_config})

        plan = {
            "selected_solver": "AMReX",
            "baseline": {
                "inputs_content": {
                    "geometry.prob_lo": "0 0 0",
                    "geometry.prob_hi": "1 1 1",
                    "geometry.is_periodic": "0 0 0",
                    "amr.n_cell": "16 16 16",
                    "amr.blocking_factor": "8",
                    "amr.max_grid_size": "16",
                }
            },
            "modifications": [("amr.max_level", "1")],
        }

        violations = validator.validate(plan)
        assert violations == []
        assert captured["config"]["amr"]["max_level"] == "1"
