"""Unit tests for AISAC-compatible action and response contracts."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types


def _install_stub_mcp_tools(monkeypatch, captured_payloads: dict):
    module = types.ModuleType("src.mcp_tools")

    def _query(payload):
        captured_payloads["knowledge"] = payload
        return {
            "answer": "stub-answer",
            "method": "stub-method",
            "confidence": 0.9,
            "sources": ["stub-source"],
        }

    def _execute(payload):
        captured_payloads["demo"] = payload
        return {
            "final": {
                "selected_case": "PeleLMeX/Exec/Production/JetInCrossflow",
                "job_status": "completed",
                "run_directory": "/tmp/demo-run",
            }
        }

    module.mcp_query_knowledge = _query
    module.mcp_execute_workflow = _execute
    monkeypatch.setitem(sys.modules, "src.mcp_tools", module)


def _install_stub_academy(monkeypatch):
    academy = types.ModuleType("academy")
    academy_agent = types.ModuleType("academy.agent")
    academy_exchange = types.ModuleType("academy.exchange")
    academy_exchange_cloud = types.ModuleType("academy.exchange.cloud")
    academy_exchange_client = types.ModuleType("academy.exchange.cloud.client")
    academy_manager = types.ModuleType("academy.manager")

    class Agent:  # noqa: D401
        """Minimal stub Agent."""

    def action(func):
        return func

    class HttpExchangeFactory:  # noqa: D401
        """Minimal stub HttpExchangeFactory."""

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class Manager:  # noqa: D401
        """Minimal stub Manager."""

        @classmethod
        async def from_exchange_factory(cls, **kwargs):
            raise RuntimeError("Not used in these unit tests")

    academy_agent.Agent = Agent
    academy_agent.action = action
    academy_exchange_client.HttpExchangeFactory = HttpExchangeFactory
    academy_manager.Manager = Manager

    monkeypatch.setitem(sys.modules, "academy", academy)
    monkeypatch.setitem(sys.modules, "academy.agent", academy_agent)
    monkeypatch.setitem(sys.modules, "academy.exchange", academy_exchange)
    monkeypatch.setitem(sys.modules, "academy.exchange.cloud", academy_exchange_cloud)
    monkeypatch.setitem(sys.modules, "academy.exchange.cloud.client", academy_exchange_client)
    monkeypatch.setitem(sys.modules, "academy.manager", academy_manager)


def test_aisac_logic_contracts(monkeypatch):
    captured = {}
    _install_stub_mcp_tools(monkeypatch, captured)

    code = importlib.import_module("aisac_compatible_amrex_agent_code")

    knowledge = code.process_task("What is the default solver?", "{}")
    assert set(knowledge.keys()) == {"answer", "rationale"}
    assert knowledge["answer"].startswith("# AMReX Knowledge Response")
    assert "## Answer" in knowledge["answer"]
    assert "## Metadata" in knowledge["answer"]
    assert "- Solver: `PeleLMeX`" in knowledge["answer"]
    assert knowledge["rationale"] == "Answered via mcp_query_knowledge."
    assert captured["knowledge"]["code"] == "PeleLMeX"

    demo = code.run_demo_workflow("Run demo", "{}")
    assert set(demo.keys()) == {"answer", "rationale"}
    assert demo["answer"].startswith("# AMReX Demo Workflow Result")
    assert "## Summary" in demo["answer"]
    assert "## Run Details" in demo["answer"]
    assert "- Job Status: `completed`" in demo["answer"]
    assert "execute_workflow" in demo["rationale"]
    assert captured["demo"]["steps"] == ["create_simulation_plan", "run_simulation"]
    assert captured["demo"]["submit"]["dry_run"] is True


def test_aisac_agent_actions_return_answer_rationale_json(monkeypatch):
    _install_stub_mcp_tools(monkeypatch, {})
    _install_stub_academy(monkeypatch)

    wrapper = importlib.import_module("aisac_compatible_amrex_mcp_agent")
    monkeypatch.setattr(
        wrapper,
        "process_task",
        lambda task, context: {"answer": f"k:{task}", "rationale": "knowledge"},
    )
    monkeypatch.setattr(
        wrapper,
        "run_demo_workflow",
        lambda example, context: {"answer": f"d:{example}", "rationale": "demo"},
    )

    agent = wrapper.AISACCompatibleAMReXAgent()
    knowledge_raw = asyncio.run(agent.amrex_knowledge_agent("q1", "{}"))
    demo_raw = asyncio.run(agent.amrex_demo_agent("q2", "{}"))

    knowledge = json.loads(knowledge_raw)
    demo = json.loads(demo_raw)
    assert set(knowledge.keys()) == {"answer", "rationale"}
    assert set(demo.keys()) == {"answer", "rationale"}
    assert knowledge["answer"] == "k:q1"
    assert demo["answer"] == "d:q2"
