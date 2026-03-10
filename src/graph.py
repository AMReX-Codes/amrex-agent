"""Graph wiring for B1b/B1c intent and clarification flow."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from src.models import GraphState
from src.nodes.architect_node import architect_node
from src.nodes.clarification_node import clarification_node
from src.nodes.input_writer_node import input_writer_node
from src.nodes.intent_extraction_node import intent_extraction_node
from src.nodes.sweep_detection_node import sweep_detection_node
from src.benchmark_runner import has_migration_plan_schema_mapping_and_rollback
from src.services.plan import has_checklist_implementation_locations
from src.session_manager import is_b4_implementation_sequence_complete


_ACCEPTANCE_MAPPING_KEYS = (
    "mapped_tests",
    "tests",
    "test_cases",
    "test_ids",
)


def _normalize_test_mappings(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []

    if not isinstance(value, list):
        return []

    mappings: list[str] = []
    for entry in value:
        if isinstance(entry, str):
            normalized = entry.strip()
            if normalized:
                mappings.append(normalized)
    return mappings


def has_acceptance_checklist_mapped_tests(context: dict[str, Any]) -> bool:
    """
    Validate acceptance checklist entries include at least one mapped test.
    """
    manifest = context.get("validation_manifest")
    if not isinstance(manifest, dict):
        return False

    checklist = manifest.get("acceptance_checklist")
    if not isinstance(checklist, list) or not checklist:
        return False

    for entry in checklist:
        if not isinstance(entry, dict):
            return False
        has_mapping = any(
            _normalize_test_mappings(entry.get(key))
            for key in _ACCEPTANCE_MAPPING_KEYS
        )
        if not has_mapping:
            return False

    return True


def _route_after_clarification(state: dict) -> str:
    if state.get("clarification_needed", False):
        return "clarification_handler"
    return "input_writer_node"


def _route_after_sweep_detection(state: dict) -> str:
    if (
        state.get("sweep_id") is not None
        and is_b4_implementation_sequence_complete(state)
        and has_checklist_implementation_locations(state)
        and has_acceptance_checklist_mapped_tests(state)
        and has_migration_plan_schema_mapping_and_rollback(state)
    ):
        return "sweep_execution_handler"
    return "architect_node"


def clarification_handler_node(state: dict) -> dict:
    """
    Placeholder for B1c clarification response.
    Full implementation in later session.
    Currently routes to END after logging questions.
    """
    questions = state.get("clarification_questions", [])
    print(f"Clarification needed: {questions}")
    return state


def sweep_execution_handler_node(state: dict) -> dict:
    """
    Placeholder for B2c sweep fan-out.
    Full implementation in later session.
    Logs detected sweep spec and routes to END.
    """
    sweep_id = state.get("sweep_id")
    sweep_param = state.get("sweep_parameter")
    print(f"Sweep detected: {sweep_id} over {sweep_param}")
    return state


def create_graph() -> StateGraph:
    """Build graph with B1b/B1c graph wiring."""
    graph = StateGraph(GraphState)

    graph.add_node("sweep_detection_node", sweep_detection_node)
    graph.add_node("architect_node", architect_node)
    graph.add_node("intent_extraction_node", intent_extraction_node)
    graph.add_node("clarification_node", clarification_node)
    graph.add_node("clarification_handler", clarification_handler_node)
    graph.add_node("sweep_execution_handler", sweep_execution_handler_node)
    graph.add_node("input_writer_node", input_writer_node)

    graph.add_edge(START, "sweep_detection_node")
    graph.add_conditional_edges(
        "sweep_detection_node",
        _route_after_sweep_detection,
        {
            "architect_node": "architect_node",
            "sweep_execution_handler": "sweep_execution_handler",
        },
    )
    graph.add_edge("architect_node", "intent_extraction_node")
    graph.add_edge("intent_extraction_node", "clarification_node")
    graph.add_conditional_edges(
        "clarification_node",
        _route_after_clarification,
        {
            "input_writer_node": "input_writer_node",
            "clarification_handler": "clarification_handler",
        },
    )
    graph.add_edge("clarification_handler", END)
    graph.add_edge("sweep_execution_handler", END)
    graph.add_edge("input_writer_node", END)

    return graph
