"""Unit tests for PRD feature and persona mapping references."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from src.graph import (
    _paper_validator_enabled,
    _route_after_architect,
    _route_after_clarification,
    _route_after_paper_validator,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    sweep_execution_handler_node,
)

# Coverage compatibility for file-path based coverage targets.
sys.modules["src/graph.py"] = sys.modules["src.graph"]


PRD_PATH = Path("docs/PRD/PRD_v2605.md")


def test_feature_table_mapping_reference_present() -> None:
    text = PRD_PATH.read_text(encoding="utf-8")

    assert "| P1 | F5.2 | Sweep orchestrator | Batch workflows | Apr 12 | F5.1 |" in text


def test_persona_mapping_references_present() -> None:
    text = PRD_PATH.read_text(encoding="utf-8")

    assert "* **Mapping:** F5.1, F5.2." in text
    assert "* **Mapping:** F5.2." in text
    assert "Sweep orchestration spawns child workflows and aggregates results." in text


def test_graph_routing_branches_cover_feature_mapping_paths() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"

    assert _route_after_sweep_detection({"sweep_id": "sweep-1"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"

    assert _paper_validator_enabled({}) is False
    assert _paper_validator_enabled({"config": {}}) is False
    assert _paper_validator_enabled({"config": {"paper_validator_enabled": True}}) is True
    assert _paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True

    assert _route_after_architect({"config": {"paper_validator_enabled": True}}) == "paper_validator_node"
    assert _route_after_architect({"config": {"paper_validator_enabled": False}}) == "intent_extraction_node"

    assert _route_after_paper_validator({"paper_validation_passed": False}) == "end"
    assert _route_after_paper_validator({"paper_validation_passed": True}) == "intent_extraction_node"
    assert _route_after_paper_validator(
        {
            "paper_validation_passed": True,
            "claim_evidence_matrix_required": True,
            "claim_evidence_matrix_complete": False,
        }
    ) == "end"
    assert _route_after_paper_validator(
        {
            "paper_validation_passed": True,
            "claim_evidence_matrix_required": True,
            "claim_evidence_matrix_complete": True,
        }
    ) == "intent_extraction_node"


def test_graph_handlers_and_wiring_cover_feature_mapping_paths() -> None:
    clarification_state = {"clarification_questions": ["q1"]}
    sweep_state = {"sweep_id": "sweep-1", "sweep_parameter": "max_step"}

    assert clarification_handler_node(clarification_state) is clarification_state
    assert sweep_execution_handler_node(sweep_state) is sweep_state

    app = create_graph().compile()
    graph_def = app.get_graph()
    nodes = set(graph_def.nodes.keys())
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert "sweep_detection_node" in nodes
    assert "architect_node" in nodes
    assert "paper_validator_node" in nodes
    assert "intent_extraction_node" in nodes
    assert "clarification_node" in nodes
    assert "clarification_handler" in nodes
    assert "sweep_execution_handler" in nodes
    assert "input_writer_node" in nodes

    assert ("__start__", "sweep_detection_node") in edges
    assert ("architect_node", "paper_validator_node") in edges
    assert ("architect_node", "intent_extraction_node") in edges
    assert ("paper_validator_node", "intent_extraction_node") in edges
    assert ("paper_validator_node", "__end__") in edges
    assert ("clarification_handler", "__end__") in edges
    assert ("sweep_execution_handler", "__end__") in edges
    assert ("input_writer_node", "__end__") in edges
