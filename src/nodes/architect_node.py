"""
Architect Node: State Adapter / Service Integration / Feedback Loop / Iteration Safety / Workflow History Logging: Architect Node Complete Implementation.

LangGraph node wrapper for ArchitectService.
Handles:
- State extraction/validation (9a)
- Service orchestration (9b)
- Feedback loop for retries (9c - Reflexion Pattern)
- Parameter resolution feedback (9c-ii - Schema mismatch handling)
- Iteration safety (9d - Loop prevention)
- Workflow history logging (9e - Observability)
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import GraphState
from src.services.architect import ArchitectService
from src.utils.gate import GateManager, run_preconfirm_gate

logger = logging.getLogger(__name__)


def architect_node(state: GraphState) -> dict[str, Any]:
    """
    Orchestrate simulation planning for the workflow graph.

    Call context: LangGraph node entry point.

    Parameters
    ----------
    state : GraphState
        Current workflow state containing configuration and prompt data.

    Returns
    -------
    dict
        State updates with selected case, modifications, and workflow metadata.
    """
    logger.info("=" * 80)
    logger.info("Starting Architect node")
    logger.info("=" * 80)

    # ========================================
    # COMPONENT 9d: ITERATION SAFETY
    # ========================================

    # 1. Extract Safety State
    iteration = state.get("iteration", 0)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)  # Default to 3 if missing
    mode = state.get("mode", "initial")

    # 2. Increment Counters
    # Always increment total iteration (steps taken)
    new_iteration = iteration + 1
    new_retry_count = retry_count

    # Increment retry count only if we are in a retry loop
    if mode == "retry":
        new_retry_count = retry_count + 1
        logger.info(f"Retry {new_retry_count}/{max_retries}")

    # 3. Enforce Termination Limits
    if new_retry_count > max_retries:
        error_msg = f"Max retries ({max_retries}) exceeded. Stopping infinite loop."
        logger.error(error_msg)

        # Return fail state immediately - do not call service
        return {
            "mode": "fail",
            "error": error_msg,
            "iteration": new_iteration,
            "retry_count": new_retry_count,
            "loop_count": new_iteration  # Legacy compatibility
        }

    # ========================================
    # COMPONENT 9a: STATE VALIDATION
    # ========================================

    config = state.get("config")
    if not config:
        logger.error("Missing required 'config' in state")
        raise ValueError("Architect Node requires 'config' in state")

    # Handle backward compatibility for prompt
    prompt = state.get("prompt") or state.get("user_requirement")
    if not prompt:
        logger.error("Missing required 'prompt' or 'user_requirement' in state")
        raise ValueError("Architect Node requires 'prompt' or 'user_requirement' in state")

    # ========================================
    # COMPONENT 9c: FEEDBACK PREPARATION
    # ========================================

    previous_feedback: dict[str, Any] | None = None
    parameter_resolution_feedback: dict[str, Any] | None = None  # Initialize for both modes

    if mode == "retry":
        logger.debug("Retry mode detected - extracting feedback")

        # Extract feedback from workflow_history (canonical source)
        workflow_history_temp = state.get("workflow_history", [])

        # Get reviewer entries for schema params
        reviewer_entries = [e for e in workflow_history_temp if e.get("node") == "reviewer"]
        logger.debug(f"[DATA TRANSFER] Found {len(reviewer_entries)} reviewer entries")

        available_from_history = []
        if reviewer_entries:
            last_reviewer = reviewer_entries[-1]
            available_from_history = last_reviewer.get("details", {}).get("available_schema_params", [])
            logger.debug(f"[DATA TRANSFER] Extracted from reviewer: {len(available_from_history)} schema params")
            if available_from_history:
                logger.debug(f"[DATA TRANSFER] Sample params: {available_from_history[:10]}")

        # ----------------------------------------
        # 9c-ii: CHECK FOR PARAMETER RESOLUTION FEEDBACK FROM INPUT_WRITER
        # ----------------------------------------
        # Extract from workflow_history instead of top-level state
        parameter_resolution_feedback = None
        input_writer_entries = [e for e in workflow_history_temp if e.get("node") == "input_writer"]

        if input_writer_entries:
            last_input_writer = input_writer_entries[-1]
            details = last_input_writer.get("details", {})

            if details.get("requires_parameter_resolution"):
                unresolved = details.get("unresolved_parameters", [])
                guidance = details.get("resolution_guidance", "")
                available = details.get("available_schema_params", [])
                suggested = details.get("suggested_params", {})

                logger.warning(
                    f"Parameter resolution feedback from workflow_history - "
                    f"{len(unresolved)} parameters need remapping"
                )

                # Log each unresolved parameter with suggestions
                for param_name, value in unresolved:
                    suggestions = suggested.get(param_name, [])[:5]
                    logger.debug(
                        f"  - '{param_name}' (value: {value}) → "
                        f"suggestions: {suggestions if suggestions else 'none'}"
                    )

                parameter_resolution_feedback = {
                    "unresolved_parameters": unresolved,
                    "resolution_guidance": guidance,
                    "available_schema_params": available,
                    "suggested_params": suggested,
                }
                logger.debug(f"[DATA TRANSFER] Built parameter_resolution_feedback from workflow_history with {len(unresolved)} unresolved params")

        # If reviewer provided structured feedback, prefer it
        if not parameter_resolution_feedback and state.get("parameter_resolution_feedback"):
            parameter_resolution_feedback = state.get("parameter_resolution_feedback")
            logger.debug(
                "[DATA TRANSFER] Using parameter_resolution_feedback from reviewer state "
                f"({len(parameter_resolution_feedback.get('unresolved_parameters', []))} unresolved)"
            )

        # Fallback: extract parameter resolution feedback from reviewer history
        if not parameter_resolution_feedback:
            reviewer_entries = [e for e in workflow_history_temp if e.get("node") == "reviewer"]
            if reviewer_entries:
                last_reviewer = reviewer_entries[-1]
                details = last_reviewer.get("details", {})
                unresolved = details.get("unresolved_parameters", [])
                suggested = details.get("suggested_params", {})
                available = details.get("available_schema_params", [])
                remap_mapping = details.get("remap_mapping", {})
                if unresolved:
                    parameter_resolution_feedback = {
                        "unresolved_parameters": unresolved,
                        "resolution_guidance": details.get("resolution_guidance", ""),
                        "available_schema_params": available,
                        "suggested_params": suggested,
                        "remap_mapping": remap_mapping,
                    }
                    logger.debug(
                        "[DATA TRANSFER] Built parameter_resolution_feedback from reviewer history "
                        f"({len(unresolved)} unresolved)"
                    )

        # ----------------------------------------
        # 9c-i: STANDARD ERROR FEEDBACK (from reviewer)
        # ----------------------------------------

        errors = state.get("errors_active", [])
        review = state.get("review", {})
        rejected_case = review.get("rejected_baseline") or state.get("selected_case")
        rejected_inputs = review.get("rejected_inputs_file")
        retry_guidance = state.get("retry_guidance", {}) or {}

        if errors:
            previous_feedback = {
                "errors": errors,
                "rejected_baseline": rejected_case,
                "rejected_inputs_file": rejected_inputs,
                "retry_guidance": retry_guidance,
                "retry_count": retry_count
            }

            logger.debug(
                f"Feedback: {len(errors)} errors, rejected baseline: {rejected_case}, inputs: {rejected_inputs}"
            )

            # ----------------------------------------
            # 9c-iii: CONVERT SCHEMA ERRORS TO PARAMETER RESOLUTION FEEDBACK
            # ----------------------------------------
            # If reviewer found schema errors but we don't have structured feedback,
            # convert the error messages to parameter_resolution_feedback format
            if not parameter_resolution_feedback:
                import re
                schema_errors = [e for e in errors if "not found in source code schema" in e.lower()]

                if schema_errors:
                    unresolved = []
                    for error in schema_errors:
                        match = re.search(r"Parameter '([^']+)'", error)
                        if match:
                            param_name = match.group(1)
                            unresolved.append((param_name, "unknown"))

                    if unresolved:
                        parameter_resolution_feedback = {
                            "unresolved_parameters": unresolved,
                            "resolution_guidance": "Use exact parameter names from the baseline inputs file",
                            "available_schema_params": available_from_history,
                            "suggested_params": {},
                        }
                        logger.debug(f"[DATA TRANSFER] Built parameter_resolution_feedback from {len(unresolved)} schema errors")
                        logger.debug(f"Built parameter_resolution_feedback from {len(unresolved)} schema errors")

        else:
            if not parameter_resolution_feedback:
                logger.warning("Retry mode but no errors_active or parameter_resolution_feedback in state")
    else:
        logger.debug(f"Mode: {mode} (initial planning)")

    # Optional solver hint
    selected_solvers = state.get("selected_solvers")
    solver_hint = None
    if selected_solvers:
        solver_hint = selected_solvers[0][0] if selected_solvers else None
        logger.debug(f"Using solver hint: {solver_hint}")

    # ========================================
    # COMPONENT 9b: SERVICE ORCHESTRATION
    # ========================================

    try:
        # Initialize EmbeddingService via factory (provides singleton + caching)
        from src.services.embedding_service_factory import get_embedding_service
        embedding_service = get_embedding_service(config)
        logger.debug(f"EmbeddingService initialized: {embedding_service is not None}")
        logger.debug(f"Embeddings available: {embedding_service.embeddings is not None}")

        # Pass embedding service to ArchitectService for Level0Searcher initialization (RAG-based planning)
        service = ArchitectService(config, embedding_service=embedding_service)
        logger.debug(f"ArchitectService instantiated with RAG support: {service.level0_searcher is not None}")
    except Exception as e:
        logger.exception("Failed to instantiate services")
        return {
            "error": f"Service instantiation failed: {str(e)}",
            "mode": "fail",
            "iteration": new_iteration,
            "retry_count": new_retry_count
        }

    # ========================================
    # COMPONENT 9c: BUILD EXCLUSION LISTS
    # ========================================

    # Accumulate excluded cases across retries
    excluded_cases = state.get("excluded_cases", [])
    excluded_inputs_files = state.get("excluded_inputs_files", [])

    if mode == "retry" and previous_feedback:
        rejected_case = previous_feedback.get("rejected_baseline")
        rejected_inputs = previous_feedback.get("rejected_inputs_file")
        retry_guidance = previous_feedback.get("retry_guidance", {}) or {}

        if rejected_case and rejected_case not in excluded_cases:
            excluded_cases.append(rejected_case)
            logger.debug(f"Excluding baseline: {rejected_case}")

        if rejected_inputs and rejected_inputs not in excluded_inputs_files:
            excluded_inputs_files.append(rejected_inputs)
            logger.debug(f"Excluding inputs file: {rejected_inputs}")

        if retry_guidance.get("baseline_base_action") == "switch" and rejected_case:
            if rejected_case not in excluded_cases:
                excluded_cases.append(rejected_case)
            logger.debug(f"Retry guidance suggests switching baseline: {rejected_case}")

    logger.debug(f"Total exclusions: {len(excluded_cases)} cases, {len(excluded_inputs_files)} inputs files")

    try:
        # Execute planning using strategy dispatcher
        # This calls create_plan_rag() or create_plan() based on config.indexing_strategy
        # and normalizes the output to canonical format
        plan_result = service.execute_planning(
            user_prompt=prompt,
            prefer_quality="excellent",
            excluded_cases=excluded_cases,
            excluded_inputs_files=excluded_inputs_files,
            parameter_resolution_feedback=parameter_resolution_feedback,  # NEW: pass to service
        )
        logger.debug(f"[DATA TRANSFER] Called architect service with feedback={parameter_resolution_feedback is not None}")

        logger.info(f"Plan created: {plan_result.selected_case}")

    except Exception as e:
        logger.exception(f"Architect planning failed: {e}")
        return {
            "error": f"Planning failed: {str(e)}",
            "mode": "fail",
            "iteration": new_iteration,
            "retry_count": new_retry_count
        }

    preconfirm_action = "proceed"
    preconfirm_selection = None
    gate_entry = None

    gate_manager = GateManager(
        strategy=getattr(config, "gate_strategy", "auto") or "auto",
        gate_points=getattr(config, "gate_points", []) or [],
    )
    decision_gate_entries = []
    allowed_gate_points = set(getattr(config, "gate_points", []) or [])
    if (not allowed_gate_points or "solver" in allowed_gate_points) and gate_manager.should_gate("solver"):
        decision = gate_manager.present_gate(
            gate_point="solver",
            selected=plan_result.selected_solver,
            confidence=plan_result.baseline_confidence or 0.0,
            reasoning=plan_result.reasoning,
            evidence={"selected_case": plan_result.selected_case},
            alternatives=[],
        )
        if decision.user_action == "modified":
            manual_selection = (decision.user_modification or {}).get("manual_selection")
            if manual_selection and manual_selection != plan_result.selected_solver:
                gate_history_entry = {
                    "node": "preconfirm_gate",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "action": "retry",
                    "iteration": new_iteration,
                    "details": {
                        "gate_node": "solver",
                        "selection": {"value": manual_selection},
                        "reason": "solver_override",
                    },
                }
                plan_result.selected_solver = manual_selection
                return {
                    "mode": "retry",
                    "iteration": new_iteration,
                    "retry_count": new_retry_count,
                    "selected_solver": manual_selection,
                    "error": "Solver override at gate; replan required.",
                    "workflow_history": state.get("workflow_history", []) + [gate_history_entry],
                    "loop_count": new_iteration,
                }
        decision_gate_entries.append(
            {
                "node": "preconfirm_gate",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": decision.user_action,
                "iteration": new_iteration,
                "details": {
                    "gate_node": "solver",
                    "selection": {"value": decision.selected_option},
                    "reason": "decision_gate",
                },
            }
        )
        if decision.user_modification:
            decision_gate_entries[-1]["details"]["user_modification"] = decision.user_modification

    if (not allowed_gate_points or "baseline" in allowed_gate_points) and gate_manager.should_gate("baseline"):
        decision = gate_manager.present_gate(
            gate_point="baseline",
            selected=plan_result.selected_case,
            confidence=plan_result.baseline_confidence or 0.0,
            reasoning=plan_result.reasoning,
            evidence={"candidate_count": len(plan_result.case_candidates or [])},
            alternatives=[],
        )
        if decision.user_action == "modified":
            manual_selection = (decision.user_modification or {}).get("manual_selection")
            if manual_selection:
                plan_result.selected_case = manual_selection
        decision_gate_entries.append(
            {
                "node": "preconfirm_gate",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": decision.user_action,
                "iteration": new_iteration,
                "details": {
                    "gate_node": "baseline",
                    "selection": {"value": decision.selected_option},
                    "reason": "decision_gate",
                },
            }
        )
        if decision.user_modification:
            decision_gate_entries[-1]["details"]["user_modification"] = decision.user_modification

    if (not allowed_gate_points or "modifications" in allowed_gate_points) and gate_manager.should_gate("modifications"):
        decision = gate_manager.present_gate(
            gate_point="modifications",
            selected=plan_result.selected_case,
            confidence=plan_result.baseline_confidence or 0.0,
            reasoning=plan_result.reasoning,
            evidence={"modifications": plan_result.modifications},
            alternatives=[],
            current_parameters=dict(plan_result.modifications),
            resource_context={
                "config": config,
                "solver_name": plan_result.selected_solver,
            },
        )
        if decision.user_action == "modified":
            modifications = (decision.user_modification or {}).get("parameters")
            if modifications:
                mods_dict = dict(plan_result.modifications)
                mods_dict.update(modifications)
                plan_result.modifications = list(mods_dict.items())
        decision_gate_entries.append(
            {
                "node": "preconfirm_gate",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": decision.user_action,
                "iteration": new_iteration,
                "details": {
                    "gate_node": "modifications",
                    "selection": {"value": decision.selected_option},
                    "reason": "decision_gate",
                },
            }
        )
        if decision.user_modification:
            decision_gate_entries[-1]["details"]["user_modification"] = decision.user_modification

    if getattr(config, "preconfirm_gate", False) is True:
        auto_approve = getattr(config, "preconfirm_gate_auto_approve", False) is True
        confidence = plan_result.baseline_confidence
        options = _build_baseline_options(plan_result)
        summary_lines = [
            f"Iteration: {new_iteration} (retry {new_retry_count})",
            f"Solver: {plan_result.selected_solver}",
            f"Selected case: {plan_result.selected_case}",
            f"Baseline confidence: {confidence if confidence is not None else 'n/a'}",
            f"Planned modifications: {len(plan_result.modifications)}",
            f"Indexing strategy: {plan_result.indexing_strategy}",
            f"Candidate baselines: {len(plan_result.case_candidates or [])}",
            "Note: Selecting an alternative keeps the current modification plan.",
        ]
        gate_result = run_preconfirm_gate(
            node_name="architect",
            summary_lines=summary_lines,
            options=options,
            enabled=getattr(config, "preconfirm_gate", False) is True,
            allow_cancel=True,
            auto_approve=auto_approve,
        )
        preconfirm_action = gate_result["action"]
        preconfirm_selection = gate_result.get("selection")
        gate_entry = gate_result.get("history_entry")
        if gate_entry:
            gate_entry["iteration"] = new_iteration
        if preconfirm_selection:
            plan_result.selected_case = preconfirm_selection["case"]
            if preconfirm_selection.get("score") is not None:
                plan_result.baseline_confidence = preconfirm_selection["score"]
            plan_result.reasoning = (
                f"{plan_result.reasoning}\n"
                f"User selected alternative baseline at pre-confirm gate: {plan_result.selected_case}"
            )

    # ========================================
    # COMPONENT 9e: WORKFLOW HISTORY LOGGING (CANONICAL PATH)
    # ========================================

    # Get current history or initialize empty list
    workflow_history = state.get("workflow_history", [])
    if decision_gate_entries:
        workflow_history = workflow_history + decision_gate_entries

    # Extract key metrics from plan (now SimulationPlan object)
    current_mods = plan_result.modifications
    current_reasoning = plan_result.reasoning
    selected_case = plan_result.selected_case

    # Compute indexing calls count (how many search operations performed)
    # For simple strategy: 1 (single FAISS search)
    # For hierarchical: 3 (L0, L1, L2 searches)
    indexing_strategy = plan_result.indexing_strategy
    if indexing_strategy == "hierarchical":
        indexing_calls = 3  # L0 + L1 + L2
    elif indexing_strategy == "override_static":
        indexing_calls = 0  # No retrieval calls
    else:
        indexing_calls = 1  # Single search

    # Compute baseline metadata (Fix #1 - needed by runner)
    code_name = plan_result.selected_solver
    repo_path = config.repositories.get(code_name) if hasattr(config, 'repositories') else None

    baseline = None
    if repo_path and selected_case:
        baseline = {
            "code_name": code_name,
            "repo_path": str(repo_path),
            "case_path": selected_case,
            "local_path": str(Path(repo_path) / selected_case)
        }

    # Determine action type based on feedback
    if parameter_resolution_feedback:
        action = "plan_created_with_parameter_remapping"
    elif mode == "retry":
        action = "plan_created_retry"
    else:
        action = "plan_created"

    # Create structured history entry (Fix #7 - canonical format with complete computation output)
    # CRITICAL: Store FULL computation output here, not snippets or counts
    history_entry = {
        "node": "architect",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "iteration": new_iteration,
        "details": {
            # Full computation output (canonical path - source of truth)
            "selected_case": selected_case,
            "selected_solver": code_name,   # Solver selection (from registry)
            "modifications": current_mods,  # Full list, NOT count
            "reasoning": current_reasoning,  # Full text, NOT snippet
            "baseline": baseline,            # Full metadata [FIX #1]
            # Execution metadata for comparative testing
            "indexing_strategy": indexing_strategy,
            "indexing_calls_count": indexing_calls,
            # Performance metrics
            "confidence_score": plan_result.baseline_confidence,
            # Parameter resolution context (if applicable)
            "parameter_resolution_applied": parameter_resolution_feedback is not None,
            "remapped_parameters": (
                [p[0] for p in parameter_resolution_feedback.get("unresolved_parameters", [])]
                if parameter_resolution_feedback else []
            ),
        }
    }

    # Append to history (immutable - create new list)
    new_history = workflow_history + [history_entry]
    if gate_entry:
        gate_entry["details"]["selection"] = preconfirm_selection
        gate_entry["details"]["options_count"] = len(_build_baseline_options(plan_result))
        new_history = new_history + [gate_entry]

    logger.debug(f"History entry appended: {history_entry['action']} at iteration {new_iteration}")
    if baseline:
        logger.debug(f"Baseline metadata computed: {baseline['local_path']}")
    else:
        if not repo_path:
            logger.warning(f"Repository not found for code: {code_name}")
        if not selected_case:
            logger.warning("Selected case is empty")

    # ========================================
    # OUTPUT MAPPING (DUAL-PATH VALIDATION MODEL)
    # ========================================
    # CANONICAL PATH (PRIMARY): workflow_history[-1]['details'] has source of truth
    # PRAGMATIC PATH (OPTIONAL): top-level state has convenience copies
    # Both paths include: selected_case, modifications, reasoning, baseline

    # Combine plan fields into canonical "plan" dict (pragmatic convenience copy)
    # Convert SimulationPlan to dict for state storage
    plan_dict = plan_result.to_dict()
    # Override baseline with computed metadata
    plan_dict["baseline"] = baseline

    updates = {
        # === UTILITY FLAGS (REQUIRED FOR CONTROL FLOW) ===
        "mode": "proceed",              # Control flow (Reviewer will override)
        "iteration": new_iteration,     # Total steps taken (all nodes)
        "retry_count": new_retry_count, # Reflexion loop count (architect retries only)
        "preconfirm_action": preconfirm_action,

        # === EXCLUSION STATE (FOR RETRY LOOP) ===
        "excluded_cases": excluded_cases,           # Cumulative excluded baselines
        "excluded_inputs_files": excluded_inputs_files,  # Cumulative excluded inputs

        # === AUDIT TRAIL (REQUIRED) ===
        # workflow_history[-1]['details'] contains canonical computation output
        "workflow_history": new_history,

        # === PRAGMATIC CONVENIENCE COPIES (OPTIONAL) ===
        # For performance/ease-of-use - must match workflow_history[-1]['details']
        "plan": plan_dict,              # Combined plan for Reviewer/visualization
        "baseline": baseline,           # For runner to find executable
        "selected_case": selected_case, # For reviewer/downstream convenience
        "selected_solver": code_name,   # Solver selection for validation/downstream
        "modifications": current_mods,  # For review/visualization
        "reasoning": current_reasoning, # For visualization
        "case_candidates": plan_result.case_candidates or [],  # For visualization
        "baseline_confidence": plan_result.baseline_confidence,  # For visualization

        # === STATE RESET ===
        "errors_active": [],            # Clear errors from previous iteration

        # === LEGACY COMPATIBILITY ===
        "loop_count": new_iteration,    # Deprecated, kept for backward compatibility
    }

    # Add timestamp if provided
    if hasattr(plan_result, "timestamp") and plan_result.timestamp:
        updates["timestamp_plan_created"] = plan_result.timestamp

    if preconfirm_action == "cancel":
        updates["mode"] = "terminal"
        updates["error"] = "User canceled at pre-confirm gate."

    logger.info(f"Iteration {new_iteration}, Retry {new_retry_count}, Mode: proceed")
    logger.info("-" * 80)
    logger.info("Architect node complete")
    logger.info("-" * 80)

    # Return updates dict (LangGraph will merge into state)
    return updates


def _build_baseline_options(plan_result, max_options: int = 4) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    seen = set()

    def add_option(case: str | None, score: float | None) -> None:
        if not case or case in seen:
            return
        label = f"{case}"
        if score is not None:
            label += f" (score {score:.2f})"
        if case == plan_result.selected_case:
            label += " [current]"
        options.append({"case": case, "score": score, "label": label, "value": case})
        seen.add(case)

    add_option(plan_result.selected_case, plan_result.baseline_confidence)
    for candidate in plan_result.case_candidates or []:
        case = candidate.get("case") or candidate.get("metadata", {}).get("repo_path")
        add_option(case, candidate.get("score"))
        if len(options) >= max_options:
            break

    return options
