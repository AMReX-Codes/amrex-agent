"""
Reviewer Service: Schema Syntax Validator: Schema & Syntax Validator.

Validates configuration against Source Code Truth (schema from Input Writer: Schema Scraper).
Checks parameter existence, type correctness, and AMReX syntax conventions.
"""
import json
import re
from pathlib import Path
from typing import Any

from database.configs import discover_code_configs

from src.config import AMReXAgentConfig
from src.services.config_model_factory import ConfigModelFactory
from src.services.rules.base import RuleViolation


class SchemaSyntaxValidator:
    """
    Reviewer Service: Schema Syntax Validator: Validates configuration against Source Code Truth (Schema).

    Architecture:
    - __init__: Takes AMReXAgentConfig (app settings)
    - validate: Takes plan dict (loads schema dynamically based on solver)
    """

    def __init__(self, config: AMReXAgentConfig):
        import logging
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.INFO)
        self._logger.debug("[SCHEMA VALIDATOR INIT] SchemaSyntaxValidator initialized")
        """
        Initialize validator with app config.

        Args:
            config: Application configuration (paths, settings)
        """
        self.config = config
        # Load registry of code configs (PeleCConfig, etc.)
        self.code_configs = {c.code_name: c for c in discover_code_configs()}
        self.available_schema_params = []  # Populated during validate()

    def validate(self, plan: dict[str, Any]) -> list[RuleViolation]:
        """
        Validate plan against Source Code Truth (schema).

        Call context: Used by Reviewer to validate against schema truth.

        Parameters
        ----------
        plan : dict
            Execution plan with baseline and modifications.

        Returns
        -------
        list of RuleViolation
            Rule violations (empty if valid).
        """
        self._logger.debug(f"[SCHEMA VALIDATOR] validate() called (plan keys: {list(plan.keys())})")
        violations = []

        # 1. Identify Solver and Baseline
        baseline = plan.get('baseline', {})
        solver_name = baseline.get('code_name') or baseline.get('code')
        if not solver_name:
            return [RuleViolation(
                rule_name="SchemaValidation",
                severity="critical",
                message="Baseline missing 'code_name' or 'code' field."
            )]

        # Get Solver Config (for schema strategy)
        solver_config_class = self.code_configs.get(solver_name)
        if not solver_config_class:
            return [RuleViolation(
                rule_name="SchemaValidation",
                severity="critical",
                message=f"Unknown solver: {solver_name}. Cannot load schema."
            )]

        # 2. Resolve and Load Schema (Source Code Truth)
        schema_path = None
        try:
            schema_path = ConfigModelFactory.resolve_schema_path(
                solver_config_class,
                self.config.amrex_agent_root / "database/schemas",
                Path(self.config.repositories.get(solver_name, ".")),
                runtime_config=self.config,
            )
            with open(schema_path) as f:
                schema_data = json.load(f)
                # Handle wrapped vs flat schema structure
                schema = schema_data.get('parameters', schema_data)
                self.available_schema_params = list(schema.keys())
                self._logger.debug(f"[SCHEMA VALIDATOR] Loaded {len(self.available_schema_params)} schema parameters")
        except FileNotFoundError:
            if schema_path:
                self._logger.warning(f"[SCHEMA VALIDATOR] Schema file NOT FOUND at {schema_path}")
            else:
                self._logger.warning("[SCHEMA VALIDATOR] Schema file NOT FOUND (path unresolved)")
            repo_root = None
            if solver_name and hasattr(self.config, "repositories"):
                repo_root = self.config.repositories.get(solver_name)
            solver_flag = solver_name.lower() if solver_name else "<solver>"
            repo_arg = repo_root or "<path-to-repo>"
            schema_cmd = f"python database/scripts/build_schema.py {repo_arg} --solver {solver_flag}"
            return [RuleViolation(
                rule_name="SchemaMissing",
                severity="critical",
                message=f"Schema not found for {solver_name}. Run: {schema_cmd}"
            )]
        except Exception as e:
            return [RuleViolation(
                rule_name="SchemaLoadError",
                severity="critical",
                message=f"Error loading schema: {str(e)}"
            )]

        # 3. Extract Modifications
        # Ensure list of tuples format
        modifications = plan.get('modifications', [])
        if isinstance(modifications, dict):
            modifications = list(modifications.items())

        # 4. Validate Each Parameter
        for param, value in modifications:
            # Check Existence
            if param not in schema:
                # Check if it's a known auxiliary parameter (allow-list)
                if self._is_known_auxiliary(param):
                    continue

                violations.append(RuleViolation(
                    rule_name="SchemaExistence",
                    severity="error",
                    parameter=param,
                    message=f"Parameter '{param}' not found in {solver_name} source code schema.",
                    suggested_fix="Check spelling or verify parameter exists in source."
                ))
                continue

            # Check Types & Syntax
            param_def = schema[param]
            violations.extend(self._validate_type_syntax(param, value, param_def))

        return violations

    def _validate_type_syntax(
        self,
        param: str,
        value: Any,
        schema_def: dict
    ) -> list[RuleViolation]:
        """
        Validate type and syntax for a single parameter.

        Args:
            param: Parameter name
            value: Parameter value
            schema_def: Schema definition for this parameter

        Returns
        -------
            List of violations for this parameter
        """
        issues = []
        expected_type = schema_def.get('type', 'string')

        # Handle None type in schema (default to string)
        if expected_type is None:
            expected_type = 'string'

        # Normalize list/tuple inputs to AMReX-style space-separated values.
        if isinstance(value, (list, tuple)):
            val_str = " ".join(str(v) for v in value)
        else:
            val_str = str(value)
            # Also normalize stringified list representations like "[64, 64]".
            if val_str.startswith("[") and val_str.endswith("]"):
                inner = val_str[1:-1].strip()
                if inner:
                    val_str = " ".join(part.strip() for part in inner.split(","))

        # Syntax: Check for AMReX incompatible formats
        if "^" in val_str:
            issues.append(RuleViolation(
                rule_name="SyntaxFormat",
                severity="error",
                parameter=param,
                message=f"Invalid syntax '{val_str}'. AMReX does not support powers (^).",
                suggested_fix=f"Replace '{val_str}' with explicit values (e.g., '256 256 256')."
            ))

        # Type: IntVect / int
        if expected_type.lower() in ["int", "integer", "intvect", "long"]:
            # Allow space-separated integers
            if not re.match(r'^-?\d+(\s+-?\d+)*$', val_str):
                issues.append(RuleViolation(
                    rule_name="TypeMismatch",
                    severity="error",
                    parameter=param,
                    message=f"Expected integer(s) for '{param}', got '{val_str}'",
                    suggested_fix="Provide integer values (e.g., '64 64 64')."
                ))

        # Type: Real / float
        elif expected_type.lower() in ["real", "float", "double", "realvect"]:
            # Allow space-separated floats
            try:
                for v in val_str.split():
                    float(v)
            except ValueError:
                issues.append(RuleViolation(
                    rule_name="TypeMismatch",
                    severity="error",
                    parameter=param,
                    message=f"Expected float(s) for '{param}', got '{val_str}'",
                    suggested_fix="Provide numeric values."
                ))

        # Type: Bool
        elif expected_type.lower() in ["bool", "boolean"]:
            # AMReX accepts case-insensitive, but enforce strict format
            valid_bools = ["true", "false", "0", "1", "t", "f"]
            if val_str not in valid_bools:
                issues.append(RuleViolation(
                    rule_name="TypeMismatch",
                    severity="error",
                    parameter=param,
                    message=f"Invalid boolean format '{val_str}'.",
                    suggested_fix="Use 'true', 'false', '0', or '1' (AMReX format)."
                ))

        return issues

    def _is_known_auxiliary(self, param: str) -> bool:
        """
        Check if parameter is a known auxiliary parameter.

        Some parameters are valid in inputs files but not in C++ source
        (e.g., plot variables defined dynamically).

        Args:
            param: Parameter name

        Returns
        -------
            True if this is a known auxiliary parameter
        """
        known_prefixes = ["amr.plot_vars", "fab.", "amrex."]
        return any(param.startswith(p) for p in known_prefixes)
