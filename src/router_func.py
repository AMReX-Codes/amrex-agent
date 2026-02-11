"""
Router functions to determine next node in workflow.

Similar to: foamagent/src/router_func.py

These functions examine the GraphState and decide which node to execute next.
Used by LangGraph's conditional_edges.

Phase 2: Simplified routing using error tracking.
- Nodes update iteration (not router)
- Uses errors_active for termination logic

Phase 4 Workflow Routes (Strategy 3):
1. Architect → Reviewer (pre-execution validation)
2. Reviewer → Input Writer (approved) OR Architect (rejected, retry)
3. Input Writer → Runner (always)
4. Runner → Analysis (always - Phase 4 decision)
5. Analysis → Visualization (passed) OR Reviewer (failed)
6. Visualization → END (always)
"""

from src.models import GraphState
from langgraph.graph import END


import logging

logger = logging.getLogger(__name__)


def _should_router_gate(state: GraphState, gate_point: str) -> bool:
    config = state.get("config")
    if not config:
        return False
    strategy = getattr(config, "router_gate_strategy", "off") or "off"
    gate_points = set(getattr(config, "router_gate_points", []) or [])
    if strategy == "off":
        return False
    if strategy == "terminal":
        return gate_point in gate_points if gate_points else True
    if strategy == "selective":
        return gate_point in gate_points
    return False


def _maybe_route_with_gate(state: GraphState, gate_point: str, next_node: str) -> str:
    if next_node == END:
        return END
    router_gate = state.get("router_gate", {}) if isinstance(state.get("router_gate", {}), dict) else {}
    if router_gate.get("status") == "pending" and router_gate.get("gate_point") == gate_point:
        return "router_gate"
    if router_gate.get("status") in {"approved", "rejected", "canceled"}:
        if router_gate.get("gate_point") == gate_point and router_gate.get("resume_node") == next_node:
            return next_node if router_gate.get("status") == "approved" else END
    if _should_router_gate(state, gate_point):
        return "router_gate"
    return next_node


def _route_after_architect_core(state: GraphState) -> str:
    """
    Route after architect node.

    Phase 4: Always proceed to reviewer for pre-execution validation.

    Args:
        state: Current graph state

    Returns:
        Next node name: 'reviewer'
    """
    if state.get("preconfirm_action") == "cancel":
        logger.warning("[ROUTE] Pre-confirm gate canceled → END")
        return END
    logger.debug("[ROUTE] Router: Architect → Reviewer (pre-execution validation)")
    return "reviewer"


def route_after_architect(state: GraphState) -> str:
    """
    Route after architect node.

    Phase 4: Always proceed to reviewer for pre-execution validation.

    Args:
        state: Current graph state

    Returns:
        Next node name: 'reviewer'
    """
    next_node = _route_after_architect_core(state)
    return _maybe_route_with_gate(state, "architect", next_node)


def _route_after_input_writer_core(state: GraphState) -> str:
    """
    Route after input_writer node.
    
    Always proceed to runner to setup job directory.
    
    Args:
        state: Current graph state
        
    Returns:
        Next node name: 'runner'
    """
    if state.get("mode") == "terminal":
        logger.warning("[ROUTE] Input Writer terminal mode → END")
        return END
    logger.debug("[ROUTE] Router: Input Writer → Runner")
    return "runner"


def route_after_input_writer(state: GraphState) -> str:
    """
    Route after input_writer node.

    Always proceed to runner to setup job directory.

    Args:
        state: Current graph state

    Returns:
        Next node name: 'runner'
    """
    next_node = _route_after_input_writer_core(state)
    return _maybe_route_with_gate(state, "input_writer", next_node)


def _route_after_runner_core(state: GraphState) -> str:
    """
    Route after runner node.

    Per PRD error handling strategy:
    - System failures (compilation, permissions) → TERMINAL (END)
    - Runtime failures (job crashes, physics issues) → RETRYABLE (Analysis)

    System failures cannot be fixed by changing inputs. Runtime failures may be
    addressable through input modifications discovered during analysis.

    Args:
        state: Current graph state

    Returns:
        'analysis' for success or runtime failures, END for system failures
    """
    # Check compilation_failed flag first (set by runner node)
    if state.get("compilation_failed"):
        logger.error("[ROUTE] Compilation failed (terminal) → END")
        return END

    mode = state.get("mode", "fail")
    error = state.get("error", "")

    # Also check mode == "terminal" (explicit terminal state)
    if mode == "terminal":
        logger.error(f"[ROUTE] Terminal mode → END: {error}")
        return END

    if state.get("job_status") in {"skipped", "cancelled", "timeout"}:
        logger.warning("[ROUTE] Runner %s → END", state.get("job_status"))
        return END

    # Terminal system failures (cannot be fixed by changing inputs)
    terminal_errors = [
        "Compilation failed",
        "Executable resolution failed",
        "PermissionError",
        "OSError",
        "Disk",
        "No such file"
    ]

    # Check if error is a terminal system failure
    if mode == "fail" and any(err in error for err in terminal_errors):
        logger.error(f"[ROUTE] Terminal system failure → END: {error}")
        return END

    # All other cases go to analysis (including runtime job failures)
    # Analysis will determine if failure is retryable
    if mode == "fail":
        logger.warning(f"[ROUTE] Runtime failure → Analysis (retryable): {error}")
        return "analysis"

    # Success case
    logger.debug("[ROUTE] Router: Runner → Analysis (execution succeeded)")
    return "analysis"


def route_after_runner(state: GraphState) -> str:
    """
    Route after runner node.

    Per PRD error handling strategy:
    - System failures (compilation, permissions) → TERMINAL (END)
    - Runtime failures (job crashes, physics issues) → RETRYABLE (Analysis)

    System failures cannot be fixed by changing inputs. Runtime failures may be
    addressable through input modifications discovered during analysis.

    Args:
        state: Current graph state

    Returns:
        'analysis' for success or runtime failures, END for system failures
    """
    next_node = _route_after_runner_core(state)
    return _maybe_route_with_gate(state, "runner", next_node)


def _route_after_reviewer_core(state: GraphState) -> str:
    """
    Route after Reviewer validation.
    
    Graph Assembly: Routing Logic: Conditional routing logic.
    - proceed → input_writer
    - retry (with attempts) → architect
    - fail or max retries → END
    """
    mode = state.get("mode", "fail")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if mode == "terminal":
        logger.warning("[ROUTE] Reviewer → END (Terminal mode)")
        return END
    if mode == "proceed":
        logger.debug("[ROUTE] Reviewer → Input Writer (Approved)")
        return "input_writer"

    elif mode == "retry":
        if retry_count < max_retries:
            logger.debug(f"[ROUTE] Reviewer → Architect (Retry {retry_count + 1}/{max_retries})")
            return "architect"
        else:
            logger.warning(f"[ROUTE] Reviewer → END (Max retries {max_retries} exceeded)")
            return END

    else:  # mode == "fail" or unknown
        logger.warning(f"[ROUTE] Reviewer → END (Validation Failed: {mode})")
        return END


def route_after_reviewer(state: GraphState) -> str:
    """
    Route after Reviewer validation.

    Graph Assembly: Routing Logic: Conditional routing logic.
    - proceed → input_writer
    - retry (with attempts) → architect
    - fail or max retries → END
    """
    next_node = _route_after_reviewer_core(state)
    return _maybe_route_with_gate(state, "reviewer", next_node)


def _route_after_analysis_core(state: GraphState) -> str:
    """
    Route after analysis node.

    Phase 4 Decision:
    - If analysis passed → visualization
    - If analysis failed → reviewer (for retry loop)

    Args:
        state: Current graph state

    Returns:
        Next node name: 'visualization' or 'reviewer'
    """
    if state.get("mode") == "terminal":
        logger.warning("[ROUTE] Analysis terminal mode → END")
        return END

    analysis_report = state.get("analysis_report", {})
    status = analysis_report.get("status", "unknown")

    if status == "failed":
        issues = analysis_report.get("issues", [])
        logger.debug("[ROUTE] Router: Analysis → Reviewer (simulation failed)")
        logger.debug(f"   Issues: {len(issues)}")
        if len(issues) == 0:
            logger.warning("[ROUTE] Analysis failure without actionable issues → Reviewer")
        state["mode"] = "retry"  # Signal post-execution retry
        return "reviewer"

    logger.debug("[ROUTE] Router: Analysis → Visualization (simulation passed)")
    return "visualization"


def route_after_analysis(state: GraphState) -> str:
    """
    Route after analysis node.

    Phase 4 Decision:
    - If analysis passed → visualization
    - If analysis failed → reviewer (for retry loop)

    Args:
        state: Current graph state

    Returns:
        Next node name: 'visualization' or 'reviewer'
    """
    next_node = _route_after_analysis_core(state)
    return _maybe_route_with_gate(state, "analysis", next_node)


def _route_after_visualization_core(state: GraphState) -> str:
    """
    Route after visualization node.

    Phase 4: Always end workflow after visualization.

    Args:
        state: Current graph state

    Returns:
        Next node name: END
    """
    images = state.get("visualization_images", [])
    logger.debug(f"[ROUTE] Router: Visualization → END ({len(images)} images generated)")
    return END


def route_after_visualization(state: GraphState) -> str:
    """
    Route after visualization node.

    Phase 4: Always end workflow after visualization.

    Args:
        state: Current graph state

    Returns:
        Next node name: END
    """
    next_node = _route_after_visualization_core(state)
    return _maybe_route_with_gate(state, "visualization", next_node)


def route_after_router_gate(state: GraphState) -> str:
    router_gate = state.get("router_gate", {}) if isinstance(state.get("router_gate", {}), dict) else {}
    status = router_gate.get("status")
    resume_node = router_gate.get("resume_node")
    if status == "approved" and resume_node:
        return resume_node
    return END


# Export for LangGraph
__all__ = [
    'route_after_architect',
    'route_after_input_writer', 
    'route_after_runner',
    'route_after_reviewer',
    'route_after_analysis',
    'route_after_visualization',
    'route_after_router_gate',
    '_route_after_architect_core',
    '_route_after_input_writer_core',
    '_route_after_runner_core',
    '_route_after_reviewer_core',
    '_route_after_analysis_core',
    '_route_after_visualization_core',
]
