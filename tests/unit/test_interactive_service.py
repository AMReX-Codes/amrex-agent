"""Unit tests for shared interactive invocation + gate policy behavior."""

from __future__ import annotations

from src.policy.gate_policy import evaluate_gate_policy
from src.interactive_service import invoke_tool


def test_gate_policy_requires_approval_for_critical_tool():
    decision = evaluate_gate_policy(
        tool_name="run_simulation",
        context={},
        caller_action=None,
    )
    assert decision.gate_required is True
    assert decision.allowed is False
    assert decision.reason_code == "approval_required"


def test_gate_policy_accepts_approval_token_for_critical_tool():
    decision = evaluate_gate_policy(
        tool_name="run_simulation",
        context={"approval_token": "approved"},
        caller_action=None,
    )
    assert decision.gate_required is True
    assert decision.allowed is True
    assert decision.reason_code == "approved"


def test_gate_policy_bypasses_demo_allowlist():
    decision = evaluate_gate_policy(
        tool_name="execute_workflow",
        context={"steps": ["create_simulation_plan", "run_simulation"]},
        caller_action="amrex_demo_agent",
    )
    assert decision.bypass_applied is True
    assert decision.allowed is True
    assert decision.reason_code == "demo_allowlist"


def test_gate_policy_checks_execute_workflow_steps():
    denied = evaluate_gate_policy(
        tool_name="execute_workflow",
        context={"steps": ["create_simulation_plan", "run_simulation"]},
        caller_action=None,
    )
    allowed = evaluate_gate_policy(
        tool_name="execute_workflow",
        context={"steps": ["create_simulation_plan"]},
        caller_action=None,
    )
    assert denied.allowed is False
    assert allowed.allowed is True


def test_gate_policy_execute_workflow_defaults_to_gated_when_steps_omitted():
    decision = evaluate_gate_policy(
        tool_name="execute_workflow",
        context={},
        caller_action=None,
    )
    assert decision.allowed is False
    assert decision.reason_code == "approval_required"


def test_invoke_tool_blocks_critical_without_approval(monkeypatch):
    monkeypatch.setattr(
        "src.interactive_service.merge_session_context",
        lambda session_id, arguments: dict(arguments),
    )
    monkeypatch.setattr(
        "src.interactive_service.append_policy_audit",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "src.interactive_service.persist_session_result",
        lambda session_id, context, result: result,
    )
    monkeypatch.setattr(
        "src.interactive_service.dispatch_tool",
        lambda name, context: {"status": "should-not-run"},
    )

    result = invoke_tool("run_simulation", {}, surface="mcp")
    assert result["error"] == "Gate approval required"
    assert result["gate"]["reason_code"] == "approval_required"


def test_invoke_tool_allows_demo_bypass(monkeypatch):
    monkeypatch.setattr(
        "src.interactive_service.merge_session_context",
        lambda session_id, arguments: dict(arguments),
    )
    monkeypatch.setattr(
        "src.interactive_service.append_policy_audit",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "src.interactive_service.persist_session_result",
        lambda session_id, context, result: result,
    )
    monkeypatch.setattr(
        "src.interactive_service.dispatch_tool",
        lambda name, context: {"status": "ok"},
    )

    result = invoke_tool(
        "execute_workflow",
        {"steps": ["create_simulation_plan", "run_simulation"]},
        surface="aisac",
        caller_action="amrex_demo_agent",
    )
    assert result["status"] == "ok"
    assert result["gate"]["gate_bypassed"] is True
