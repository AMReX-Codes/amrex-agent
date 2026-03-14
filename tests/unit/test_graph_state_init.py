"""Graph state initialization tests."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.config import AMReXAgentConfig
from src.main import initialize_state
from src.models.graph_state_canonical import GRAPH_STATE_B1_B2_DEFAULTS, GraphState


NEW_FIELDS = {
    "resolved_config",
    "intent_extraction_applied",
    "intent_extraction_error",
    "intent_locked_fields",
    "clarification_history",
    "clarification_turns",
    "unresolved_level",
    "reviewer_failure_category",
    "gate_approvals",
    "sweep_id",
    "sweep_child_id",
    "sweep_parameter",
    "sweep_parameter_value",
}


EXISTING_CORE_FIELDS = {
    "prompt",
    "config",
    "mode",
    "iteration",
    "retry_count",
    "max_retries",
    "errors_active",
    "errors_found",
    "errors_fixed",
    "error_logs",
    "modifications",
    "workflow_history",
    "history",
}


@pytest.fixture
def mock_config() -> Mock:
    config = Mock(spec=AMReXAgentConfig)
    config.max_iterations = 3
    return config


def _clone_b1_b2_defaults() -> dict[str, object]:
    return {
        key: value.copy() if isinstance(value, list) else value
        for key, value in GRAPH_STATE_B1_B2_DEFAULTS.items()
    }


def test_initializes_default_counters(mock_config: Mock) -> None:
    state = initialize_state("simulation request", mock_config)

    assert state["retry_count"] == 0
    assert state["iteration"] == 0
    assert state["mode"] == "initial"


def test_initializes_empty_collections(mock_config: Mock) -> None:
    state = initialize_state("test request", mock_config)

    assert state["workflow_history"] == []
    assert state["errors_active"] == []
    assert state["modifications"] == []


def test_loads_prompt_from_file_path(mock_config: Mock, tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("simulate combustion")

    state = initialize_state(str(prompt_file), mock_config)

    assert state["prompt"] == "simulate combustion"


def test_loads_prompt_from_string(mock_config: Mock) -> None:
    raw_prompt = "run flame simulation"

    state = initialize_state(raw_prompt, mock_config)

    assert state["prompt"] == "run flame simulation"


def test_injects_config_object(mock_config: Mock) -> None:
    state = initialize_state("test", mock_config)

    assert state["config"] == mock_config


def test_sets_max_retries_from_config(mock_config: Mock) -> None:
    mock_config.max_iterations = 5

    state = initialize_state("test", mock_config)

    assert state["max_retries"] == 5


def test_schema_has_node_required_fields(mock_config: Mock) -> None:
    state = initialize_state("test", mock_config)

    assert "errors_active" in state
    assert "mode" in state
    assert "retry_count" in state
    assert "modifications" in state
    assert "workflow_history" in state
    assert "execution_intent" in state
    assert "visualization_intent" in state


def test_validates_empty_prompt(mock_config: Mock) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        initialize_state("", mock_config)


def test_validates_whitespace_only_prompt(mock_config: Mock) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        initialize_state("   \n  ", mock_config)


def test_handles_missing_prompt_file(mock_config: Mock) -> None:
    state = initialize_state("/non/existent/file.txt", mock_config)

    assert state["prompt"] == "/non/existent/file.txt"


# Intent Extraction fields
def test_resolved_config_field_exists_with_none_default(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["resolved_config"] is None


def test_intent_extraction_applied_defaults_false(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["intent_extraction_applied"] is False


def test_intent_extraction_error_defaults_none(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["intent_extraction_error"] is None


def test_intent_locked_fields_defaults_empty_list(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["intent_locked_fields"] == []


# Clarification fields
def test_clarification_history_defaults_empty_list(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["clarification_history"] == []


def test_clarification_turns_defaults_zero(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["clarification_turns"] == 0


def test_unresolved_level_defaults_none(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["unresolved_level"] is None


# Reviewer routing fields
def test_reviewer_failure_category_defaults_none(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["reviewer_failure_category"] is None


# Gate approval fields
def test_gate_approvals_defaults_empty_list(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["gate_approvals"] == []


# Sweep fields (schemas only, no orchestrator logic)
def test_sweep_id_defaults_none(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["sweep_id"] is None


def test_sweep_child_id_defaults_none(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["sweep_child_id"] is None


def test_sweep_parameter_defaults_none(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["sweep_parameter"] is None


def test_sweep_parameter_value_defaults_none(mock_config: Mock) -> None:
    state = _clone_b1_b2_defaults()
    assert state["sweep_parameter_value"] is None


# Schema integrity tests
def test_all_new_fields_have_defaults(mock_config: Mock) -> None:
    state: GraphState = _clone_b1_b2_defaults()

    assert state["resolved_config"] is None
    assert state["intent_extraction_applied"] is False
    assert state["intent_extraction_error"] is None
    assert state["intent_locked_fields"] == []
    assert state["clarification_history"] == []
    assert state["clarification_turns"] == 0
    assert state["unresolved_level"] is None
    assert state["reviewer_failure_category"] is None
    assert state["gate_approvals"] == []
    assert state["sweep_id"] is None
    assert state["sweep_child_id"] is None
    assert state["sweep_parameter"] is None
    assert state["sweep_parameter_value"] is None


def test_new_fields_do_not_shadow_existing() -> None:
    assert NEW_FIELDS.isdisjoint(EXISTING_CORE_FIELDS)

    graph_state_fields = set(GraphState.__annotations__.keys())
    assert NEW_FIELDS.issubset(graph_state_fields)


def test_list_fields_are_independent_instances(mock_config: Mock) -> None:
    state_one: GraphState = _clone_b1_b2_defaults()
    state_two: GraphState = _clone_b1_b2_defaults()

    assert state_one["intent_locked_fields"] is not state_two["intent_locked_fields"]
    assert state_one["clarification_history"] is not state_two["clarification_history"]
    assert state_one["gate_approvals"] is not state_two["gate_approvals"]


def test_serialization_matches_workflow_history_pattern(mock_config: Mock) -> None:
    state: GraphState = {
        "workflow_history": [],
        **_clone_b1_b2_defaults(),
    }

    state["gate_approvals"].append({"gate": "reviewer", "status": "approved"})
    state["clarification_history"].append({"question": "Need Reynolds number?", "answer": "1e5"})

    serialized = json.dumps(
        {
            "workflow_history": state["workflow_history"],
            "gate_approvals": state["gate_approvals"],
            "clarification_history": state["clarification_history"],
        }
    )

    assert isinstance(serialized, str)
    assert all(isinstance(item, dict) for item in state["gate_approvals"])
    assert all(isinstance(item, dict) for item in state["clarification_history"])
