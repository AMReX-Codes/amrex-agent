from src.policy.gate_policy import evaluate_gate_policy


def test_gate_approved_flag_without_source_does_not_grant_permission() -> None:
    decision = evaluate_gate_policy(
        tool_name="run_simulation",
        context={"gate_approved": True},
        caller_action=None,
    )

    assert decision.gate_required is True
    assert decision.allowed is False
    assert decision.reason_code == "approval_required"


def test_gate_approved_with_human_source_allows_permission() -> None:
    decision = evaluate_gate_policy(
        tool_name="run_simulation",
        context={"gate_approved": True, "approval_source": "human"},
        caller_action=None,
    )

    assert decision.allowed is True
    assert decision.reason_code == "approved"
