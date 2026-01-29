"""
Reviewer Service: Physics Validator: Config Dict Validator.

Runs AMReX-generic and solver-specific validation on config dicts.
Uses BaseAMReXConfig hooks for grid/completeness and solver overrides.
"""

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from database.configs import discover_code_configs

from src.config import AMReXAgentConfig
from src.services.rules.base import RuleViolation

logger = logging.getLogger(__name__)


class ConfigValidator:
    """
    Config-driven validation for AMReX inputs.

    Uses selected_solver to pick a config class, merges baseline inputs_content
    with modifications, and delegates to validate_config().
    """

    def __init__(self, config: AMReXAgentConfig):
        self.config = config
        self.code_configs = {c.code_name: c for c in discover_code_configs()}

    def validate(self, plan: dict[str, Any]) -> list[RuleViolation]:
        """
        Validate plan configuration dictionary.

        Call context: Used by Reviewer to validate merged inputs content.

        Parameters
        ----------
        plan : dict
            Execution plan payload.

        Returns
        -------
        list of RuleViolation
            Rule violations from config validation.
        """
        solver_name = plan.get("selected_solver")
        if not solver_name:
            logger.warning("No selected_solver in plan, skipping config validation")
            return []

        if isinstance(solver_name, list):
            return [RuleViolation(
                rule_name="SingleSolverEnforcement",
                severity="critical",
                message=f"Plan targets multiple solvers: {solver_name}. "
                        "Multi-solver workflows not supported.",
                suggested_fix="Resolve to single solver before validation."
            )]

        solver_config = self.code_configs.get(solver_name)
        if not solver_config:
            return [RuleViolation(
                rule_name="SolverRegistry",
                severity="critical",
                message=f"Solver '{solver_name}' not found in registry.",
            )]

        baseline = plan.get("baseline", {})
        inputs_content = baseline.get("inputs_content", {})
        if not inputs_content:
            logger.warning("Baseline missing inputs_content; config validation limited")

        config_dict = self._merge_inputs_with_mods(inputs_content, plan.get("modifications", []))
        if not config_dict:
            return []

        return solver_config.validate_config(config_dict)

    def _merge_inputs_with_mods(
        self,
        inputs_content: dict[str, Any],
        modifications: Iterable[Any],
    ) -> dict[str, Any]:
        merged = self._expand_inputs_content(inputs_content)

        mods = self._normalize_modifications(modifications)
        for param, value in mods:
            if not param:
                continue
            self._assign_param(merged, param, value)

        return merged

    def _expand_inputs_content(self, inputs_content: dict[str, Any]) -> dict[str, Any]:
        if not inputs_content:
            return {}
        if any("." in key for key in inputs_content):
            expanded: dict[str, Any] = {}
            for key, value in inputs_content.items():
                self._assign_param(expanded, key, value)
            return expanded
        return dict(inputs_content)

    def _normalize_modifications(self, modifications: Iterable[Any]) -> list[tuple[str, Any]]:
        if isinstance(modifications, dict):
            return list(modifications.items())
        normalized: list[tuple[str, Any]] = []
        for mod in modifications or []:
            if isinstance(mod, tuple) and len(mod) == 2:
                normalized.append(mod)
            elif isinstance(mod, dict):
                param = mod.get("parameter")
                value = mod.get("new_value", mod.get("value"))
                normalized.append((param, value))
        return normalized

    def _assign_param(self, target: dict[str, Any], param: str, value: Any) -> None:
        if "." not in param:
            target[param] = value
            return
        section, key = param.split(".", 1)
        if section not in target or not isinstance(target[section], dict):
            target[section] = {}
        target[section][key] = value


if __name__ == "__main__":
    from amrex_tools import parse_pele_inputs
    from database.configs import discover_code_configs

    from src.config import AMReXAgentConfig

    amrex_root = Path(__file__).resolve().parents[5] / "amrex"
    amrex_inputs = amrex_root / "Tests/Amr/Advection_AmrCore/Exec/inputs"
    inputs_content = {}
    if amrex_inputs.exists():
        try:
            inputs_content = parse_pele_inputs(str(amrex_inputs))
            logger.info(f"Loaded AMReX inputs from {amrex_inputs}")
        except Exception as exc:
            logger.warning(f"Failed to parse {amrex_inputs}: {exc}")

    if not inputs_content:
        inputs_content = {
            "geometry.prob_lo": "0 0 0",
            "geometry.prob_hi": "1 1 1",
            "geometry.is_periodic": "0 0 0",
            "amr.n_cell": "32 32 32",
            "amr.blocking_factor": "8",
            "amr.max_grid_size": "32",
        }
    else:
        if isinstance(inputs_content.get("amr"), dict):
            n_cell = inputs_content["amr"].get("n_cell")
            blocking = inputs_content["amr"].get("blocking_factor", "16")
        else:
            n_cell = inputs_content.get("amr.n_cell")
            blocking = inputs_content.get("amr.blocking_factor", "16")
        try:
            n_cell_vals = [int(v) for v in str(n_cell).split()]
            blocking_val = int(blocking)
        except (TypeError, ValueError):
            n_cell_vals = []
            blocking_val = None
        if blocking_val and any(cells % blocking_val != 0 for cells in n_cell_vals):
            if isinstance(inputs_content.get("amr"), dict):
                inputs_content["amr"]["blocking_factor"] = "8"
            inputs_content["amr.blocking_factor"] = "8"
            logger.info("Adjusted amr.blocking_factor to 8 for demo consistency")

    solver_configs = discover_code_configs()
    solver_name = solver_configs[0].code_name if solver_configs else ""
    test_plan = {
        "selected_solver": solver_name,
        "baseline": {
            "inputs_content": inputs_content,
        },
        "modifications": [],
    }

    validator = ConfigValidator(AMReXAgentConfig())
    result = validator.validate(test_plan)
    for violation in result:
        print(f"{violation.severity}: {violation.rule_name} {violation.parameter} -> {violation.message}")
