"""Regression tests for invocation security and Academy response wrapping."""

from __future__ import annotations

import asyncio
import importlib
import sys
import types


def _install_stub_mcp_deps(monkeypatch):
    mcp = types.ModuleType("mcp")
    mcp_server = types.ModuleType("mcp.server")
    mcp_stdio = types.ModuleType("mcp.server.stdio")

    class _Server:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_tools(self):
            def _decorator(fn):
                return fn

            return _decorator

        def call_tool(self):
            def _decorator(fn):
                return fn

            return _decorator

        def create_initialization_options(self):
            return {}

    class _Tool:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    async def _stdio_server():  # pragma: no cover
        raise RuntimeError("not used")

    mcp.Tool = _Tool
    mcp_server.Server = _Server
    mcp_stdio.stdio_server = _stdio_server
    monkeypatch.setitem(sys.modules, "mcp", mcp)
    monkeypatch.setitem(sys.modules, "mcp.server", mcp_server)
    monkeypatch.setitem(sys.modules, "mcp.server.stdio", mcp_stdio)


def _install_stub_academy(monkeypatch):
    academy = types.ModuleType("academy")
    academy_agent = types.ModuleType("academy.agent")

    class Agent:
        pass

    def action(func):
        return func

    academy_agent.Agent = Agent
    academy_agent.action = action
    monkeypatch.setitem(sys.modules, "academy", academy)
    monkeypatch.setitem(sys.modules, "academy.agent", academy_agent)


def _install_stub_core(monkeypatch):
    mcp_tools = types.ModuleType("src.mcp_tools")
    mcp_tools.AMReXAgentConfig = object
    mcp_tools.AnalysisService = object
    mcp_tools.ArchitectService = object
    mcp_tools.InputWriterService = object
    mcp_tools.LocalRunner = object
    mcp_tools.PeleKnowledgeService = object
    mcp_tools.SimulationPlan = object
    mcp_tools.SuperfacilityRunner = object
    mcp_tools.ValidationService = object
    mcp_tools.VisualizationService = object
    mcp_tools.config = types.SimpleNamespace(
        environment="test",
        faiss_db_path="/tmp/faiss",
        knowledge_base_path="/tmp/kb",
    )
    mcp_tools.get_tool_specs = lambda: []
    # Names imported by mcp_server; bodies are irrelevant in this test.
    mcp_tools.mcp_analyze_results = lambda _p: {}
    mcp_tools.mcp_apply_plan = lambda _p: {}
    mcp_tools.mcp_create_proposed_modifications_with_plan = lambda _p: {}
    mcp_tools.mcp_create_simulation_plan = lambda _p: {}
    mcp_tools.mcp_execute_workflow = lambda _p: {}
    mcp_tools.mcp_generate_visualizations = lambda _p: {}
    mcp_tools.mcp_query_knowledge = lambda _p: {}
    mcp_tools.mcp_run_simulation = lambda _p: {}
    mcp_tools.mcp_select_baseline_case = lambda _p: {}
    mcp_tools.mcp_setup_job = lambda _p: {}
    mcp_tools.mcp_stage_out_globus = lambda _p: {}
    mcp_tools.mcp_validate_config = lambda _p: {}
    mcp_tools.mcp_validate_inputs = lambda _p: {}
    mcp_tools._get_session_context = lambda _s: {}
    mcp_tools._persist_session_context = lambda _s, _c: None
    monkeypatch.setitem(sys.modules, "src.mcp_tools", mcp_tools)


def test_mcp_server_ignores_untrusted_caller_action(monkeypatch):
    _install_stub_mcp_deps(monkeypatch)
    _install_stub_core(monkeypatch)

    captured = {}
    interactive_service = types.ModuleType("src.interactive_service")

    def _invoke_tool(name, arguments=None, **kwargs):
        captured["name"] = name
        captured["arguments"] = dict(arguments or {})
        captured["kwargs"] = kwargs
        return {"ok": True}

    interactive_service.invoke_tool = _invoke_tool
    monkeypatch.setitem(sys.modules, "src.interactive_service", interactive_service)

    module = importlib.import_module("mcp_server")
    result = asyncio.run(
        module.call_tool(
            "run_simulation",
            {"caller_action": "amrex_demo_agent", "foo": "bar"},
        )
    )

    assert result == {"ok": True}
    assert captured["arguments"]["caller_action"] == "amrex_demo_agent"
    assert captured["kwargs"]["caller_action"] is None


def test_academy_wrapper_marks_error_status(monkeypatch):
    _install_stub_academy(monkeypatch)

    module = importlib.import_module("src.academy_mcp_agent")
    wrapped = module.AMReXMCPAgent._maybe_wrap_response_rationale(
        {"error": "blocked by gate"},
        include_response_rationale=True,
    )
    assert wrapped["status"] == "error"
    assert wrapped["response"] == "error: blocked by gate"
    assert wrapped["data"]["error"] == "blocked by gate"


def test_academy_wrapper_preserves_error_status_field(monkeypatch):
    _install_stub_academy(monkeypatch)

    module = importlib.import_module("src.academy_mcp_agent")
    wrapped = module.AMReXMCPAgent._maybe_wrap_response_rationale(
        {"status": "error", "message": "tool failed"},
        include_response_rationale=True,
    )
    assert wrapped["status"] == "error"
    assert wrapped["response"] == "error"
    assert wrapped["data"]["message"] == "tool failed"


def test_academy_wrapper_does_not_force_ok_for_non_success_status(monkeypatch):
    _install_stub_academy(monkeypatch)

    module = importlib.import_module("src.academy_mcp_agent")
    wrapped = module.AMReXMCPAgent._maybe_wrap_response_rationale(
        {"status": "failed", "reason": "rate_limited"},
        include_response_rationale=True,
    )
    assert wrapped["status"] == "error"
    assert wrapped["response"] == "failed"
    assert wrapped["data"]["reason"] == "rate_limited"


def test_academy_call_tool_wraps_exception_when_requested(monkeypatch):
    _install_stub_academy(monkeypatch)

    module = importlib.import_module("src.academy_mcp_agent")

    async def _raise_to_thread(_func, *_args, **_kwargs):
        raise RuntimeError("transport unavailable")

    monkeypatch.setattr(module.asyncio, "to_thread", _raise_to_thread)
    result = asyncio.run(
        module.AMReXMCPAgent().call_tool(
            "query_knowledge",
            {"query": "test"},
            include_response_rationale=True,
        )
    )
    assert result["status"] == "error"
    assert result["response"] == "error: transport unavailable"
    assert result["data"]["error"] == "transport unavailable"
    assert "traceback" in result["data"]
