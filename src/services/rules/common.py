"""
Input Writer: Rule Factory: Generic AMReX Rules.

Minimal implementation for TDD.
"""

from typing import Any

from pydantic import BaseModel

from .base import RuleViolation, ValidationRule


class BuildFlagDependencyRule(ValidationRule):
    """Check parameters match build configuration."""

    @property
    def name(self) -> str:
        """
        Rule identifier.

        Returns
        -------
        str
            Rule name.
        """
        return "BuildFlagDependency"

    def check(
        self,
        config: BaseModel,
        schema: dict[str, Any],
        build_config: dict[str, str]
    ) -> list[RuleViolation]:
        """
        Check configuration against build flag dependencies.

        Parameters
        ----------
        config : BaseModel
            Config model to validate.
        schema : dict
            Schema dictionary for available fields.
        build_config : dict
            Build flags for dependency checks.

        Returns
        -------
        list of RuleViolation
            Violations found by the rule.
        """
        violations = []

        # Get config dict with original parameter names
        config_dict = config.model_dump(by_alias=True, exclude_none=True)

        for param_name, param_value in config_dict.items():
            if param_value is None:
                continue

            # Check schema for dependencies
            # Handle both dot notation (solver.moisture_model) and underscore (solver_moisture_model)
            param_schema = schema.get(param_name, {})
            if not param_schema:
                # Try converting FIRST underscore to dot (namespace separator)
                # solver_moisture_model -> solver.moisture_model (NOT solver.moisture.model)
                parts = param_name.split('_', 1)  # Split on first underscore only
                if len(parts) == 2:
                    dotted_name = f"{parts[0]}.{parts[1]}"
                    param_schema = schema.get(dotted_name, {})
                    if param_schema:
                        param_name = dotted_name  # Use dotted name for error message

            dependencies = param_schema.get("dependencies", [])

            for dep in dependencies:
                # Check if dependency is satisfied (must be TRUE/ON)
                is_satisfied = False

                # Check exact name first
                if dep in build_config:
                    if build_config[dep].upper() in ["TRUE", "ON", "1", "YES"]:
                        is_satisfied = True
                else:
                    # Try normalized (ERF_USE_MOISTURE → USE_MOISTURE)
                    # Solver prefixes use *_.
                    # Known solver prefixes: ERF_, INCFLO_, PELEC_, PELELMEX_, WARPX_.
                    normalized = (
                        dep.replace("ERF_", "")
                        .replace("INCFLO_", "")
                        .replace("PELEC_", "")
                        .replace("PELELMEX_", "")
                        .replace("WARPX_", "")
                    )
                    if normalized in build_config and build_config[normalized].upper() in ["TRUE", "ON", "1", "YES"]:
                        is_satisfied = True

                if not is_satisfied:
                    violations.append(RuleViolation(
                        rule_name=self.name,
                        severity="error",
                        parameter=param_name,
                        message=f"Parameter '{param_name}' requires build flag '{dep}' "
                               f"but it's not enabled in build configuration",
                        suggested_fix=f"Remove '{param_name}' or recompile with {dep}=TRUE"
                    ))

        return violations


class GridConsistencyRule(ValidationRule):
    """Check AMReX grid constraints."""

    @property
    def name(self) -> str:
        """
        Rule identifier.

        Returns
        -------
        str
            Rule name.
        """
        return "GridConsistency"

    def check(
        self,
        config: BaseModel,
        schema: dict[str, Any],
        build_config: dict[str, str]
    ) -> list[RuleViolation]:
        """
        Check AMReX grid constraints.

        Parameters
        ----------
        config : BaseModel
            Config model to validate.
        schema : dict
            Schema dictionary for available fields.
        build_config : dict
            Build flags for dependency checks.

        Returns
        -------
        list of RuleViolation
            Violations found by the rule.
        """
        violations = []

        # Get grid parameters
        n_cell = getattr(config, 'amr_n_cell', None)
        blocking_factor = getattr(config, 'amr_blocking_factor', None)

        # Check blocking_factor divides n_cell
        if n_cell and blocking_factor:
            n_cells = n_cell if isinstance(n_cell, list) else [n_cell]
            if isinstance(blocking_factor, list):
                b_factors = blocking_factor
            else:
                b_factors = [blocking_factor] * len(n_cells)
            for i, nc in enumerate(n_cells):
                bf = b_factors[i] if i < len(b_factors) else b_factors[-1]
                if bf and nc % bf != 0:
                    violations.append(RuleViolation(
                        rule_name=self.name,
                        severity="error",
                        parameter="amr.blocking_factor",
                        message=f"blocking_factor ({bf}) must divide n_cell[{i}] ({nc})",
                        suggested_fix=f"Use blocking_factor that divides {nc}",
                        auto_correctable=True
                    ))

        return violations

    def auto_correct(
        self,
        config: BaseModel,
        violation: RuleViolation
    ) -> BaseModel:
        """
        Auto-correct blocking_factor to nearest divisor.

        Parameters
        ----------
        config : BaseModel
            Config model to update.
        violation : RuleViolation
            Violation to correct.

        Returns
        -------
        BaseModel
            Updated config model.
        """
        if "blocking_factor" in violation.message and hasattr(config, 'amr_n_cell'):
            n_cell = config.amr_n_cell
            bf = getattr(config, 'amr_blocking_factor', None)
            n_cells = n_cell if isinstance(n_cell, list) else [n_cell]
            if not n_cells:
                return config
            nc = n_cells[0]
            divisors = [i for i in range(1, nc + 1) if nc % i == 0]
            if not divisors:
                return config
            current = bf[0] if isinstance(bf, list) and bf else bf or 1
            new_bf = min(divisors, key=lambda x: abs(x - current))
            config.amr_blocking_factor = new_bf

        return config


class TimestepBoundsRule(ValidationRule):
    """Detect suspicious timestep usage (e.g., huge max_dt for 'timesteps')."""

    @property
    def name(self) -> str:
        """
        Rule identifier.

        Returns
        -------
        str
            Rule name.
        """
        return "TimestepBounds"

    def check(
        self,
        config: BaseModel,
        schema: dict[str, Any],
        build_config: dict[str, str]
    ) -> list[RuleViolation]:
        """
        Check for suspicious timestep usage.

        Parameters
        ----------
        config : BaseModel
            Config model to validate.
        schema : dict
            Schema dictionary for available fields.
        build_config : dict
            Build flags for dependency checks.

        Returns
        -------
        list of RuleViolation
            Violations found by the rule.
        """
        violations: list[RuleViolation] = []

        max_dt = getattr(config, 'amr_max_dt', None)
        max_step = getattr(config, 'amr_max_step', None)
        if max_dt is not None:
            try:
                dt_val = float(max_dt)
            except (TypeError, ValueError):
                dt_val = None
            if dt_val is not None and dt_val > 1.0 and max_step is None:
                violations.append(RuleViolation(
                    rule_name=self.name,
                    severity="error",
                    parameter="amr.max_dt",
                    message=(
                        f"amr.max_dt ({dt_val}) is unusually large. "
                        "Did you mean amr.max_step for number of timesteps?"
                    ),
                    suggested_fix="Replace amr.max_dt with amr.max_step"
                ))

        return violations
