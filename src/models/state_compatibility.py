"""
Backward compatibility layer for GraphState migration.

Handles transition from:
- history: List[str] (old, deprecated)
- workflow_history: List[Dict[str, Any]] (new, canonical)

Usage in nodes:
    from src.models.state_compatibility import add_history_entry
    
    # Works with both old and new state schemas
    state = add_history_entry(state, "Reviewer: Approved plan")
"""

from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def ensure_history_fields(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure both history fields exist for backward compatibility.
    
    Initializes:
    - history: List[str] (legacy)
    - workflow_history: List[Dict[str, Any]] (canonical)
    
    Args:
        state: GraphState dict
        
    Returns:
        State with both history fields initialized
    """
    if "history" not in state:
        state["history"] = []
    
    if "workflow_history" not in state:
        state["workflow_history"] = []
    
    return state


def add_history_entry(
    state: Dict[str, Any],
    message: str,
    node: str = None,
    action: str = None,
    details: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Add entry to both history formats for compatibility.
    
    This allows gradual migration:
    - Old code: Uses history[0], history[1], etc.
    - New code: Uses workflow_history with structured data
    
    Args:
        state: GraphState dict
        message: Human-readable message (for legacy history)
        node: Node name (for workflow_history)
        action: Action taken (for workflow_history)
        details: Additional metadata (for workflow_history)
        
    Returns:
        Updated state
        
    Example:
        >>> state = add_history_entry(
        ...     state,
        ...     "Reviewer: Approved plan",
        ...     node="reviewer",
        ...     action="approved",
        ...     details={"errors": 0, "warnings": 2}
        ... )
    """
    # Ensure fields exist
    state = ensure_history_fields(state)
    
    # Add to legacy history (simple string)
    state["history"].append(message)
    
    # Add to canonical workflow_history (structured)
    iteration = state.get("iteration", 0)

    # If node/action not provided, try to infer from message
    if not node:
        node = _infer_node_from_message(message)
    if not action:
        action = _infer_action_from_message(message)

    # Build details dict with message if provided (Fix 8 - canonical format)
    entry_details = details or {}
    if message and not details:
        # If only message provided, parse it into details
        entry_details = {"message": message}
    elif message and details:
        # If both provided, add message to details
        entry_details = {**details, "message": message}

    workflow_entry = {
        "node": node or "unknown",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action or "message",
        "iteration": iteration,
        "details": entry_details
    }

    state["workflow_history"].append(workflow_entry)
    
    return state


def _infer_node_from_message(message: str) -> str:
    """Infer node name from legacy message format"""
    message_lower = message.lower()
    
    if message.startswith("Architect:") or "architect" in message_lower:
        return "architect"
    elif message.startswith("Reviewer:") or "reviewer" in message_lower:
        return "reviewer"
    elif message.startswith("Writer:") or "input writer" in message_lower:
        return "input_writer"
    elif message.startswith("Runner:") or "runner" in message_lower:
        return "runner"
    elif message.startswith("Analysis:") or "analysis" in message_lower:
        return "analysis"
    elif message.startswith("Viz:") or "visualization" in message_lower:
        return "visualization"
    else:
        return "unknown"


def _infer_action_from_message(message: str) -> str:
    """Infer action from legacy message format"""
    message_lower = message.lower()
    
    if "approved" in message_lower or "passed" in message_lower:
        return "approved"
    elif "rejected" in message_lower or "failed" in message_lower:
        return "rejected"
    elif "created" in message_lower or "generated" in message_lower:
        return "created"
    elif "skipped" in message_lower:
        return "skipped"
    elif "completed" in message_lower:
        return "completed"
    elif "retry" in message_lower:
        return "retry"
    else:
        return "message"


def get_history_summary(state: Dict[str, Any]) -> str:
    """
    Get formatted summary of execution history.
    
    Works with both old and new history formats.
    
    Args:
        state: GraphState dict
        
    Returns:
        Multi-line summary string
    """
    lines = ["Execution History:", "=" * 60]
    
    # Prefer workflow_history if available
    if "workflow_history" in state and state["workflow_history"]:
        for i, entry in enumerate(state["workflow_history"]):
            node = entry.get("node", "unknown")
            action = entry.get("action", "message")
            iteration = entry.get("iteration", 0)
            # Fix 8: message is now in details dict
            details = entry.get("details", {})
            message = details.get("message", "") if isinstance(details, dict) else ""
            # Fallback for old format (backward compatibility)
            if not message:
                message = entry.get("message", "")

            lines.append(
                f"{i+1}. [{node}] {action} (iter {iteration}): {message[:60]}"
            )
    
    # Fallback to legacy history
    elif "history" in state and state["history"]:
        for i, message in enumerate(state["history"]):
            lines.append(f"{i+1}. {message}")
    
    else:
        lines.append("(No history available)")
    
    return "\n".join(lines)
