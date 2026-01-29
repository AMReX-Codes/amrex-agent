"""
Schema Validation Helpers for Integration Tests

Utilities to verify GraphState compliance at runtime.
"""
from typing import Dict, Any, List, get_type_hints
from src.models.graph_state_canonical import GraphState


def validate_field_names(state: Dict[str, Any]) -> List[str]:
    """
    Check that state uses canonical field names.

    Detects deprecated names like:
    - run_dir → should be run_directory
    - inputs_path → should be inputs_file_path

    Args:
        state: State dict to validate

    Returns:
        List of deprecated field names found

    Example:
        >>> deprecated = validate_field_names(state)
        >>> assert len(deprecated) == 0, f"Found deprecated fields: {deprecated}"
    """
    deprecated_mappings = {
        "run_dir": "run_directory",
        "inputs_path": "inputs_file_path",
        "user_requirement": "prompt",
        "user_req": "prompt"
    }

    found_deprecated = []

    for old_name, new_name in deprecated_mappings.items():
        if old_name in state:
            found_deprecated.append(f"{old_name} (use {new_name})")

    return found_deprecated


def validate_history_structure(history: List[Dict[str, Any]]) -> List[str]:
    """
    Validate workflow_history entries have required fields.

    Each entry must have:
    - node: str
    - timestamp: str
    - action: str
    - iteration: int (optional)

    Args:
        history: workflow_history list

    Returns:
        List of validation errors

    Example:
        >>> errors = validate_history_structure(state["workflow_history"])
        >>> assert len(errors) == 0, f"Invalid history: {errors}"
    """
    errors = []
    required_fields = ["node", "timestamp", "action"]

    for i, entry in enumerate(history):
        for field in required_fields:
            if field not in entry:
                errors.append(f"Entry {i} missing '{field}'")

        # Validate timestamp format (basic check)
        if "timestamp" in entry:
            ts = entry["timestamp"]
            if not isinstance(ts, str) or "T" not in ts:
                errors.append(f"Entry {i} has invalid timestamp format: {ts}")

    return errors


def validate_mode_transition(
    old_state: Dict[str, Any],
    new_state: Dict[str, Any]
) -> bool:
    """
    Validate mode transition is legal.

    Legal transitions:
    - initial → proceed, retry, fail
    - retry → proceed, retry (again), fail
    - proceed → proceed (next node), fail
    - fail → (terminal, no transitions)

    Args:
        old_state: State before node execution
        new_state: State after node execution

    Returns:
        True if transition is valid

    Example:
        >>> assert validate_mode_transition(old_state, new_state)
    """
    old_mode = old_state.get("mode", "initial")
    new_mode = new_state.get("mode", "initial")

    valid_transitions = {
        "initial": ["proceed", "retry", "fail"],
        "retry": ["proceed", "retry", "fail"],
        "proceed": ["proceed", "fail"],
        "fail": []  # Terminal
    }

    allowed = valid_transitions.get(old_mode, [])
    return new_mode in allowed


def assert_immutable_append(
    old_history: List[Dict[str, Any]],
    new_history: List[Dict[str, Any]]
) -> None:
    """
    Assert that history was appended immutably (not mutated).

    Checks:
    1. New history is longer than old
    2. Old entries are unchanged (by value)
    3. Only new entries added at end

    Args:
        old_history: workflow_history before update
        new_history: workflow_history after update

    Raises:
        AssertionError: If history was mutated instead of appended

    Example:
        >>> old = state["workflow_history"]
        >>> state = node(state)
        >>> new = state["workflow_history"]
        >>> assert_immutable_append(old, new)
    """
    assert len(new_history) >= len(old_history), \
        f"History shrunk: {len(old_history)} → {len(new_history)}"

    # Verify old entries unchanged
    for i, old_entry in enumerate(old_history):
        new_entry = new_history[i]
        assert old_entry == new_entry, \
            f"History entry {i} was mutated: {old_entry} → {new_entry}"

    # Verify new entries only at end
    new_entries = new_history[len(old_history):]
    assert len(new_entries) > 0, "No new entries added"
