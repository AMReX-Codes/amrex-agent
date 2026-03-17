"""
Reviewer node - Pre-execution plan validation.

L1 Integration: Architect + Reviewer (State Machine Logic)
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import GraphState
from src.models.state_transitions import (
    skip_review,
)
from src.services.reviewer import ReviewerOrchestrator
from src.utils.gate import run_preconfirm_gate

logger = logging.getLogger(__name__)
_ERROR_TAXONOMY_VERSION = "v1"


def _normalize_error_taxonomy(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize reviewer terminal taxonomy payloads to a stable UNNUMBERED-236 shape."""
    normalized = dict(payload) if isinstance(payload, dict) else {}
    unresolved = normalized.get("unresolved_parameters")
    if not isinstance(unresolved, list):
        unresolved = []
    normalized["unresolved_parameters"] = [str(p) for p in unresolved]

    normalized["version"] = _ERROR_TAXONOMY_VERSION
    normalized["stage"] = "reviewer"
    normalized["terminal"] = bool(normalized.get("terminal", True))
    normalized["type"] = str(normalized.get("type") or "retry_exhausted")
    normalized["category"] = str(normalized.get("category") or "reviewer_terminal_failure")
    reason_code = normalized.get("reason_code") or normalized.get("reason") or "unspecified"
    normalized["reason_code"] = str(reason_code)
    normalized["reason"] = str(reason_code)
    normalized["retry_count"] = int(normalized.get("retry_count", 0))
    normalized["max_retries"] = int(normalized.get("max_retries", 0))
    return normalized


def _build_final_error_taxonomy(
    *,
    category: str,
    reason: str,
    retry_count: int,
    max_retries: int,
    unresolved_parameters: list[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    return _normalize_error_taxonomy(
        {
            "type": "retry_exhausted",
            "terminal": True,
            "version": _ERROR_TAXONOMY_VERSION,
            "reason_code": reason,
            "reason": reason,
            "category": category,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "unresolved_parameters": [p[0] for p in unresolved_parameters or []],
        }
    )


def get_architect_plan(state: GraphState) -> dict[str, Any] | None:
    """
    Resolve the architect plan from workflow history or state.

    Parameters
    ----------
    state : GraphState
        Current workflow state containing workflow history and plan data.

    Returns
    -------
    dict or None
        Architect plan dict when available; otherwise ``None``.
    """
    # Try canonical path first (source of truth)
    try:
        history = state.get('workflow_history', [])
        architect_entry = next(
            e for e in reversed(history)
            if e.get('node') == 'architect'
        )
        plan = architect_entry.get('details', {})
        if plan:
            logger.debug("Plan loaded from workflow_history (canonical path)")
            return plan
    except StopIteration:
        logger.debug("Architect entry not in workflow_history, falling back to state")

    # Fallback to pragmatic path (convenience copy in state)
    plan = state.get("plan")
    if plan:
        logger.debug("Plan loaded from state (pragmatic path - convenience copy)")
        return plan

    logger.warning("Plan not found in workflow_history or state")
    return None


def _load_baseline_inputs_content(plan: dict[str, Any]) -> dict[str, Any]:
    baseline = plan.get("baseline", {})
    metadata = baseline.get("metadata", {})
    inputs_content = (
        metadata.get("inputs_content")
        or baseline.get("inputs_content")
        or {}
    )
    if inputs_content:
        return inputs_content

    solver_name = baseline.get("code_name") or baseline.get("code")
    local_path = metadata.get("local_path") or baseline.get("local_path")
    repo_path = metadata.get("repo_path") or baseline.get("repo_path")
    if not solver_name or not local_path:
        return {}

    try:
        from database.configs import discover_code_configs

        code_registry = {c.code_name: c for c in discover_code_configs()}
        solver_config = code_registry.get(solver_name)
        if not solver_config:
            return {}

        metadata_from_inputs = solver_config.extract_metadata(
            Path(local_path),
            repo_root=Path(repo_path) if repo_path else None,
        )
        return metadata_from_inputs.get("inputs_content", {})
    except Exception as exc:
        logger.debug(f"[Reviewer] extract_metadata failed: {exc}")
        return {}


def reviewer_node(state: GraphState) -> dict[str, Any]:
    """
    Validate the architect plan before execution.

    Call context: LangGraph node entry point.

    Parameters
    ----------
    state : GraphState
        Current workflow state.

    Returns
    -------
    dict
        State updates containing review decisions and guidance.
    """
    logger.info("=" * 80)
    logger.info("Starting Reviewer node")
    logger.info("=" * 80)

    config = state["config"]
    iteration = state.get("iteration", 0)

    workflow_history = state.get("workflow_history", [])
    architect_entry = next(
        (entry for entry in reversed(workflow_history) if entry.get("node") == "architect"),
        None,
    )
    plan_details = architect_entry.get("details", {}) if architect_entry else {}
    selected_case = plan_details.get("selected_case", "unknown")
    modifications = plan_details.get("modifications", []) or []

    auto_approve = getattr(config, "preconfirm_gate_auto_approve", False) is True
    gate_result = run_preconfirm_gate(
        node_name="reviewer",
        summary_lines=[
            "This step validates the plan before writing inputs.",
            f"Selected case: {selected_case}",
            f"Planned modifications: {len(modifications)}",
        ],
        options=[{"label": "Proceed with validation", "value": "proceed"}],
        enabled=getattr(config, "preconfirm_gate", False) is True,
        allow_cancel=True,
        auto_approve=auto_approve,
    )
    gate_entry = gate_result.get("history_entry")
    if gate_entry:
        gate_entry["iteration"] = iteration
    if gate_result["action"] == "cancel":
        return {
            "mode": "terminal",
            "error": "User canceled at pre-confirm gate.",
            "workflow_history": state.get("workflow_history", []) + ([gate_entry] if gate_entry else []),
        }
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    workflow_history = state.get("workflow_history", [])
    if gate_entry:
        workflow_history = workflow_history + [gate_entry]

    # ========================================
    # PARAMETER RESOLUTION CHECK (from input_writer via workflow_history)
    # ========================================
    # If input_writer flagged unresolved parameters, route back to architect
    # Extract from workflow_history instead of top-level state

    logger.debug("[DATA TRANSFER] Checking for parameter resolution requirement")

    # Extract from input_writer entries in workflow_history
    input_writer_entries = [e for e in workflow_history if e.get("node") == "input_writer"]
    requires_resolution = False
    unresolved = []
    guidance = ""
    available = []
    suggested = {}

    if input_writer_entries:
        last_input_writer = input_writer_entries[-1]
        details = last_input_writer.get("details", {})
        requires_resolution = details.get("requires_parameter_resolution", False)

        if requires_resolution:
            unresolved = details.get("unresolved_parameters", [])
            guidance = details.get("resolution_guidance", "")
            available = details.get("available_schema_params", [])
            suggested = details.get("suggested_params", {})

            logger.debug("[DATA TRANSFER] Parameter resolution required from workflow_history")
            logger.debug(f"[DATA TRANSFER] Extracted unresolved_parameters: {len(unresolved)} items")
            logger.debug(f"[DATA TRANSFER] Extracted available_schema_params: {len(available)} items")
            logger.debug(f"[DATA TRANSFER] Extracted suggested_params: {len(suggested)} mappings")

    logger.debug(f"[DATA TRANSFER] requires_parameter_resolution = {requires_resolution}")

    if requires_resolution:

        logger.warning(
            f"[Reviewer] Parameter resolution required - "
            f"{len(unresolved)} unresolved parameters"
        )

        # Check if we've exhausted retries for parameter resolution
        if retry_count >= max_retries:
            logger.error(
                f"[Reviewer] Max retries ({max_retries}) exceeded for parameter resolution - "
                f"terminating with {len(unresolved)} unresolved parameters"
            )
            taxonomy = _build_final_error_taxonomy(
                category="parameter_resolution_max_retries",
                reason="max_retries_exceeded_parameter_resolution",
                retry_count=retry_count,
                max_retries=max_retries,
                unresolved_parameters=unresolved,
            )

            history_entry = {
                "node": "reviewer",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "parameter_resolution_max_retries",
                "iteration": iteration,
                "details": {
                    "status": "terminal",
                    "reason": "max_retries_exceeded_parameter_resolution",
                    "unresolved_parameters": unresolved,
                    "retry_count": retry_count,
                    "max_retries": max_retries,
                    "final_error_taxonomy": taxonomy,
                }
            }

            return {
                "mode": "terminal",
                "error": f"Parameter resolution failed after {max_retries} retries: {[p[0] for p in unresolved]}",
                "errors_active": [f"Unresolved parameter: {p[0]}" for p in unresolved],
                "workflow_history": workflow_history + [history_entry],
                "reviewer_failure_category": taxonomy["category"],
                "final_error_taxonomy": taxonomy,
            }

        # Route back to architect with feedback
        logger.info(
            f"[Reviewer] Routing to architect for parameter re-mapping "
            f"(retry {retry_count + 1}/{max_retries})"
        )

        history_entry = {
            "node": "reviewer",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "parameter_resolution_retry",
            "iteration": iteration,
            "details": {
                "status": "retry",
                "reason": "unresolved_parameters",
                "unresolved_parameters": unresolved,
                "resolution_guidance": guidance,
                "available_schema_params_count": len(available),
                "suggested_params": suggested,
                "retry_count": retry_count + 1
            }
        }

        return {
            # Control flow - back to architect
            "mode": "retry",
            "retry_count": retry_count + 1,
            "iteration": iteration,

            # Feedback for architect re-planning (extracted from workflow_history)
            "parameter_resolution_feedback": {
                "unresolved_parameters": unresolved,
                "resolution_guidance": guidance,
                "available_schema_params": available,
                "suggested_params": suggested,
            },

            # Error tracking
            "errors_active": [f"Unresolved parameter: {p[0]}" for p in unresolved],

            # Audit trail
            "workflow_history": workflow_history + [history_entry]
        }

    # ========================================
    # COMPILATION FAILURE CHECK (terminal condition)
    # ========================================

    if state.get("compilation_failed"):
        logger.error("Compilation failed in previous iteration - terminating")
        taxonomy = _build_final_error_taxonomy(
            category="compilation_failed",
            reason="compilation_failed",
            retry_count=retry_count,
            max_retries=max_retries,
        )
        return {
            "mode": "terminal",
            "error": "Compilation failed - cannot proceed",
            "errors_active": ["Compilation failed for selected case"],
            "workflow_history": workflow_history,
            "reviewer_failure_category": taxonomy["category"],
            "final_error_taxonomy": taxonomy,
        }

    # ========================================
    # PLAN VALIDATION
    # ========================================

    # Get plan from canonical path (workflow_history) with fallback to state
    plan = get_architect_plan(state)

    # Handle no plan case
    if not plan:
        logger.warning("[WARN] No plan to review (skipping)")
        return skip_review(state, "no plan")

    # Get previous errors for progress tracking
    errors_previous = state.get("errors_active", [])
    errors_all_found = state.get("errors_found", [])
    errors_all_fixed = state.get("errors_fixed", [])

    # Phase 1: Review the plan
    logger.info("Reviewing plan...")
    orchestrator = ReviewerOrchestrator(config)
    validation_started_at = time.perf_counter()
    validation_result = orchestrator.validate_plan(plan)
    validator_latency_ms = round((time.perf_counter() - validation_started_at) * 1000.0, 3)

    # Convert ValidationResult to structured format
    approved = validation_result.mode == "proceed"
    errors_current = [v.message for v in validation_result.violations if v.severity == "error"]
    warnings = [v.message for v in validation_result.violations if v.severity == "warning"]
    schema_missing = any(v.rule_name in {"SchemaMissing", "SchemaLoadError"} for v in validation_result.violations)
    solver_unknown = any(
        v.rule_name in {"SolverRegistry", "SchemaValidation"} and "unknown solver" in v.message.lower()
        for v in validation_result.violations
    )
    solver_name = None
    if plan.get("baseline"):
        solver_name = plan["baseline"].get("code_name") or plan["baseline"].get("code")
    if schema_missing:
        repo_root = None
        if solver_name and hasattr(config, "repositories"):
            repo_root = config.repositories.get(solver_name)
        solver_flag = solver_name.lower() if solver_name else "<solver>"
        repo_arg = repo_root or "<path-to-repo>"
        schema_cmd = f"python database/scripts/build_schema.py {repo_arg} --solver {solver_flag}"
        schema_msg = f"Schema missing for {solver_name or 'unknown solver'}. Run: {schema_cmd}"
        errors_current.append(schema_msg)

    # If schema errors exist, route through parameter resolution flow
    schema_errors = [v for v in validation_result.violations if v.rule_name == "SchemaExistence"]
    if schema_errors:
        baseline = plan.get("baseline", {})
        baseline_inputs = _load_baseline_inputs_content(plan)
        baseline_params = set()
        if isinstance(baseline_inputs, dict):
            for key, value in baseline_inputs.items():
                if isinstance(value, dict):
                    for subkey in value.keys():
                        dotted_key = f"{key}.{subkey}"
                        baseline_params.add(dotted_key)
                        baseline_params.add(dotted_key.replace(".", "_"))
                else:
                    baseline_params.add(key)
                    baseline_params.add(key.replace(".", "_"))
        baseline_schema_messages = []
        filtered_schema_errors = []
        for v in schema_errors:
            param = v.parameter or ""
            if param and (param in baseline_params or param.replace("_", ".") in baseline_params):
                baseline_schema_messages.append(v.message)
                continue
            filtered_schema_errors.append(v)
        if baseline_schema_messages:
            errors_current = [e for e in errors_current if e not in baseline_schema_messages]
        schema_errors = filtered_schema_errors
        solver_name = baseline.get("code_name") or baseline.get("code")
        mod_list = plan.get("modifications", [])
        mod_map = dict(mod_list) if isinstance(mod_list, list) else dict(mod_list.items())
        unresolved = []
        for v in schema_errors:
            param = v.parameter or ""
            if not param:
                continue
            if param in baseline_params:
                continue
            unresolved.append((param, mod_map.get(param)))

        if unresolved and solver_name:
            try:
                from database.configs import discover_code_configs

                from src.services.config_model_factory import ConfigModelFactory
                code_registry = {c.code_name: c for c in discover_code_configs()}
                solver_config = code_registry.get(solver_name)
                if not solver_config:
                    raise ValueError(f"No solver config for {solver_name}")
                schema_path = ConfigModelFactory.resolve_schema_path(
                    solver_config,
                    config.amrex_agent_root / "database/schemas",
                    Path(config.repositories.get(solver_name, ".")),
                    runtime_config=config,
                )
                feedback = ConfigModelFactory.build_parameter_resolution_feedback(
                    unresolved_params=unresolved,
                    config_service=config,
                    solver_config=solver_config,
                    schema_path=schema_path,
                    build_config=plan.get("build_config", {})
                )
            except Exception as exc:
                logger.warning(f"Schema resolution feedback failed: {exc}")
                feedback = None

            if feedback:
                available_schema_params = set(feedback.get("available_schema_params", []))
                remap_mapping = feedback.get("remap_mapping", {})
                valid_remap_count = sum(
                    1 for target in remap_mapping.values()
                    if target in available_schema_params
                )
                remap_success_count = valid_remap_count
                next_retry = retry_count if remap_success_count else retry_count + 1
                last_schema_retry = next(
                    (
                        entry for entry in reversed(workflow_history)
                        if entry.get("node") == "reviewer"
                        and entry.get("action") == "parameter_resolution_retry"
                        and entry.get("details", {}).get("reason") == "schema_resolution"
                    ),
                    None
                )
                if last_schema_retry:
                    last_unresolved = last_schema_retry.get("details", {}).get("unresolved_parameters", [])
                    if last_unresolved == feedback["unresolved_parameters"]:
                        taxonomy = _build_final_error_taxonomy(
                            category="schema_resolution_stalled",
                            reason="schema_resolution_stalled",
                            retry_count=retry_count,
                            max_retries=max_retries,
                            unresolved_parameters=feedback["unresolved_parameters"],
                        )
                        history_entry = {
                            "node": "reviewer",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "action": "parameter_resolution_stalled",
                            "iteration": iteration,
                            "details": {
                                "status": "terminal",
                                "reason": "schema_resolution_stalled",
                                "unresolved_parameters": feedback["unresolved_parameters"],
                                "resolution_guidance": feedback["resolution_guidance"],
                                "available_schema_params_count": len(feedback["available_schema_params"]),
                                "suggested_params": feedback["suggested_params"],
                                "remap_mapping": remap_mapping,
                                "remap_success_count": remap_success_count,
                                "retry_count": retry_count,
                                "final_error_taxonomy": taxonomy,
                            }
                        }

                        return {
                            "mode": "terminal",
                            "error": (
                                "Parameter resolution stalled with unchanged unresolved parameters: "
                                f"{[p[0] for p in feedback['unresolved_parameters']]}"
                            ),
                            "errors_active": [f"Unresolved parameter: {p[0]}" for p in feedback["unresolved_parameters"]],
                            "workflow_history": workflow_history + [history_entry],
                            "reviewer_failure_category": taxonomy["category"],
                            "final_error_taxonomy": taxonomy,
                        }
                history_entry = {
                    "node": "reviewer",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "action": "parameter_resolution_retry",
                    "iteration": iteration,
                    "details": {
                        "status": "retry",
                        "reason": "schema_resolution",
                        "unresolved_parameters": feedback["unresolved_parameters"],
                        "resolution_guidance": feedback["resolution_guidance"],
                        "available_schema_params_count": len(feedback["available_schema_params"]),
                        "suggested_params": feedback["suggested_params"],
                        "remap_mapping": feedback.get("remap_mapping", {}),
                        "remap_success_count": remap_success_count,
                        "retry_count": next_retry
                    }
                }

                return {
                    "mode": "retry",
                    "retry_count": next_retry,
                    "iteration": iteration,
                    "parameter_resolution_feedback": {
                        "unresolved_parameters": feedback["unresolved_parameters"],
                        "resolution_guidance": feedback["resolution_guidance"],
                        "available_schema_params": feedback["available_schema_params"],
                        "suggested_params": feedback["suggested_params"],
                        "remap_mapping": feedback.get("remap_mapping", {}),
                        "remap_success_count": remap_success_count,
                    },
                    "errors_active": [f"Unresolved parameter: {p[0]}" for p in feedback["unresolved_parameters"]],
                    "workflow_history": workflow_history + [history_entry]
                }

    if not errors_current and not schema_missing and not solver_unknown:
        approved = True

    # Phase 2: Track error progress
    newly_fixed: list[str] = []
    newly_found: list[str] = []

    if iteration > 0:
        # Which previous errors were fixed?
        newly_fixed = [e for e in errors_previous if e not in errors_current]

        # Which errors are new?
        newly_found = [e for e in errors_current if e not in errors_all_found]

        # Update cumulative lists
        errors_all_found = list(set(errors_all_found + newly_found))
        errors_all_fixed = list(set(errors_all_fixed + newly_fixed))

        # Report progress
        if newly_fixed:
            logger.info(f"Fixed {len(newly_fixed)} errors: {newly_fixed}")
        if newly_found:
            logger.warning(f"New errors found: {newly_found}")

    # ========================================
    # PHASE 3: DECIDE MODE TRANSITION
    # ========================================

    if schema_missing:
        logger.error("Schema missing - terminating for manual schema build")
        next_mode = "terminal"
    elif approved:
        logger.info("Plan approved - proceeding to execution")
        next_mode = "proceed"
    else:
        # Check if we've hit max retries
        if retry_count >= max_retries:
            logger.error(f"Max retries ({max_retries}) exceeded - terminating")
            next_mode = "terminal"
        else:
            logger.warning(f"Plan rejected ({len(errors_current)} errors) - retry {retry_count + 1}/{max_retries}")
            if errors_current:
                logger.warning("Reviewer errors: %s", "; ".join(errors_current))
            next_mode = "retry"

    # ========================================
    # EXTRACT REJECTED ITEMS (FOR RETRY EXCLUSION)
    # ========================================
    # If plan is rejected, store what was rejected so Architect can exclude it on retry

    rejected_baseline = None
    rejected_inputs = None
    baseline_dir_rejected = False

    if not approved:
        rejected_baseline = plan.get("selected_case")
        # Try multiple sources for inputs file
        rejected_inputs = (
            state.get("inputs_file_path") or  # From input_writer
            state.get("used_inputs_file") or   # Tracked by input_writer
            plan.get("baseline", {}).get("inputs_file")  # From plan
        )

        if rejected_baseline:
            logger.debug(f"Rejected baseline: {rejected_baseline}")
        if rejected_inputs:
            logger.debug(f"Rejected inputs file: {rejected_inputs}")

        # Only reject baseline directory after retry threshold or explicit solver mismatch.
        retry_threshold = getattr(config, "baseline_switch_after_retries", 3)
        next_retry_count = retry_count + 1 if next_mode == "retry" else retry_count
        baseline_override = getattr(config, "baseline_override", None)
        if baseline_override:
            baseline_dir_rejected = False
        elif solver_unknown or not schema_missing and next_retry_count >= retry_threshold:
            baseline_dir_rejected = True

    # ========================================
    # RETRY GUIDANCE (Inputs vs Baseline)
    # ========================================
    unknown_param_count = 0
    persistent_unknown_count = 0
    has_schema_missing = schema_missing
    has_solver_unknown = solver_unknown

    def _extract_param_from_error(message: str) -> str | None:
        import re
        match = re.search(r"Parameter '([^']+)'", message or "")
        return match.group(1) if match else None

    unknown_param_count = sum(
        1 for v in validation_result.violations if v.rule_name == "SchemaExistence"
    )
    persistent_unknown_count = 0
    if errors_all_found:
        found_params = {
            _extract_param_from_error(e) for e in errors_all_found if e
        }
        fixed_params = {
            _extract_param_from_error(e) for e in errors_all_fixed if e
        }
        for v in validation_result.violations:
            if v.rule_name != "SchemaExistence":
                continue
            param_name = v.parameter or _extract_param_from_error(v.message)
            if param_name and param_name in found_params and param_name not in fixed_params:
                persistent_unknown_count += 1

    def _derive_retry_guidance(violations, rejected_inputs_file, rejected_baseline_case, baseline_dir_rejected_flag, solver_unknown_flag):
        nonlocal unknown_param_count, persistent_unknown_count, has_schema_missing, has_solver_unknown
        inputs_action = "keep"
        baseline_action = "keep"
        inputs_reason = None
        baseline_reason = None

        has_schema_missing = any(v.rule_name in {"SchemaMissing", "SchemaLoadError"} for v in violations)
        has_solver_unknown = solver_unknown_flag

        if rejected_inputs_file:
            inputs_action = "switch"
            inputs_reason = "review_rejected_inputs_file"
        elif unknown_param_count >= 3:
            inputs_action = "switch"
            inputs_reason = f"{unknown_param_count}_unknown_parameters"
        elif persistent_unknown_count >= 2:
            inputs_action = "switch"
            inputs_reason = f"{persistent_unknown_count}_persistent_unknown_parameters"

        baseline_override = getattr(config, "baseline_override", None)
        if baseline_override:
            baseline_action = "keep"
            baseline_reason = "baseline_override_locked"
        elif has_schema_missing:
            baseline_action = "keep"
            baseline_reason = "schema_missing_build_required"
        elif baseline_dir_rejected_flag:
            baseline_action = "switch"
            baseline_reason = "review_rejected_baseline_dir"
        elif rejected_baseline_case and has_solver_unknown or has_solver_unknown:
            baseline_action = "switch"
            baseline_reason = "schema_or_solver_mismatch"

        return {
            "inputs_base_action": inputs_action,
            "inputs_reason": inputs_reason,
            "baseline_base_action": baseline_action,
            "baseline_reason": baseline_reason,
        }

    retry_guidance = _derive_retry_guidance(
        validation_result.violations,
        rejected_inputs,
        rejected_baseline,
        baseline_dir_rejected,
        solver_unknown
    )

    final_error_taxonomy = None
    reviewer_failure_category = None
    if next_mode == "terminal" and retry_count >= max_retries:
        final_error_taxonomy = _build_final_error_taxonomy(
            category="review_validation_max_retries",
            reason="max_retries_exceeded_review_validation",
            retry_count=retry_count,
            max_retries=max_retries,
        )
        reviewer_failure_category = final_error_taxonomy["category"]

    # Optional LLM refinement (only when guidance is keep/keep)
    if (
        retry_guidance.get("inputs_base_action") == "keep"
        and retry_guidance.get("baseline_base_action") == "keep"
        and getattr(config, "retry_guidance_use_llm", False)
    ):
        try:
            from src.utils.metrics import metrics_context

            from database.configs import get_config_for_path

            from src.config import get_llm_client
            llm_client = get_llm_client(config)
            config_cls = get_config_for_path(str(baseline.get("local_path", "")))
            prompt = config_cls.get_prompt_templates().get("misc", {}).get("retry_guidance")
            if prompt:
                filled = prompt.format(
                    solver=baseline.get("code_name") or baseline.get("code") or "unknown",
                    baseline_case=plan.get("selected_case") or "unknown",
                    inputs_file=rejected_inputs or state.get("used_inputs_file") or "unknown",
                    errors_current="\n".join(errors_current) if errors_current else "none",
                    errors_all_found="\n".join(errors_all_found) if errors_all_found else "none",
                    errors_all_fixed="\n".join(errors_all_fixed) if errors_all_fixed else "none",
                    analysis_issues="none",
                )
                try:
                    import json
                    from pydantic import BaseModel, Field
                    from src.utils.llm_calls import LLMCallSpec, call_llm

                    class RetryGuidance(BaseModel):
                        inputs_base_action: str = Field(description="keep or switch")
                        baseline_base_action: str = Field(description="keep or switch")
                        rationale: str | None = None

                    spec = LLMCallSpec(
                        model=config.llm_model,
                        response_model=RetryGuidance,
                        messages=[{"role": "user", "content": filled}],
                        temperature=0.0,
                        max_retries=2,
                        purpose="retry_guidance",
                        template_name="retry_guidance",
                        template_source="solver_config.misc",
                    )
                    with metrics_context("reviewer", node="reviewer", iteration=iteration):
                        result = call_llm(llm_client, spec, config=config)
                    if hasattr(result, "inputs_base_action"):
                        retry_guidance.update({
                            "inputs_base_action": result.inputs_base_action or "keep",
                            "baseline_base_action": result.baseline_base_action or "keep",
                            "inputs_reason": result.rationale,
                            "baseline_reason": result.rationale,
                        })
                    else:
                        content = result.choices[0].message.content.strip()
                        parsed = json.loads(content)
                        if isinstance(parsed, dict):
                            retry_guidance.update({
                                "inputs_base_action": parsed.get("inputs_base_action", "keep"),
                                "baseline_base_action": parsed.get("baseline_base_action", "keep"),
                                "inputs_reason": parsed.get("rationale"),
                                "baseline_reason": parsed.get("rationale"),
                            })
                except Exception as exc:
                    logger.debug(f"Retry guidance LLM unavailable: {exc}")
        except Exception as exc:
            logger.debug(f"Retry guidance LLM unavailable: {exc}")

    # ========================================
    # WORKFLOW HISTORY ENTRY (CANONICAL PATH)
    # ========================================
    # Store complete review results in workflow_history.details

    logger.debug("[REVIEWER NODE] Creating history entry")
    logger.debug(f"[REVIEWER NODE] validation_result.available_schema_params: {len(validation_result.available_schema_params)} items")
    if validation_result.available_schema_params:
        logger.debug(f"[REVIEWER NODE] Sample schema params: {validation_result.available_schema_params[:10]}")

    try:
        from src.utils.metrics import metrics_collector

        validation_metrics = {
            "validator_latency_ms": validator_latency_ms,
            "validator_outcome": validation_result.mode,
            "review_outcome": "approved" if approved else "rejected",
            "transition_mode": next_mode,
            "error_count": len(errors_current),
            "warning_count": len(warnings),
            "violation_count": len(validation_result.violations),
            "unknown_param_count": unknown_param_count,
            "persistent_unknown_count": persistent_unknown_count,
            "schema_missing": schema_missing,
            "solver_unknown": solver_unknown,
        }
        metrics_collector.record_event(
            "validation_metrics",
            validation_metrics,
            stage="reviewer",
            node="reviewer",
            iteration=iteration,
        )
        metrics_summary = metrics_collector.summarize_stage("reviewer", iteration=iteration)
    except Exception:
        metrics_summary = {}

    history_entry = {
        "node": "reviewer",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": "validation_completed",
        "iteration": iteration,
        "details": {
            # Review results (computation output)
            "status": "approved" if approved else "rejected",
            "errors": errors_current,
            "warnings": warnings,
            "validation_passed": approved,
            "error_count": len(errors_current),
            "warning_count": len(warnings),
            # Progress tracking
            "newly_fixed": newly_fixed,
            "newly_found": newly_found,
            "errors_all_found": errors_all_found,
            "errors_all_fixed": errors_all_fixed,
            # Metadata
            "suggested_fixes": [v.suggested_fix for v in validation_result.violations if v.suggested_fix],
            "available_schema_params": validation_result.available_schema_params,
            "retry_guidance": retry_guidance,
            "baseline_dir_rejected": baseline_dir_rejected,
            "plan_rejected_baseline": rejected_baseline,
            "plan_rejected_inputs_file": rejected_inputs,
        }
    }
    if final_error_taxonomy:
        history_entry["details"]["final_error_taxonomy"] = final_error_taxonomy
        history_entry["details"]["reviewer_failure_category"] = reviewer_failure_category
    if metrics_summary:
        history_entry["details"]["metrics"] = metrics_summary

    new_history = workflow_history + [history_entry]

    # ========================================
    # RETURN STATE UPDATES (LangGraph PATTERN)
    # ========================================
    # Return dict of updates, not modified state

    updates = {
        # === UTILITY FLAGS ===
        "mode": next_mode,
        "iteration": iteration,
        "retry_count": retry_count + 1 if next_mode == "retry" else retry_count,

        # === AUDIT TRAIL ===
        "workflow_history": new_history,

        # === PRAGMATIC CONVENIENCE COPIES ===
        # For performance/debugging (optional, matches workflow_history.details)
        "review": {
            "status": "approved" if approved else "rejected",
            "errors": errors_current,
            "warnings": warnings,
            "rejected_baseline": rejected_baseline if baseline_dir_rejected else None,  # For retry exclusion
            "rejected_inputs_file": rejected_inputs,  # For retry exclusion
            "suggested_fixes": [v.suggested_fix for v in validation_result.violations if v.suggested_fix]
        },
        "review_analysis": {
            "mode": validation_result.mode,
            "violations": [v.__dict__ for v in validation_result.violations],
            "summary": validation_result.summary
        },
        "retry_guidance": retry_guidance,
        "errors_active": errors_current,
        "errors_found": errors_all_found,
        "errors_fixed": errors_all_fixed,
        "suggested_fixes": [v.suggested_fix for v in validation_result.violations if v.suggested_fix],
        "available_schema_params": validation_result.available_schema_params,
        "baseline_dir_rejected": baseline_dir_rejected,
        "plan_rejected_baseline": rejected_baseline,
        "plan_rejected_inputs_file": rejected_inputs,
        "reviewer_failure_category": reviewer_failure_category,
        "final_error_taxonomy": final_error_taxonomy,
    }

    logger.info(f"Review complete: {next_mode} (errors: {len(errors_current)})")
    logger.info("-" * 80)
    logger.info("Reviewer node complete")
    logger.info("-" * 80)
    return updates


# Export for LangGraph
__all__ = ['reviewer_node']
