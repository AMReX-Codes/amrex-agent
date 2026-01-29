"""
Reviewer Service: Build Dependency Validator: Build & Dependency Validator.

Validates parameters against compile-time build flags.
Enforces constraints like AMREX_USE_EB, DIM, AMREX_PARTICLES.
"""
import json
import logging
from pathlib import Path
from typing import Any

from database.configs import discover_code_configs

from src.config import AMReXAgentConfig
from src.services.config_model_factory import ConfigModelFactory
from src.services.rules.base import RuleViolation

logger = logging.getLogger(__name__)


class BuildDependencyValidator:
    """
    Reviewer Service: Build Dependency Validator: Validates runtime parameters against compile-time build flags.

    Architecture:
    - __init__: Takes AMReXAgentConfig (app settings)
    - validate: Takes plan dict (loads schema, checks build constraints)
    """

    def __init__(self, config: AMReXAgentConfig):
        """
        Initialize validator with app config.

        Args:
            config: Application configuration (paths, settings)
        """
        self.config = config
        self.code_configs = {c.code_name: c for c in discover_code_configs()}

    def validate(self, plan: dict[str, Any]) -> list[RuleViolation]:
        """
        Validate plan against build-time constraints.

        Call context: Used by Reviewer to enforce build constraints.

        Parameters
        ----------
        plan : dict
            Execution plan with baseline and modifications.

        Returns
        -------
        list of RuleViolation
            Rule violations (empty if valid).
        """
        violations = []

        # 1. Get Baseline Path & Metadata
        build_config = self._extract_build_config(plan)

        # Graceful degradation: If no build config, skip validation
        if not build_config:
            logger.warning("No build config found - skipping dependency checks")
            return []

        # 2. Load Schema for Solver
        solver_name = plan.get('selected_solver')
        if not solver_name:
            return [
                RuleViolation(
                    rule_name="BuildDependencyValidator",
                    severity="critical",
                    message="Plan missing 'selected_solver' field.",
                )
            ]
        schema = self._load_schema(solver_name)

        if not schema:
            logger.warning(f"Could not load schema for {solver_name}")
            return []

        # 3. Extract Modifications
        modifications = plan.get('modifications', [])
        if isinstance(modifications, dict):
            modifications = list(modifications.items())

        # 4. Check Each Parameter Against Build Flags
        for param, value in modifications:
            if param not in schema:
                continue  # Handled by SchemaValidator (8b)

            param_def = schema[param]

            # Check build flag requirements
            violations.extend(
                self._check_build_flags(param, param_def, build_config)
            )

            # Check dimension consistency
            violations.extend(
                self._check_dimension(param, value, build_config)
            )

        return violations

    def _extract_build_config(self, plan: dict[str, Any]) -> dict[str, str]:
        """
        Extract build configuration from plan.

        Tries in order:
        1. plan['baseline_metadata']
        2. Extract from plan['selected_case'] path

        Returns
        -------
            Build config dict (e.g., {'DIM': '3', 'AMREX_USE_EB': 'TRUE'})
        """
        # Try explicit metadata first
        if 'baseline_metadata' in plan:
            return plan['baseline_metadata']

        # Try to extract from baseline path
        baseline_path = plan.get('selected_case')
        if baseline_path:
            baseline_path = Path(baseline_path)
            if baseline_path.exists():
                try:
                    from database.configs.base_amrex_config import BaseAMReXConfig
                    metadata = BaseAMReXConfig.extract_metadata(baseline_path)
                    # Filter to uppercase keys (build flags)
                    return {k: v for k, v in metadata.items() if k.isupper()}
                except Exception as e:
                    logger.warning(f"Could not extract metadata from {baseline_path}: {e}")

        return {}

    def _load_schema(self, solver_name: str) -> dict[str, Any]:
        """
        Load schema for solver.

        Args:
            solver_name: Name of solver (from configured registry)

        Returns
        -------
            Schema parameters dict or empty dict
        """
        solver_config_class = self.code_configs.get(solver_name)
        if not solver_config_class:
            return {}

        try:
            schema_path = ConfigModelFactory.resolve_schema_path(
                solver_config_class,
                self.config.amrex_agent_root / "database/schemas",
                Path(self.config.repositories.get(solver_name, "."))
            )
            with open(schema_path) as f:
                schema_data = json.load(f)
                # Handle wrapped vs flat schema structure
                return schema_data.get('parameters', schema_data)
        except Exception as e:
            logger.warning(f"Could not load schema for {solver_name}: {e}")
            return {}

    def _check_build_flags(
        self,
        param: str,
        param_def: dict[str, Any],
        build_config: dict[str, str]
    ) -> list[RuleViolation]:
        """
        Check if parameter's build flags are satisfied.

        Args:
            param: Parameter name
            param_def: Schema definition for parameter
            build_config: Build configuration flags

        Returns
        -------
            List of violations (empty if satisfied)
        """
        violations = []
        build_flags = param_def.get('build_flags', [])

        for flag in build_flags:
            # Check if flag is enabled in build config
            flag_value = build_config.get(flag, "FALSE")

            # Handle TRUE/FALSE, 1/0, ON/OFF
            is_enabled = flag_value.upper() in ["TRUE", "1", "ON"]

            if not is_enabled:
                violations.append(RuleViolation(
                    rule_name="BuildDependency",
                    severity="error",
                    parameter=param,
                    message=f"Parameter '{param}' requires build flag '{flag}=TRUE', but it is {flag_value}.",
                    suggested_fix=f"Recompile with {flag}=TRUE or remove this parameter."
                ))

        return violations

    def _check_dimension(
        self,
        param: str,
        value: Any,
        build_config: dict[str, str]
    ) -> list[RuleViolation]:
        """
        Check if array parameter matches DIM.

        Args:
            param: Parameter name
            value: Parameter value
            build_config: Build configuration

        Returns
        -------
            List of violations (empty if valid)
        """
        violations = []

        # Only check vector-like parameters
        vector_params = ['amr.n_cell', 'geometry.prob_lo', 'geometry.prob_hi',
                        'geometry.is_periodic']

        if param not in vector_params:
            return violations

        dim = int(build_config.get('DIM', 3))
        val_str = str(value)

        # Count components (space-separated values)
        components = val_str.split()
        num_components = len(components)

        if num_components != dim:
            violations.append(RuleViolation(
                rule_name="DimensionMismatch",
                severity="error",
                parameter=param,
                message=f"Parameter '{param}' has {num_components} values but binary is DIM={dim}.",
                suggested_fix=f"Provide {dim} values for {param}."
            ))

        return violations
