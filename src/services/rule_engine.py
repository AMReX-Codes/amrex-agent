"""
Input Writer: Rule Engine Orchestrator: Rule Engine Orchestrator.

Bridges config-driven validation rules with runtime execution.
Executes rules defined in solver configs against Pydantic models.

Architecture:
  • Reads validation_rules from solver config classes
  • Creates rules via RuleFactory (Input Writer: Rule Factory)
  • Aggregates violations
  • Auto-corrects when possible (Amendment C)

Design Decisions:
  - Warn on missing validation_rules (don't crash)
  - Single-pass enforcement (not iterative)
  - Log warnings for unknown rules
  - Return corrected BaseModel from enforce()
"""

import logging
from typing import Any

from pydantic import BaseModel

from src.services.rules import RuleFactory, RuleViolation

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Orchestrator for validation rules.

    Executes rules defined in Solver Configs against Pydantic models.
    Implements Amendment C (Contextual Generation) via auto-correction.
    """

    @staticmethod
    def validate(
        config_model: BaseModel,
        solver_config: Any,
        build_config: dict[str, str] | None = None
    ) -> list[RuleViolation]:
        """
        Run all rules defined for the specific solver configuration.

        Parameters
        ----------
        config_model : BaseModel
            Pydantic model to validate.
        solver_config : object
            Solver config class (has validation_rules attribute).
        build_config : dict or None, optional
            Build flags (USE_EB, DIM, etc.).

        Returns
        -------
        list of RuleViolation
            Aggregated violations from all rules.

        Behavior:
            • Reads validation_rules from solver_config
            • Creates each rule via RuleFactory
            • Executes rule.check()
            • Aggregates violations
            • Warns on unknown rules (doesn't crash)
            • Safe default if validation_rules missing

        Design (Q4: Config-aware validation):
            • Rules receive BaseModel (config_model)
            • Rules call model_dump(by_alias=True) to get dot-notation parameters
            • Aliases are set in create_from_schema() to original parameter names
            • This ensures RuleEngine validates against Source Code Truth with correct notation
        """
        violations = []
        build_config = build_config or {}

        # 1. Get list of rules from solver config
        # Safe default: empty list if attribute missing
        rule_names = getattr(solver_config, 'validation_rules', [])

        if not rule_names:
            logger.debug("No validation rules defined for this solver config")
            return violations

        # 2. Extract schema from Pydantic model
        # Rules use this to check if fields exist
        schema = {}
        if hasattr(config_model, 'model_json_schema'):
            try:
                json_schema = config_model.model_json_schema()
                # Extract just the properties dict from JSON Schema
                # Pydantic JSON Schema format: {"properties": {...}, "title": ..., "type": "object", ...}
                # Rules expect: {"amr.n_cell": {...}, "geometry.is_periodic": {...}, ...}
                schema = json_schema.get('properties', {})
            except Exception as e:
                logger.warning(f"Could not extract schema: {e}")

        # 3. Execute each rule
        for rule_name in rule_names:
            try:
                # Create rule instance
                rule = RuleFactory.create(rule_name)

                # Execute rule check
                # Rules receive BaseModel and call model_dump(by_alias=True) themselves
                rule_violations = rule.check(config_model, schema, build_config)

                # Aggregate violations
                violations.extend(rule_violations)

                logger.debug(f"Rule '{rule_name}' found {len(rule_violations)} violation(s)")

            except KeyError:
                # Unknown rule name - log and skip
                logger.warning(f"Skipping unknown validation rule: '{rule_name}'")

            except Exception as e:
                # Unexpected error - log and skip
                logger.error(f"Error running rule '{rule_name}': {e}")

        return violations

    @staticmethod
    def enforce(
        config_model: BaseModel,
        solver_config: Any,
        build_config: dict[str, str] | None = None
    ) -> BaseModel:
        """
        Run validation and AUTO-CORRECT violations.

        Implements Amendment C.3 (Contextual Generation):
        - Detect violations
        - Auto-fix when auto_correctable=True
        - Return corrected model

        Parameters
        ----------
        config_model : BaseModel
            Pydantic model (may be modified in place).
        solver_config : object
            Solver config class.
        build_config : dict or None, optional
            Build flags.

        Returns
        -------
        BaseModel
            Corrected model.

        Behavior:
            • Single-pass correction (not iterative)
            • Only corrects auto_correctable violations
            • Logs corrections and failures
            • Returns model even if some violations remain
        """
        # 1. Run validation to find issues
        violations = RuleEngine.validate(config_model, solver_config, build_config)

        if not violations:
            logger.debug("No violations found - no corrections needed")
            return config_model

        # 2. Apply fixes for auto-correctable violations
        for violation in violations:
            if not violation.auto_correctable:
                # Skip non-auto-correctable violations
                logger.debug(
                    f"Skipping non-auto-correctable violation: {violation.message}"
                )
                continue

            try:
                # Get rule instance
                rule = RuleFactory.create(violation.rule_name)

                # Apply auto-correction
                config_model = rule.auto_correct(config_model, violation)

                logger.info(f"Auto-corrected: {violation.message}")

            except Exception as e:
                # Auto-correction failed
                logger.error(
                    f"Failed to auto-correct {violation.rule_name}: {e}"
                )

        return config_model
