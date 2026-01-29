"""
Reviewer Service: Physics Validator: Physics Validator.

Wraps RuleEngine to execute solver-specific physics rules.
Architecture Decision (Q4): Config-aware RuleEngine approach.
"""
import logging
from typing import Any

from database.configs import discover_code_configs

from src.config import AMReXAgentConfig
from src.services.config_model_factory import ConfigModelFactory
from src.services.rule_engine import RuleEngine
from src.services.rules.base import RuleViolation

logger = logging.getLogger(__name__)


class PhysicsValidator:
    """
    Physics consistency validator.

    Architecture (Q5: Validator wraps RuleEngine):
    - Loads solver config from plan
    - Gets validation_rules list from config
    - Delegates to RuleEngine for execution

    This keeps validators universal (Q5) while rules are solver-specific.
    """

    def __init__(self, config: AMReXAgentConfig):
        """Initialize validator with app config."""
        self.config = config
        self.rule_engine = RuleEngine()

        # Load code configs (Q6: Explicit registry via discover_code_configs)
        self.code_configs = {c.code_name: c for c in discover_code_configs()}

    def validate(self, plan: dict[str, Any]) -> list[RuleViolation]:
        """
        Validate physics consistency using solver-specific rules.

        Call context: Used by Reviewer to run physics rules.

        Parameters
        ----------
        plan : dict
            Execution plan with selected_solver and modifications.

        Returns
        -------
        list of RuleViolation
            Rule violations from physics rules.
        """
        violations = []

        # 1. Get solver name from plan (Q8: Single-solver enforcement)
        solver_name = plan.get('selected_solver')
        if not solver_name:
            logger.warning("No selected_solver in plan, skipping physics validation")
            return []

        # Enforce single-solver (Q8)
        if isinstance(solver_name, list):
            violations.append(RuleViolation(
                rule_name="SingleSolverEnforcement",
                severity="critical",
                message=f"Plan targets multiple solvers: {solver_name}. "
                        "Multi-solver workflows not supported in Phase 1.",
                suggested_fix="Resolve to single solver before validation."
            ))
            return violations

        # 2. Load solver config (Q4: Config-aware approach)
        solver_config = self.code_configs.get(solver_name)
        if not solver_config:
            logger.error(f"Unknown solver: {solver_name}")
            violations.append(RuleViolation(
                rule_name="SolverRegistry",
                severity="critical",
                message=f"Solver '{solver_name}' not found in registry.",
                parameter=None
            ))
            return violations

        # 3. Get schema and build config from plan
        schema = plan.get('schema', {})
        build_config = plan.get('build_config', {})

        # 4. Create Pydantic model from modifications
        baseline = plan.get('baseline', {})
        modifications = plan.get('modifications', [])

        try:
            # Convert plan to config model
            model_class = ConfigModelFactory.create_from_schema(schema, build_config)

            # Merge baseline + modifications
            merged_params = self._merge_config(baseline, modifications)
            config_model = model_class(**merged_params)

        except Exception as e:
            logger.exception("Failed to create config model")
            violations.append(RuleViolation(
                rule_name="ModelCreation",
                severity="error",
                message=f"Failed to create config model: {str(e)}",
                parameter=None
            ))
            return violations

        # 5. Call RuleEngine with solver config (Q4: Config-aware)
        # Rules will call model_dump(by_alias=True) themselves to get dot notation
        try:
            physics_violations = self.rule_engine.validate(
                config_model=config_model,
                solver_config=solver_config,
                build_config=build_config
            )
            violations.extend(physics_violations)

        except Exception as e:
            logger.exception("RuleEngine crashed")
            violations.append(RuleViolation(
                rule_name="RuleEngineError",
                severity="critical",
                message=f"Physics validation crashed: {str(e)}",
                parameter=None
            ))

        return violations

    def _merge_config(self, baseline: dict, modifications: list) -> dict:
        """
        Merge baseline with modifications.

        Args:
            baseline: Base configuration dict
            modifications: List of (param, value) tuples or dicts

        Returns
        -------
            Merged configuration dict
        """
        merged = dict(baseline)

        # Handle different modification formats
        if isinstance(modifications, dict):
            modifications = list(modifications.items())

        for mod in modifications:
            if isinstance(mod, tuple):
                param, value = mod
            elif isinstance(mod, dict):
                param = mod.get('parameter')
                value = mod.get('new_value')
            else:
                continue

            if param:
                # Convert dotted notation to nested dict
                # e.g., "amr.n_cell" -> merged['amr']['n_cell'] = value
                parts = param.split('.')
                if len(parts) == 1:
                    merged[param] = value
                else:
                    # Nested parameter
                    section = parts[0]
                    key = parts[1]
                    if section not in merged:
                        merged[section] = {}
                    merged[section][key] = value

        return merged
