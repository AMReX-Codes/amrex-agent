from types import SimpleNamespace

import importlib

reviewer_node_module = importlib.import_module("src.nodes.reviewer_node")


def _base_state(config):
    return {
        "config": config,
        "prompt": "Run ERF ABL and diagnose failures",
        "workflow_history": [
            {
                "node": "architect",
                "details": {
                    "selected_case": "ERF/Exec/ABL",
                    "modifications": [("max_step", "10")],
                    "baseline": {"code_name": "ERF", "local_path": "ERF/Exec/ABL"},
                },
            }
        ],
        "iteration": 0,
        "retry_count": 0,
        "max_retries": 3,
        "review_context": "post_execution",
        "analysis_report": {"status": "failed", "issues": ["runtime crash"]},
        "errors_active": [],
        "errors_found": [],
        "errors_fixed": [],
    }


def test_post_execution_feasibility_llm_payload_propagates_to_state_and_history(monkeypatch):
    config = SimpleNamespace(
        preconfirm_gate=False,
        preconfirm_gate_auto_approve=False,
        retry_guidance_use_llm=False,
        reviewer_feasibility_llm_enabled=True,
        llm_model="test-model",
        baseline_switch_after_retries=3,
        clarification_route_on_intent_missing_only=True,
        enable_clarification_subgraph=True,
    )

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan):
            return SimpleNamespace(
                mode="proceed",
                violations=[],
                summary="ok",
                available_schema_params=[],
                required_solver=None,
                forbidden_path_patterns=[],
                preferred_path_patterns=[],
                excluded_cases=[],
                schema_escalation_required=False,
                replan_reason_codes=[],
            )

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    monkeypatch.setattr("src.config.get_llm_client", lambda _config: object())
    monkeypatch.setattr(
        "src.utils.llm_calls.call_llm",
        lambda *_args, **_kwargs: SimpleNamespace(
            feasible=False,
            intent_consistent=False,
            diagnosis="Plan diverges from requested objective after failed run",
            guidance={"required_solver": "ERF", "excluded_cases": ["Exec/DevTests/BadCase"]},
        ),
    )

    updates = reviewer_node_module.reviewer_node(_base_state(config))
    rg = updates["reviewer_guidance"]

    assert rg["feasible"] is False
    assert rg["intent_consistent"] is False
    assert isinstance(rg["diagnosis"], str) and rg["diagnosis"]
    assert isinstance(rg["guidance"], dict)
    assert rg["required_solver"] == "ERF"
    assert "Exec/DevTests/BadCase" in rg["excluded_cases"]

    history_guidance = updates["workflow_history"][-1]["details"]["reviewer_guidance"]
    assert history_guidance["feasible"] is False
    assert history_guidance["intent_consistent"] is False
    assert isinstance(history_guidance["diagnosis"], str) and history_guidance["diagnosis"]
    assert isinstance(history_guidance["guidance"], dict)


def test_post_execution_feasibility_llm_failure_uses_typed_fallback(monkeypatch):
    config = SimpleNamespace(
        preconfirm_gate=False,
        preconfirm_gate_auto_approve=False,
        retry_guidance_use_llm=False,
        reviewer_feasibility_llm_enabled=True,
        llm_model="test-model",
        baseline_switch_after_retries=3,
        clarification_route_on_intent_missing_only=True,
        enable_clarification_subgraph=True,
    )

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan):
            return SimpleNamespace(
                mode="proceed",
                violations=[],
                summary="ok",
                available_schema_params=[],
                required_solver=None,
                forbidden_path_patterns=[],
                preferred_path_patterns=[],
                excluded_cases=[],
                schema_escalation_required=False,
                replan_reason_codes=[],
            )

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)
    monkeypatch.setattr("src.config.get_llm_client", lambda _config: object())
    monkeypatch.setattr(
        "src.utils.llm_calls.call_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("llm unavailable")),
    )

    updates = reviewer_node_module.reviewer_node(_base_state(config))
    rg = updates["reviewer_guidance"]

    assert isinstance(rg["feasible"], bool)
    assert isinstance(rg["intent_consistent"], bool)
    assert isinstance(rg["diagnosis"], str) and rg["diagnosis"]
    assert isinstance(rg["guidance"], dict)


def test_pre_execution_missing_explicit_assignment_routes_to_intent_retry(monkeypatch):
    config = SimpleNamespace(
        preconfirm_gate=False,
        preconfirm_gate_auto_approve=False,
        retry_guidance_use_llm=False,
        reviewer_feasibility_llm_enabled=True,
        reviewer_intent_coverage_enabled=True,
        llm_model="test-model",
        baseline_switch_after_retries=3,
        clarification_route_on_intent_missing_only=True,
        enable_clarification_subgraph=True,
    )

    class FakeOrchestrator:
        def __init__(self, _config):
            pass

        def validate_plan(self, _plan):
            return SimpleNamespace(
                mode="proceed",
                violations=[],
                summary="ok",
                available_schema_params=[],
                required_solver=None,
                forbidden_path_patterns=[],
                preferred_path_patterns=[],
                excluded_cases=[],
                schema_escalation_required=False,
                replan_reason_codes=[],
            )

    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", FakeOrchestrator)

    state = {
        "config": config,
        "prompt": "Configure ERF ABL with max_step = 10 and dt = 20",
        "workflow_history": [
            {
                "node": "architect",
                "details": {
                    "selected_case": "ERF/Exec/ABL",
                    "modifications": [("max_step", "10")],
                    "baseline": {"code_name": "ERF", "local_path": "ERF/Exec/ABL"},
                },
            }
        ],
        "iteration": 0,
        "retry_count": 0,
        "max_retries": 3,
        "errors_active": [],
        "errors_found": [],
        "errors_fixed": [],
    }

    updates = reviewer_node_module.reviewer_node(state)
    assert updates["mode"] == "retry"
    assert "intent_coverage_feedback" in updates
    unresolved = updates["intent_coverage_feedback"]["unresolved_requests"]
    assert unresolved, "expected unresolved explicit assignment requests"
    assert any(item[0] == "dt" for item in unresolved)
