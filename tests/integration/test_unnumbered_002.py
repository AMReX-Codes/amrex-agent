from __future__ import annotations

from src.graph import create_graph


def _stub_sweep_detection(_state: dict) -> dict:
    # Force the non-sweep path so the graph executes architect -> ... -> input_writer.
    return {"sweep_id": None}


def _stub_architect(_state: dict) -> dict:
    return {}


def _stub_intent_extraction(_state: dict) -> dict:
    return {}


def _stub_clarification(_state: dict) -> dict:
    return {}


def _stub_input_writer(_state: dict) -> dict:
    return {}


def _force_architect_to_intent(_state: dict) -> str:
    return "intent_extraction_node"


def _force_clarification_to_input_writer(_state: dict) -> str:
    return "input_writer_node"


def _force_manifest_to_input_writer(_state: dict) -> str:
    return "input_writer_node"


def _force_input_writer_to_complexity_evidence(_state: dict) -> str:
    return "complexity_evidence_node"


def _force_complexity_to_handler(_state: dict) -> str:
    return "complexity_evidence_handler"


def _force_complexity_to_end(_state: dict) -> str:
    return "end"


def test_unnumbered_002_routes_to_complexity_handler_when_radon_evidence_missing(monkeypatch) -> None:
    monkeypatch.setattr("src.graph.sweep_detection_node", _stub_sweep_detection)
    monkeypatch.setattr("src.graph.architect_node", _stub_architect)
    monkeypatch.setattr("src.graph.intent_extraction_node", _stub_intent_extraction)
    monkeypatch.setattr("src.graph.clarification_node", _stub_clarification)
    monkeypatch.setattr("src.graph.input_writer_node", _stub_input_writer)

    monkeypatch.setattr("src.graph._route_after_architect", _force_architect_to_intent)
    monkeypatch.setattr("src.graph._route_after_clarification", _force_clarification_to_input_writer)
    monkeypatch.setattr("src.graph._route_after_manifest_validation", _force_manifest_to_input_writer)
    monkeypatch.setattr("src.graph._route_after_input_writer", _force_input_writer_to_complexity_evidence)
    monkeypatch.setattr("src.graph._route_after_complexity_evidence", _force_complexity_to_handler)

    app = create_graph().compile()
    steps = list(app.stream({"prompt": "plan"}))

    node_sequence = [next(iter(step.keys())) for step in steps]
    assert node_sequence == [
        "sweep_detection_node",
        "architect_node",
        "intent_extraction_node",
        "clarification_node",
        "paper_manifest_gate_node",
        "input_writer_node",
        "complexity_evidence_node",
        "complexity_evidence_handler",
    ]


def test_unnumbered_002_routes_to_end_when_radon_evidence_present(monkeypatch) -> None:
    monkeypatch.setattr("src.graph.sweep_detection_node", _stub_sweep_detection)
    monkeypatch.setattr("src.graph.architect_node", _stub_architect)
    monkeypatch.setattr("src.graph.intent_extraction_node", _stub_intent_extraction)
    monkeypatch.setattr("src.graph.clarification_node", _stub_clarification)
    monkeypatch.setattr("src.graph.input_writer_node", _stub_input_writer)

    monkeypatch.setattr("src.graph._route_after_architect", _force_architect_to_intent)
    monkeypatch.setattr("src.graph._route_after_clarification", _force_clarification_to_input_writer)
    monkeypatch.setattr("src.graph._route_after_manifest_validation", _force_manifest_to_input_writer)
    monkeypatch.setattr("src.graph._route_after_input_writer", _force_input_writer_to_complexity_evidence)
    monkeypatch.setattr("src.graph._route_after_complexity_evidence", _force_complexity_to_end)

    app = create_graph().compile()
    steps = list(app.stream({"prompt": "plan"}))

    node_sequence = [next(iter(step.keys())) for step in steps]
    assert node_sequence == [
        "sweep_detection_node",
        "architect_node",
        "intent_extraction_node",
        "clarification_node",
        "paper_manifest_gate_node",
        "input_writer_node",
        "complexity_evidence_node",
    ]
