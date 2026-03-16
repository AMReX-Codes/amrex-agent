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
        reviewer_guidance_defaults = self._build_guidance(plan, [])

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
                    guidance = self._build_guidance(plan, all_violations)
                    logger.debug(f"[REVIEWER SERVICE] Returning ValidationResult with {len(schema_params)} schema params")
                    return ValidationResult(
                        available_schema_params=schema_params,
                        required_solver=guidance["required_solver"],
                        forbidden_path_patterns=guidance["forbidden_path_patterns"],
                        preferred_path_patterns=guidance["preferred_path_patterns"],
                        excluded_cases=guidance["excluded_cases"],
                        schema_escalation_required=guidance["schema_escalation_required"],
                        replan_reason_codes=guidance["replan_reason_codes"],
                        mode="fail",
                        violations=all_violations,
                        summary=f"Critical error: {violations[0].message}"
                    )

            except Exception as e:
                # Treat validator crash as critical system error
                logger.exception(f"Validator {validator.__class__.__name__} crashed")
                guidance = self._build_guidance(plan, all_violations)
                logger.debug(f"[REVIEWER SERVICE] Returning ValidationResult with {len(schema_params)} schema params")
                return ValidationResult(
                    available_schema_params=schema_params,
                    required_solver=guidance["required_solver"],
                    forbidden_path_patterns=guidance["forbidden_path_patterns"],
                    preferred_path_patterns=guidance["preferred_path_patterns"],
                    excluded_cases=guidance["excluded_cases"],
                    schema_escalation_required=guidance["schema_escalation_required"],
                    replan_reason_codes=guidance["replan_reason_codes"],
                    mode="fail",
                    violations=all_violations,
                    summary=f"Validator crash: {str(e)}"
                )

        # Determine workflow mode
        if not all_violations:
            logger.debug(f"[REVIEWER SERVICE] Returning ValidationResult with {len(schema_params)} schema params")
            return ValidationResult(
                available_schema_params=schema_params,
                required_solver=reviewer_guidance_defaults["required_solver"],
                preferred_path_patterns=reviewer_guidance_defaults["preferred_path_patterns"],
                mode="proceed",
                violations=[],
                summary="All validation checks passed."
            )

        # Check max retries
        max_retries = getattr(self.config, 'max_iterations', 3)
        guidance = self._build_guidance(plan, all_violations)
        if retry_count >= max_retries:
            logger.debug(f"[REVIEWER SERVICE] Returning ValidationResult with {len(schema_params)} schema params")
            return ValidationResult(
                available_schema_params=schema_params,
                required_solver=guidance["required_solver"],
                forbidden_path_patterns=guidance["forbidden_path_patterns"],
                preferred_path_patterns=guidance["preferred_path_patterns"],
                excluded_cases=guidance["excluded_cases"],
                schema_escalation_required=guidance["schema_escalation_required"],
                replan_reason_codes=guidance["replan_reason_codes"],
                mode="fail",
                violations=all_violations,
                summary=f"Max retries ({max_retries}) exceeded."
            )

        # Default to retry
        logger.debug(f"[REVIEWER SERVICE] Returning ValidationResult with {len(schema_params)} schema params")
        return ValidationResult(
            available_schema_params=schema_params,
            required_solver=guidance["required_solver"],
            forbidden_path_patterns=guidance["forbidden_path_patterns"],
            preferred_path_patterns=guidance["preferred_path_patterns"],
            excluded_cases=guidance["excluded_cases"],
            schema_escalation_required=guidance["schema_escalation_required"],
            replan_reason_codes=guidance["replan_reason_codes"],
            mode="retry",
            violations=all_violations,
            summary=f"Found {len(all_violations)} violations. Requesting Architect revision."
        )

    def _is_disabled(self, validator) -> bool:
        """Check if validator is disabled in config."""
        disabled = getattr(self.config, 'disabled_validators', [])
        validator_name = validator.__class__.__name__
        return validator_name in disabled

    @staticmethod
    def _selected_case(plan: dict[str, Any]) -> str:
        selected_case = plan.get("selected_case")
        if isinstance(selected_case, str) and selected_case.strip():
            return selected_case.strip()
        baseline = plan.get("baseline", {})
        if isinstance(baseline, dict):
            for key in ("case_path", "path", "local_path", "repo_path"):
                value = baseline.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    @staticmethod
    def _solver_name(plan: dict[str, Any]) -> str | None:
        baseline = plan.get("baseline", {})
        if isinstance(baseline, dict):
            for key in ("code_name", "code", "solver"):
                value = baseline.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _build_guidance(self, plan: dict[str, Any], violations: list[RuleViolation]) -> dict[str, Any]:
        if not bool(getattr(self.config, "reviewer_reflexive_guidance_enabled", True)):
            return {
                "required_solver": self._solver_name(plan),
                "forbidden_path_patterns": [],
                "preferred_path_patterns": [],
                "excluded_cases": [],
                "schema_escalation_required": False,
                "replan_reason_codes": [],
            }
        selected_case = self._selected_case(plan)
        required_solver = self._solver_name(plan)

        reason_codes: set[str] = set()
        for violation in violations:
            rule_name = (violation.rule_name or "").lower()
            message = (violation.message or "").lower()
            severity = (violation.severity or "").lower()

            if "intent" in rule_name or ("intent" in message and "missing" in message):
                reason_codes.add("intent_missing")
            if "schema" in rule_name:
                reason_codes.add("schema_unresolved")
            if "solver" in rule_name or "unknown solver" in message:
                reason_codes.add("solver_mismatch")
            if "resource" in rule_name or "build" in rule_name:
                reason_codes.add("resource_conflict")
            if "physics" in rule_name:
                reason_codes.add("domain_conflict")
            if "path" in message or "inputs file" in message or "no such file" in message:
                reason_codes.add("baseline_path_mismatch")
            if ("429" in message or "rate limit" in message or "too many requests" in message) and severity != "info":
                reason_codes.add("rate_limit_pressure")

        if not reason_codes and violations:
            reason_codes.add("schema_unresolved")

        configured_codes = getattr(self.config, "reviewer_reason_codes", None)
        if not isinstance(configured_codes, (list, tuple, set)):
            configured_codes = [
                "intent_missing",
                "solver_mismatch",
                "baseline_path_mismatch",
                "domain_conflict",
                "schema_unresolved",
                "resource_conflict",
                "rate_limit_pressure",
            ]
        allowed_codes = set(str(code) for code in configured_codes)
        normalized_codes = sorted(code for code in reason_codes if code in allowed_codes)
        preferred_patterns: list[str] = []
        if selected_case and "/" in selected_case:
            preferred_patterns.append(selected_case.rsplit("/", 1)[0])

        forbidden_patterns: list[str] = []
        if "baseline_path_mismatch" in normalized_codes and selected_case:
            forbidden_patterns.append(selected_case)

        excluded_cases: list[str] = [selected_case] if selected_case and normalized_codes else []
        schema_escalation_required = "schema_unresolved" in normalized_codes

        return {
            "required_solver": required_solver,
            "forbidden_path_patterns": forbidden_patterns,
            "preferred_path_patterns": preferred_patterns,
            "excluded_cases": excluded_cases,
            "schema_escalation_required": schema_escalation_required,
            "replan_reason_codes": normalized_codes,
        }
