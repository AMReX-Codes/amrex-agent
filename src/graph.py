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


def _route_after_clarification(state: dict) -> str:
    if state.get("clarification_needed", False):
        return "clarification_handler"
    return "input_writer_node"


def _route_after_sweep_detection(state: dict) -> str:
    if state.get("sweep_id") is not None:
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
