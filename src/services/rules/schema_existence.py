"""
Amendment D.3: Schema Existence Rule.

Validates that all parameters in config exist in Source Code Truth (schema).
Prevents hallucinated parameters from silently being ignored by simulation.
"""

from typing import Any

from pydantic import BaseModel

from src.services.rules.base import RuleViolation, ValidationRule


class SchemaExistenceRule(ValidationRule):
    """
    Check if parameters exist in the Source Code Truth (Schema).

    Design:
    - Checks all parameters (including extras from permissive loading)
    - Compares against schema scraped from source code
    - Handles both dot-notation (amr.max_level) and underscore (amr_max_level)
    - Auto-correctable: removes unknown parameters
    - Filters out metadata fields and namespace dicts
    """

    # Plan metadata fields - NOT AMReX parameters
    METADATA_FIELDS = {
        'code_name', 'repo_path', 'case_path', 'local_path',
        'baseline', 'selected_case', 'reasoning', 'confidence',
        'modifications', 'selected_solver', 'amr_settings'
    }

    @property
    def name(self) -> str:
        """
        Rule identifier.

        Returns
        -------
        str
            Rule name.
        """
        return "SchemaExistence"

    def check(
        self,
        config: BaseModel,
        schema: dict[str, Any],
        build_config: dict[str, str]
    ) -> list[RuleViolation]:
        """
        Detect parameters not in schema (hallucinations).

        Uses model_dump(by_alias=True) to get all parameters,
        including extra fields from permissive loading.

        Filters out:
        - Metadata fields (code_name, repo_path, etc.)
        - Namespace dicts (amr, geometry, etc. - these are groups of parameters)

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
            Violations for unknown parameters.
        """
        violations = []

        # Get all parameters (including extras)
        # by_alias=True ensures defined fields use dot-notation (amr.max_level)
        config_dict = config.model_dump(by_alias=True, exclude_none=True)

        for param_name, param_value in config_dict.items():
            # SKIP 1: Metadata fields - NOT AMReX parameters
            if param_name in self.METADATA_FIELDS:
                continue

            # SKIP 2: Namespace dicts (amr, solver namespace, geometry, etc)
            # These are groups of parameters, not parameters themselves
            if isinstance(param_value, dict):
                continue

            # Check 1: Direct match (e.g., "amr.max_level")
            if param_name in schema:
                continue

            # Check 2: Underscore fallback (e.g., "amr_max_level" -> "amr.max_level")
            # Extra fields often come through as underscores if not aliased
            dotted_name = param_name.replace("_", ".")
            if dotted_name in schema:
                continue

            # If we get here, the parameter is unknown to the schema
            violations.append(RuleViolation(
                rule_name=self.name,
                severity="error",
                parameter=param_name,
                message=f"Parameter '{param_name}' not found in source code schema (Source Code Truth).",
                suggested_fix="Remove parameter or check spelling.",
                auto_correctable=True
            ))

        return violations

    def auto_correct(
        self,
        config: BaseModel,
        violation: RuleViolation
    ) -> BaseModel:
        """
        Remove unknown parameter from model.

        Handles both regular attributes and Pydantic v2 extra fields.

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
        param = violation.parameter

        # Try direct attribute removal
        if hasattr(config, param):
            delattr(config, param)
            return config

        # Try underscore version (attribute access)
        attr_name = param.replace(".", "_")
        if hasattr(config, attr_name):
            delattr(config, attr_name)

        # Handle Pydantic v2 extra fields storage
        if hasattr(config, "__pydantic_extra__") and config.__pydantic_extra__:
            if param in config.__pydantic_extra__:
                del config.__pydantic_extra__[param]
            if attr_name in config.__pydantic_extra__:
                del config.__pydantic_extra__[attr_name]

        return config
