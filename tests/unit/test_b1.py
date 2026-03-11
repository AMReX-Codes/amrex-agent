"""Unit tests for B1 Feature A dependency gate enforcement."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from src.graph import (
    _route_after_clarification,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    feature_a_dependency_handler_node,
    sweep_execution_handler_node,
)
from src.session_manager import (
    FEATURE_A_DEPENDENCY_ID,
    _get_store_functions,
    append_policy_audit,
    feature_a_dependency_failure_reason,
    feature_a_dependency_passed,
    merge_session_context,
    persist_session_result,
    resolve_dependency_state,
)


def test_merge_session_context_uses_stubbed_store(monkeypatch):
    """Persisted context is merged and stale workflow steps are cleared."""

    def _fake_get_store_functions():
        return (
            lambda _session_id: {"feature_a_verified": True, "steps": ["stale"]},
            lambda _session_id, _context: None,
        )

    monkeypatch.setattr("src.session_manager._get_store_functions", _fake_get_store_functions)

    merged = merge_session_context(
        session_id="session-1",
        arguments={"prompt": "run feature gate"},
    )

    assert merged["feature_a_verified"] is True
    assert merged["prompt"] == "run feature gate"
    assert "steps" not in merged


def test_merge_session_context_without_session_id_returns_copy():
    source = {"prompt": "x"}
    merged = merge_session_context(session_id=None, arguments=source)
    assert merged == source
    assert merged is not source


def test_merge_session_context_keeps_steps_when_explicit(monkeypatch):
    def _fake_get_store_functions():
        return (
            lambda _session_id: {"steps": ["persisted"]},
            lambda _session_id, _context: None,
        )

    monkeypatch.setattr("src.session_manager._get_store_functions", _fake_get_store_functions)
    merged = merge_session_context(session_id="session-2", arguments={"steps": ["new"]})
    assert merged["steps"] == ["new"]


def test_get_store_functions_returns_callables(monkeypatch):
    fake_module = SimpleNamespace(
        _get_session_context=lambda _session_id: {},
        _persist_session_context=lambda _session_id, _context: None,
    )
    monkeypatch.setitem(sys.modules, "src.mcp_tools", fake_module)
    get_context, persist_context = _get_store_functions()
    assert callable(get_context)
    assert callable(persist_context)


def test_append_policy_audit_appends_entry():
    context: dict[str, object] = {}
    append_policy_audit(
        context,
        tool_name="run_simulation",
        surface="mcp",
        gate_required=True,
        bypass_applied=False,
        reason_code="approval_required",
        policy_version="v1",
        caller_action="caller",
    )
    assert isinstance(context["policy_audit"], list)
    assert context["policy_audit"][0]["tool_name"] == "run_simulation"


def test_append_policy_audit_noop_for_non_list():
    context: dict[str, object] = {"policy_audit": "invalid"}
    append_policy_audit(
        context,
        tool_name="run_simulation",
        surface="mcp",
        gate_required=True,
        bypass_applied=False,
        reason_code="approval_required",
        policy_version="v1",
    )
    assert context["policy_audit"] == "invalid"


def test_persist_session_result_no_session_id_returns_result():
    payload = {"status": "ok"}
    assert persist_session_result(session_id=None, context={}, result=payload) == payload


def test_persist_session_result_persists_dict_and_stamps_session(monkeypatch):
    writes: list[tuple[str, dict[str, object]]] = []

    def _fake_get_store_functions():
        return (
            lambda _session_id: {},
            lambda session_id, context: writes.append((session_id, context)),
        )

    monkeypatch.setattr("src.session_manager._get_store_functions", _fake_get_store_functions)

    result = persist_session_result(
        session_id="session-3",
        context={"prompt": "run"},
        result={"status": "ok"},
    )

    assert result["session_id"] == "session-3"
    assert writes[0][0] == "session-3"
    assert writes[0][1]["status"] == "ok"
    assert writes[0][1]["prompt"] == "run"


def test_persist_session_result_handles_non_dict_payload(monkeypatch):
    writes: list[tuple[str, dict[str, object]]] = []

    def _fake_get_store_functions():
        return (
            lambda _session_id: {},
            lambda session_id, context: writes.append((session_id, context)),
        )

    monkeypatch.setattr("src.session_manager._get_store_functions", _fake_get_store_functions)
    result = persist_session_result(session_id="session-4", context={"a": 1}, result="ok")
    assert result == "ok"
    assert writes[0][1] == {"a": 1}


def test_resolve_dependency_state_hydrates_from_session(monkeypatch):
    monkeypatch.setattr(
        "src.session_manager.merge_session_context",
        lambda session_id, arguments: {**arguments, "feature_a_verified": True, "session_id": session_id},
    )

    resolved = resolve_dependency_state({"session_id": "abc"})
    assert resolved["feature_a_verified"] is True
    assert resolved["session_id"] == "abc"


def test_feature_a_dependency_passed_with_explicit_marker():
    assert feature_a_dependency_passed({"feature_a_verified": True}) is True
    assert feature_a_dependency_passed({"feature_a_verified": False}) is False


def test_feature_a_dependency_passed_with_legacy_marker():
    assert feature_a_dependency_passed({"feature_a_verification_passed": True}) is True
    assert feature_a_dependency_passed({"feature_a_verification_passed": False}) is False


def test_feature_a_dependency_passed_with_gate_approval_record():
    state = {
        "gate_approvals": [
            {
                "decision": "approved",
                "details": {"criterion": FEATURE_A_DEPENDENCY_ID},
            }
        ]
    }
    assert feature_a_dependency_passed(state) is True


def test_feature_a_dependency_defaults_to_fail_closed():
    assert feature_a_dependency_passed({}) is False
    assert feature_a_dependency_failure_reason({}) == "feature_a_dependency_unverified"
    assert (
        feature_a_dependency_failure_reason({"feature_a_verified": True})
        == "feature_a_dependency_satisfied"
    )


def test_feature_a_dependency_passed_handles_invalid_gate_entries():
    state = {
        "gate_approvals": [
            "bad-entry",
            {"details": "bad-details"},
            {"details": {"criterion": "other"}, "decision": "approved"},
            {"details": {"criterion": FEATURE_A_DEPENDENCY_ID}, "decision": "rejected"},
        ]
    }
    assert feature_a_dependency_passed(state) is False


def test_route_after_clarification_branches():
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"
    assert _route_after_clarification({}) == "input_writer_node"


def test_route_after_sweep_detection_blocks_without_feature_verification():
    route = _route_after_sweep_detection({"sweep_id": None})
    assert route == "feature_a_dependency_handler"


def test_route_after_sweep_detection_routes_architect_when_gate_passed():
    route = _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": None})
    assert route == "architect_node"


def test_route_after_sweep_detection_routes_sweep_handler_when_gate_passed():
    route = _route_after_sweep_detection(
        {"feature_a_verified": True, "sweep_id": "sweep_001"}
    )
    assert route == "sweep_execution_handler"


def test_route_after_sweep_detection_uses_session_stub(monkeypatch):
    def _fake_get_store_functions():
        return (
            lambda _session_id: {"feature_a_verified": True},
            lambda _session_id, _context: None,
        )

    monkeypatch.setattr("src.session_manager._get_store_functions", _fake_get_store_functions)

    route = _route_after_sweep_detection({"session_id": "s1"})
    assert route == "architect_node"


def test_feature_a_dependency_handler_node_records_rejection():
    updates = feature_a_dependency_handler_node(
        {"gate_approvals": "invalid", "errors_active": "invalid"}
    )

    assert updates["mode"] == "terminal"
    assert updates["reviewer_failure_category"] == "dependency_gate"
    assert updates["gate_approvals"][-1]["decision"] == "rejected"
    assert updates["gate_approvals"][-1]["details"]["criterion"] == FEATURE_A_DEPENDENCY_ID
    assert "feature_a_dependency_unverified" in updates["errors_active"]


def test_feature_a_dependency_handler_deduplicates_existing_reason():
    updates = feature_a_dependency_handler_node(
        {
            "feature_a_verified": False,
            "gate_approvals": [],
            "errors_active": ["feature_a_dependency_unverified"],
        }
    )
    assert updates["errors_active"].count("feature_a_dependency_unverified") == 1


def test_clarification_handler_node_logs_and_returns_state(capsys):
    state = {"clarification_questions": ["q1"]}
    returned = clarification_handler_node(state)
    out = capsys.readouterr().out
    assert "Clarification needed:" in out
    assert returned is state


def test_sweep_execution_handler_node_logs_and_returns_state(capsys):
    state = {"sweep_id": "sweep-1", "sweep_parameter": "run_ntasks"}
    returned = sweep_execution_handler_node(state)
    out = capsys.readouterr().out
    assert "Sweep detected:" in out
    assert returned is state


def test_graph_wires_dependency_handler_from_sweep_detection():
    app = create_graph().compile()
    graph_def = app.get_graph()
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert ("sweep_detection_node", "feature_a_dependency_handler") in edges
    assert ("feature_a_dependency_handler", "__end__") in edges
