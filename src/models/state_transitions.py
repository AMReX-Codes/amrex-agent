"""
State transition helper for Integration Ladder workflow.

Handles mode changes, counter updates, and history tracking.

This is the CANONICAL way to update state - enforces:
- Correct mode transitions
- Proper counter updates
- Consistent workflow_history structure
- Validation of state machine rules
"""

from typing import Dict, Any
from src.models.state_compatibility import add_history_entry
import logging

logger = logging.getLogger(__name__)


def validate_transition(state: Dict[str, Any], new_mode: str) -> bool:
    """
    Validate mode transition is legal per workflow state machine.
    
    State Machine:
        initial → proceed | retry | terminal
        proceed → terminal
        retry → proceed | retry | terminal
        terminal → (no transitions)
    
    Args:
        state: Current state
        new_mode: Desired new mode
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If transition is invalid
    """
    current_mode = state.get("mode", "initial")
    
    valid_transitions = {
        "initial": ["proceed", "retry", "terminal"],
        "proceed": ["terminal"],
        "retry": ["proceed", "retry", "terminal"],
        "terminal": []
    }
    
    if new_mode not in valid_transitions.get(current_mode, []):
        raise ValueError(
            f"Invalid state transition: {current_mode} → {new_mode}\n"
            f"Valid transitions from '{current_mode}': {valid_transitions.get(current_mode, [])}"
        )
    
    return True


def transition_to_proceed(state: Dict[str, Any], message: str = None) -> Dict[str, Any]:
    """
    Transition to 'proceed' mode after successful review.
    
    Validates transition, sets mode, records in workflow_history.
    
    Args:
        state: Current state
        message: Optional history message
        
    Returns:
        Updated state with mode='proceed'
        
    Raises:
        ValueError: If transition is invalid
    """
    validate_transition(state, "proceed")
    state["mode"] = "proceed"
    
    if message:
        state = add_history_entry(
            state,
            message,
            node="reviewer",
            action="approved"
        )
    
    return state


def transition_to_retry(state: Dict[str, Any], message: str = None) -> Dict[str, Any]:
    """
    Transition to 'retry' mode after failed review.
    
    Validates transition, sets mode, increments counters, records in workflow_history.
    
    Args:
        state: Current state
        message: Optional history message
        
    Returns:
        Updated state with mode='retry' and incremented counters
        
    Raises:
        ValueError: If transition is invalid
    """
    validate_transition(state, "retry")
    state["mode"] = "retry"
    
    # Increment retry counter
    state["retry_count"] = state.get("retry_count", 0) + 1
    
    # Increment iteration
    state["iteration"] = state.get("iteration", 0) + 1
    
    if message:
        state = add_history_entry(
            state,
            message,
            node="reviewer",
            action="rejected",
            details={
                "retry_count": state["retry_count"],
                "iteration": state["iteration"]
            }
        )
    
    return state


def transition_to_terminal(state: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """
    Transition to terminal mode (max retries exceeded).
    
    Validates transition, sets mode, records in workflow_history.
    
    Args:
        state: Current state
        reason: Reason for termination
        
    Returns:
        Updated state with mode='terminal'
        
    Raises:
        ValueError: If transition is invalid
    """
    validate_transition(state, "terminal")
    state["mode"] = "terminal"
    
    state = add_history_entry(
        state,
        f"Reviewer: Terminated - {reason}",
        node="reviewer",
        action="terminated",
        details={"reason": reason}
    )
    
    return state


def skip_review(state: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """
    Skip review (no plan provided).
    
    Does NOT change mode (stays in current state).
    Records skip in workflow_history.
    
    Args:
        state: Current state
        reason: Reason for skipping
        
    Returns:
        Updated state with skipped review
    """
    state["review_analysis"] = {
        "approved": True,
        "message": f"Skipped: {reason}"
    }
    
    state = add_history_entry(
        state,
        f"Reviewer: Skipped ({reason})",
        node="reviewer",
        action="skipped",
        details={"reason": reason}
    )
    
    logger.info(f"Review skipped: {reason}")
    
    # Don't change mode when skipping (stay in current mode)
    return state
