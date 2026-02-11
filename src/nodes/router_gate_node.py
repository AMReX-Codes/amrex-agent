"""
Router gate node - emits gate proposals and applies resolutions.
"""
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from src.models import GraphState
from src.router_func import (
    _route_after_analysis_core,
    _route_after_architect_core,
    _route_after_input_writer_core,
    _route_after_reviewer_core,
    _route_after_runner_core,
    _route_after_visualization_core,
)

logger = logging.getLogger(__name__)


def _get_last_node(state: GraphState) -> str | None:
    for entry in reversed(state.get("workflow_history", []) or []):
        node = entry.get("node")
        if node and node not in {"router_gate", "preconfirm_gate"}:
            return node
    return None


def _compute_resume_node(last_node: str, state: GraphState) -> str | None:
    routing_map = {
        "architect": _route_after_architect_core,
        "reviewer": _route_after_reviewer_core,
        "input_writer": _route_after_input_writer_core,
        "runner": _route_after_runner_core,
        "analysis": _route_after_analysis_core,
        "visualization": _route_after_visualization_core,
    }
    route_fn = routing_map.get(last_node)
    if not route_fn:
        return None
    state_snapshot = dict(state)
    return route_fn(state_snapshot)


def router_gate_node(state: GraphState) -> dict[str, Any]:
    """
    Emit a gate proposal or apply a gate resolution for router-level gating.
    """
    iteration = state.get("iteration", 0)
    workflow_history = state.get("workflow_history", [])
    last_node = _get_last_node(state)
    if not last_node:
        logger.warning("[ROUTER_GATE] Missing last node; skipping router gate.")
        return {
            "workflow_history": workflow_history + [{
                "node": "router_gate",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "skipped",
                "iteration": iteration,
                "details": {"reason": "missing_last_node"},
            }]
        }

    resume_node = _compute_resume_node(last_node, state)
    if not resume_node:
        logger.warning("[ROUTER_GATE] Missing resume node; skipping router gate.")
        return {
            "workflow_history": workflow_history + [{
                "node": "router_gate",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "skipped",
                "iteration": iteration,
                "details": {"reason": "missing_resume_node", "gate_point": last_node},
            }]
        }

    router_gate = state.get("router_gate", {}) if isinstance(state.get("router_gate", {}), dict) else {}
    resolution = state.get("gate_resolution") if isinstance(state.get("gate_resolution"), dict) else None

    if resolution and router_gate and resolution.get("gate_id") == router_gate.get("gate_id"):
        action = resolution.get("action")
        status_map = {"approve": "approved", "reject": "rejected", "cancel": "canceled"}
        status = status_map.get(action, "rejected")
        updated_gate = {
            **router_gate,
            "status": status,
            "resolution": resolution,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        history_entry = {
            "node": "router_gate",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": status,
            "iteration": iteration,
            "details": {
                "gate_point": last_node,
                "gate_id": updated_gate.get("gate_id"),
                "resume_node": resume_node,
                "selection": resolution.get("selection"),
                "feedback": resolution.get("feedback"),
            },
        }
        return {
            "router_gate": updated_gate,
            "gate_resolution": None,
            "workflow_history": workflow_history + [history_entry],
        }

    if router_gate.get("status") == "pending":
        return {}

    gate_id = str(uuid4())
    proposal = {
        "gate_id": gate_id,
        "step_id": last_node,
        "options": [
            {
                "option_id": "continue",
                "summary": f"Proceed to {resume_node}",
                "rationale": "Router gate confirmation required.",
            }
        ],
        "decision_type": "select",
        "resume_context": {"resume_node": resume_node, "gate_point": last_node},
    }
    pending_gate = {
        "gate_id": gate_id,
        "gate_point": last_node,
        "status": "pending",
        "resume_node": resume_node,
    }
    history_entry = {
        "node": "router_gate",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": "proposed",
        "iteration": iteration,
        "details": {
            "gate_point": last_node,
            "gate_id": gate_id,
            "resume_node": resume_node,
        },
    }
    return {
        "router_gate": pending_gate,
        "gate_proposal": proposal,
        "workflow_history": workflow_history + [history_entry],
    }


__all__ = ["router_gate_node"]
