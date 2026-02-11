from unittest.mock import Mock

from langgraph.graph import END

from src.router_func import route_after_reviewer, route_after_router_gate
from src.nodes.router_gate_node import router_gate_node


def _config(strategy="selective", points=None):
    config = Mock()
    config.router_gate_strategy = strategy
    config.router_gate_points = points or []
    return config


def test_route_after_reviewer_routes_to_gate_when_enabled():
    state = {
        "config": _config(points=["reviewer"]),
        "mode": "proceed",
        "retry_count": 0,
        "max_retries": 3,
    }

    assert route_after_reviewer(state) == "router_gate"


def test_route_after_reviewer_skips_gate_when_disabled():
    state = {
        "config": _config(strategy="off"),
        "mode": "proceed",
        "retry_count": 0,
        "max_retries": 3,
    }

    assert route_after_reviewer(state) == "input_writer"


def test_router_gate_node_builds_gate_proposal():
    state = {
        "config": _config(points=["reviewer"]),
        "mode": "proceed",
        "retry_count": 0,
        "max_retries": 3,
        "workflow_history": [{"node": "reviewer", "details": {}}],
    }

    updates = router_gate_node(state)

    proposal = updates.get("gate_proposal", {})
    assert proposal.get("step_id") == "reviewer"
    assert len(proposal.get("options", [])) >= 1
    assert updates.get("router_gate", {}).get("resume_node") == "input_writer"


def test_route_after_router_gate_resumes_after_approval():
    state = {"router_gate": {"status": "approved", "resume_node": "input_writer"}}

    assert route_after_router_gate(state) == "input_writer"


def test_route_after_router_gate_blocks_when_pending():
    state = {"router_gate": {"status": "pending", "resume_node": "input_writer"}}

    assert route_after_router_gate(state) == END
