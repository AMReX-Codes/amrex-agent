"""
State Management Utilities for AMReXAgent

Implements the Immutable Append Pattern for LangGraph compliance.

Key Principles:
- Never mutate state in place
- Always return new collections
- Preserve history for time-travel debugging

References:
- PRD Amendment A [Source 781]
- Architect Node: Workflow History Logging [Source 4587]
- LangGraph Reducers Pattern [Source 2919]
"""
from typing import Dict, Any, List
from datetime import datetime


def append_to_history(
    existing_history: List[Dict[str, Any]],
    node_name: str,
    action: str,
    iteration: int = 0,
    details: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Immutable append to workflow_history.

    This is the CORRECT pattern for LangGraph state updates.
    Creates a new list rather than modifying existing one.

    Args:
        existing_history: Current workflow_history from state
        node_name: Name of node adding entry (e.g., "architect")
        action: Action taken (e.g., "plan_created", "approved")
        iteration: Current retry iteration
        details: Additional metadata (optional)

    Returns:
        New list with entry appended

    Example:
        >>> state = {"workflow_history": [...]}
        >>> new_history = append_to_history(
        ...     state["workflow_history"],
        ...     node_name="reviewer",
        ...     action="approved",
        ...     iteration=0,
        ...     details={"errors": 0, "warnings": 2}
        ... )
        >>> return {"workflow_history": new_history}

    Anti-pattern (DO NOT DO):
        >>> state["workflow_history"].append(entry)  # WRONG: mutates state
    """
    new_entry = {
        "node": node_name,
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "iteration": iteration,
    }

    if details:
        new_entry["details"] = details

    # Create NEW list (immutable append)
    return existing_history + [new_entry]


def increment_retry_count(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Increment retry counter immutably.

    Args:
        state: Current graph state

    Returns:
        Updates dict with incremented retry_count

    Example:
        >>> updates = increment_retry_count(state)
        >>> return {**updates, "mode": "retry"}
    """
    current_count = state.get("retry_count", 0)
    return {"retry_count": current_count + 1}


def add_error(
    state: Dict[str, Any],
    error_message: str,
    error_type: str = "active"
) -> Dict[str, Any]:
    """
    Add error to appropriate error list immutably.

    Args:
        state: Current graph state
        error_message: Error description
        error_type: "active", "found", or "fixed"

    Returns:
        Updates dict with error added to correct list

    Example:
        >>> updates = add_error(state, "CFL too high", "active")
        >>> return {**updates, "mode": "retry"}
    """
    field_map = {
        "active": "errors_active",
        "found": "errors_found",
        "fixed": "errors_fixed"
    }

    field = field_map.get(error_type, "errors_active")
    current_errors = state.get(field, [])

    # Avoid duplicates
    if error_message not in current_errors:
        return {field: current_errors + [error_message]}

    return {}


def mark_error_fixed(
    state: Dict[str, Any],
    error_message: str
) -> Dict[str, Any]:
    """
    Move error from active to fixed list immutably.

    Args:
        state: Current graph state
        error_message: Error that was resolved

    Returns:
        Updates dict removing from active, adding to fixed

    Example:
        >>> updates = mark_error_fixed(state, "missing amr.max_level")
        >>> return updates
    """
    current_active = state.get("errors_active", [])
    current_fixed = state.get("errors_fixed", [])

    # Remove from active (create new list without error)
    new_active = [e for e in current_active if e != error_message]

    # Add to fixed (if not already there)
    new_fixed = current_fixed + [error_message] if error_message not in current_fixed else current_fixed

    return {
        "errors_active": new_active,
        "errors_fixed": new_fixed
    }


def create_node_update(
    node_name: str,
    action: str,
    state: Dict[str, Any],
    **additional_fields
) -> Dict[str, Any]:
    """
    Convenience function to create standard node update dict.

    Combines history append with custom fields in one call.

    Args:
        node_name: Name of node
        action: Action taken
        state: Current state (for history)
        **additional_fields: Custom fields to include

    Returns:
        Updates dict with history + custom fields

    Example:
        >>> return create_node_update(
        ...     "architect",
        ...     "plan_created",
        ...     state,
        ...     selected_case="PMF",
        ...     modifications=[(...), (...)],
        ...     mode="proceed"
        ... )
    """
    new_history = append_to_history(
        state.get("workflow_history", []),
        node_name=node_name,
        action=action,
        iteration=state.get("iteration", 0),
        details={k: v for k, v in additional_fields.items() if k not in ["mode", "retry_count"]}
    )

    return {
        "workflow_history": new_history,
        **additional_fields
    }
