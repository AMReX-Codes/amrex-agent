import pytest


def _build_workflow_history(
    *,
    code_case: str,
    param_key: str,
    intent_value: str,
    repaired_value: str,
) -> list[dict]:
    return [
        {
            "node": "architect",
            "iteration": 1,
            "details": {
                "selected_case": code_case,
                "modifications": [("max_step", "10")],
            },
        },
        {
            "node": "reviewer",
            "action": "intent_coverage_retry",
            "iteration": 1,
            "details": {"required_assignments": {param_key: intent_value}},
        },
        {
            "node": "architect",
            "iteration": 2,
            "details": {
                "selected_case": code_case,
                "modifications": [("max_step", "10"), (param_key, intent_value)],
            },
        },
        {"node": "runner", "iteration": 2, "details": {"status": "failed"}},
        {
            "node": "analysis",
            "iteration": 2,
            "details": {
                "status": "failed",
                "postexec_repair_hints": {"required_assignments": {param_key: repaired_value}},
            },
        },
        {
            "node": "reviewer",
            "action": "validation_completed",
            "iteration": 2,
            "details": {
                "review_context": "post_execution",
                "postexec_repair_feedback": {"required_assignments": {param_key: repaired_value}},
            },
        },
        {
            "node": "architect",
            "iteration": 3,
            "details": {
                "selected_case": code_case,
                "modifications": [("max_step", "10"), (param_key, repaired_value)],
            },
        },
        {"node": "runner", "iteration": 3, "details": {"status": "completed"}},
        {
            "node": "analysis",
            "iteration": 3,
            "details": {
                "status": "success",
            },
        },
    ]


def _assert_two_phase_fix_contract(
    workflow_history: list[dict],
    *,
    param_key: str,
    intent_value: str,
    repaired_value: str,
) -> None:
    runner_indices = [i for i, e in enumerate(workflow_history) if e.get("node") == "runner"]
    assert len(runner_indices) >= 2

    first_runner_idx = runner_indices[0]
    postexec_review_indices = [
        i
        for i, e in enumerate(workflow_history)
        if e.get("node") == "reviewer"
        and e.get("details", {}).get("review_context") == "post_execution"
    ]
    assert postexec_review_indices
    assert any(first_runner_idx < idx < runner_indices[1] for idx in postexec_review_indices)

    intent_indices = [
        i
        for i, e in enumerate(workflow_history)
        if e.get("node") == "reviewer" and e.get("action") == "intent_coverage_retry"
    ]
    assert intent_indices
    assert any(
        (workflow_history[i].get("details", {}).get("required_assignments", {}) or {}).get(param_key) == intent_value
        and i < first_runner_idx
        for i in intent_indices
    )

    assert any(
        (workflow_history[i].get("details", {}).get("postexec_repair_feedback", {}).get("required_assignments", {}) or {}).get(param_key)
        == repaired_value
        for i in postexec_review_indices
    )
    assert repaired_value != intent_value

    assert any(
        e.get("node") == "architect"
        and i < first_runner_idx
        and any(
            isinstance(m, (list, tuple))
            and len(m) >= 2
            and str(m[0]) == param_key
            and str(m[1]) == intent_value
            for m in e.get("details", {}).get("modifications", [])
        )
        for i, e in enumerate(workflow_history)
    )
    assert any(
        e.get("node") == "architect"
        and any(post_i < i for post_i in postexec_review_indices)
        and any(
            isinstance(m, (list, tuple))
            and len(m) >= 2
            and str(m[0]) == param_key
            and str(m[1]) == repaired_value
            for m in e.get("details", {}).get("modifications", [])
        )
        for i, e in enumerate(workflow_history)
    )

    analysis_entries = [e for e in workflow_history if e.get("node") == "analysis"]
    assert analysis_entries
    assert analysis_entries[-1].get("details", {}).get("status") == "success"


@pytest.mark.unit
def test_two_phase_fix_contract_pelec_cfl() -> None:
    workflow_history = _build_workflow_history(
        code_case="PeleC/Exec/RegTests/PMF",
        param_key="amr.cfl",
        intent_value="0.9",
        repaired_value="0.45",
    )
    _assert_two_phase_fix_contract(
        workflow_history,
        param_key="amr.cfl",
        intent_value="0.9",
        repaired_value="0.45",
    )


@pytest.mark.unit
def test_two_phase_fix_contract_pelelmex_reaction_dt() -> None:
    workflow_history = _build_workflow_history(
        code_case="PeleLMeX/Exec/RegTests/FlameSheet",
        param_key="pelelm.react_dt",
        intent_value="1.0e-5",
        repaired_value="2.5e-6",
    )
    _assert_two_phase_fix_contract(
        workflow_history,
        param_key="pelelm.react_dt",
        intent_value="1.0e-5",
        repaired_value="2.5e-6",
    )


@pytest.mark.unit
def test_two_phase_fix_contract_remora_fixed_dt() -> None:
    workflow_history = _build_workflow_history(
        code_case="REMORA/Exec/RegTests/Upwelling",
        param_key="remora.fixed_dt",
        intent_value="30",
        repaired_value="7.5",
    )
    _assert_two_phase_fix_contract(
        workflow_history,
        param_key="remora.fixed_dt",
        intent_value="30",
        repaired_value="7.5",
    )


@pytest.mark.unit
def test_two_phase_fix_contract_incflo_cfl() -> None:
    workflow_history = _build_workflow_history(
        code_case="incflo/Exec/TaylorGreenVortex",
        param_key="incflo.cfl",
        intent_value="0.8",
        repaired_value="0.4",
    )
    _assert_two_phase_fix_contract(
        workflow_history,
        param_key="incflo.cfl",
        intent_value="0.8",
        repaired_value="0.4",
    )
