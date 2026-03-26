from src.models.sweep_schemas import ChildJobStatus, ChildWorkflowState, ParentSweepState, SweepSpec, SweepType
from src.services.sweep_orchestrator import _poll_until_complete, poll_child_status


def test_poll_child_status_unknown_status_fails_submitted_child() -> None:
    child = ChildWorkflowState(
        sweep_id="s1",
        sweep_child_id="s1-child-0",
        parameter_name="viscosity",
        parameter_value=0.1,
        status=ChildJobStatus.submitted,
    )

    updated = poll_child_status(child, lambda _child: {"status": "mystery_state"})
    assert updated.status == ChildJobStatus.failed
    assert updated.failure_reason == "poll returned unknown/unmappable status"


def test_poll_until_complete_unknown_status_does_not_wait_full_timeout() -> None:
    spec = SweepSpec(
        sweep_type=SweepType.physics,
        parameter_name="viscosity",
        parameter_values=[0.1, 0.2],
        sweep_id="s2",
        metadata={},
    )
    child = ChildWorkflowState(
        sweep_id="s2",
        sweep_child_id="s2-child-0",
        parameter_name="viscosity",
        parameter_value=0.1,
        status=ChildJobStatus.submitted,
    )
    parent = ParentSweepState(
        sweep_id="s2",
        sweep_spec=spec,
        children=[child],
        total_count=1,
        completed_count=0,
        failed_count=0,
    )

    result = _poll_until_complete(parent, poll_fn=lambda _child: {"status": "unknown"})
    assert result.failed_count == 1
    assert result.completed_count == 0
    assert result.children[0].status == ChildJobStatus.failed
    assert result.children[0].failure_reason == "poll returned unknown/unmappable status"
