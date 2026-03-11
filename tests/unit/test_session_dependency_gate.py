from __future__ import annotations

from src.graph import (
    _route_after_sweep_detection,
    create_graph,
    session_dependency_handler_node,
)
from src.session_manager import (
    SESSION_DEPENDENCY_COMPLETION_MARKER,
    append_policy_audit,
    is_session_dependency_complete,
    merge_session_context,
    persist_session_result,
)


def test_merge_session_context_without_session_id_returns_arguments_copy():
    arguments = {"alpha": 1}
    merged = merge_session_context(session_id=None, arguments=arguments)

    assert merged == {"alpha": 1}
    assert merged is not arguments


def test_merge_session_context_with_session_removes_steps_when_not_provided(monkeypatch):
    def _get_session_context(_session_id: str):
        return {"persisted": "yes", "steps": ["old"]}

    def _persist_session_context(_session_id: str, _context: dict):
        return None

    monkeypatch.setattr(
        "src.session_manager._get_store_functions",
        lambda: (_get_session_context, _persist_session_context),
    )

    merged = merge_session_context(session_id="sess-1", arguments={"new": "arg"})
    assert merged == {"persisted": "yes", "new": "arg"}


def test_merge_session_context_with_session_keeps_steps_when_provided(monkeypatch):
    def _get_session_context(_session_id: str):
        return {"persisted": "yes", "steps": ["old"]}

    def _persist_session_context(_session_id: str, _context: dict):
        return None

    monkeypatch.setattr(
        "src.session_manager._get_store_functions",
        lambda: (_get_session_context, _persist_session_context),
    )

    merged = merge_session_context(session_id="sess-2", arguments={"steps": ["new"]})
    assert merged["steps"] == ["new"]


def test_append_policy_audit_appends_when_list_exists():
    context = {}
    append_policy_audit(
        context,
        tool_name="tool_a",
        surface="mcp",
        gate_required=True,
        bypass_applied=False,
        reason_code="ok",
        policy_version="v1",
        caller_action="run",
    )

    assert len(context["policy_audit"]) == 1
    assert context["policy_audit"][0]["tool_name"] == "tool_a"


def test_append_policy_audit_noop_when_audit_slot_not_list():
    context = {"policy_audit": "bad-shape"}
    append_policy_audit(
        context,
        tool_name="tool_b",
        surface="cli",
        gate_required=False,
        bypass_applied=False,
        reason_code="none",
        policy_version="v2",
    )

    assert context["policy_audit"] == "bad-shape"


def test_persist_session_result_returns_unchanged_when_session_missing():
    result = persist_session_result(session_id=None, context={"x": 1}, result={"ok": True})
    assert result == {"ok": True}


def test_persist_session_result_merges_context_and_result_for_dict(monkeypatch):
    persisted: dict[str, dict] = {}

    def _get_session_context(_session_id: str):
        return {}

    def _persist_session_context(session_id: str, context: dict):
        persisted[session_id] = context

    monkeypatch.setattr(
        "src.session_manager._get_store_functions",
        lambda: (_get_session_context, _persist_session_context),
    )

    result = {"output": "done"}
    returned = persist_session_result(
        session_id="sess-3",
        context={"request": 7},
        result=result,
    )

    assert persisted["sess-3"]["request"] == 7
    assert persisted["sess-3"]["output"] == "done"
    assert returned["session_id"] == "sess-3"


def test_persist_session_result_persists_context_for_non_dict_result(monkeypatch):
    persisted: dict[str, dict] = {}

    def _get_session_context(_session_id: str):
        return {}

    def _persist_session_context(session_id: str, context: dict):
        persisted[session_id] = context

    monkeypatch.setattr(
        "src.session_manager._get_store_functions",
        lambda: (_get_session_context, _persist_session_context),
    )

    returned = persist_session_result(
        session_id="sess-4",
        context={"request": "x"},
        result="raw-result",
    )

    assert returned == "raw-result"
    assert persisted["sess-4"] == {"request": "x"}


def test_dependency_completion_marker_check_supports_all_documented_shapes():
    assert is_session_dependency_complete({SESSION_DEPENDENCY_COMPLETION_MARKER: True})
    assert is_session_dependency_complete(
        {"session_markers": {SESSION_DEPENDENCY_COMPLETION_MARKER: True}}
    )
    assert is_session_dependency_complete({"completed_sessions": ["session_dependency_complete"]})
    assert not is_session_dependency_complete({SESSION_DEPENDENCY_COMPLETION_MARKER: False})


def test_route_after_sweep_detection_without_sweep_routes_architect():
    assert _route_after_sweep_detection({}) == "architect_node"


def test_route_after_sweep_detection_blocks_when_dependency_not_complete():
    route = _route_after_sweep_detection(
        {"sweep_id": "sweep-01", "enforce_session_dependency_gate": True}
    )
    assert route == "session_dependency_handler"


def test_route_after_sweep_detection_allows_when_dependency_complete():
    route = _route_after_sweep_detection(
        {
            "sweep_id": "sweep-01",
            "session_markers": {SESSION_DEPENDENCY_COMPLETION_MARKER: True},
        }
    )
    assert route == "sweep_execution_handler"


def test_dependency_handler_records_error_and_required_marker():
    result = session_dependency_handler_node({})
    assert "session must complete" in result["dependency_error"]
    assert result["required_marker"] == SESSION_DEPENDENCY_COMPLETION_MARKER


def test_graph_contains_dependency_handler_route_and_compiles():
    app = create_graph().compile()
    graph_def = app.get_graph()
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert ("sweep_detection_node", "session_dependency_handler") in edges
    assert ("session_dependency_handler", "__end__") in edges
