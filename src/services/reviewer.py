"""
Reviewer Service: Reviewer Orchestrator: Reviewer Orchestrator.

Central coordination point for all validation logic.
Delegates to sub-validators, aggregates results, decides workflow mode.
"""
import logging
from typing import Any

from src.services.rules.base import RuleViolation
from src.services.validation_result import ValidationResult
from src.services.validators.build_validator import BuildDependencyValidator
from src.services.validators.physics_validator import PhysicsValidator
from src.services.validators.resource_validator import ResourceValidator

# Import validators so they can be patched in tests
from src.services.validators.schema_validator import SchemaSyntaxValidator

logger = logging.getLogger(__name__)


class ReviewerOrchestrator:
    """
    Coordinates validation workflow across multiple validators.

    Execution Order:
    1. Schema (8b): Syntax validation
    2. Build/Dependency (8c): Feature availability
    3. Physics (8d): Scientific consistency
    4. Resources (8e): Runtime feasibility
    """

    def __init__(self, config):
        """Initialize orchestrator with config and all validators."""
        self.config = config

        # Initialize validators in priority order
        self.validators = [
            SchemaSyntaxValidator(config),
            BuildDependencyValidator(config),
            PhysicsValidator(config),
            ResourceValidator(config),
        ]

    def validate_plan(
        self,
        plan: dict[str, Any],
        retry_count: int = 0
    ) -> ValidationResult:
        """
        Validate execution plan through all sub-validators.

        Call context: Primary entry point used by the Reviewer node.

        Parameters
        ----------
        plan : dict
            Execution plan from Architect.
        retry_count : int, optional
            Current retry iteration.

        Returns
        -------
        ValidationResult
            Validation result with routing decision.
        """
        all_violations: list[RuleViolation] = []
        schema_params = []  # Collected from schema validator

        # Execute validators in order
        for validator in self.validators:
            # Check if validator is disabled
            if self._is_disabled(validator):
                logger.debug(f"Skipping disabled validator: {validator.__class__.__name__}")
                continue

            try:
                violations = validator.validate(plan)
                all_violations.extend(violations)

                # Capture schema params from schema validator
                if hasattr(validator, 'available_schema_params'):
                    schema_params = validator.available_schema_params

                # Short-circuit on critical errors
                if any(v.severity == 'critical' for v in violations):
                    logger.error(f"Critical validation failure in {validator.__class__.__name__}")
                    critical_violations = [v for v in violations if v.severity == 'critical']
                    for cv in critical_violations:
                        logger.error(f"  Critical error: {cv.message}")
                    logger.info(f"📊 [REVIEWER SERVICE] Returning ValidationResult with {len(schema_params)} schema params")
                    return ValidationResult(
                        available_schema_params=schema_params,
                        mode="fail",
                        violations=all_violations,
                        summary=f"Critical error: {violations[0].message}"
                    )

            except Exception as e:
                # Treat validator crash as critical system error
                logger.exception(f"Validator {validator.__class__.__name__} crashed")
                logger.info(f"📊 [REVIEWER SERVICE] Returning ValidationResult with {len(schema_params)} schema params")
                return ValidationResult(
                        available_schema_params=schema_params,
                        mode="fail",
                    violations=all_violations,
                    summary=f"Validator crash: {str(e)}"
                )

        # Determine workflow mode
        if not all_violations:
            logger.info(f"📊 [REVIEWER SERVICE] Returning ValidationResult with {len(schema_params)} schema params")
            return ValidationResult(
                        available_schema_params=schema_params,
                        mode="proceed",
                violations=[],
                summary="All validation checks passed."
            )

        # Check max retries
        max_retries = getattr(self.config, 'max_iterations', 3)
        if retry_count >= max_retries:
            logger.info(f"📊 [REVIEWER SERVICE] Returning ValidationResult with {len(schema_params)} schema params")
            return ValidationResult(
                        available_schema_params=schema_params,
                        mode="fail",
                violations=all_violations,
                summary=f"Max retries ({max_retries}) exceeded."
            )

        # Default to retry
        logger.info(f"📊 [REVIEWER SERVICE] Returning ValidationResult with {len(schema_params)} schema params")
        return ValidationResult(
                        available_schema_params=schema_params,
                        mode="retry",
            violations=all_violations,
            summary=f"Found {len(all_violations)} violations. Requesting Architect revision."
        )

    def _is_disabled(self, validator) -> bool:
        """Check if validator is disabled in config."""
        disabled = getattr(self.config, 'disabled_validators', [])
        validator_name = validator.__class__.__name__
        return validator_name in disabled
