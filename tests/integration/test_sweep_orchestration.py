from types import SimpleNamespace
from unittest.mock import Mock

from src.models.sweep_schemas import SweepSpec, SweepType
from src.services.sweep_orchestrator import orchestrate_sweep


def test_sweep_orchestration_end_to_end():
    spec = SweepSpec(
        sweep_type=SweepType.physics,
        parameter_name="transport.viscosity",
        parameter_values=[0.1, 0.2],
        sweep_id="sweep-integration-1",
        metadata={},
    )

    architect_fn = Mock(return_value={"plan": "base-plan"})
    reviewer_fn = Mock(side_effect=lambda child, plan: {**plan, "value": child.parameter_value})
    submit_fn = Mock(return_value={"status": "submitted"})

    # First poll per child => running, second => completed
    poll_outcomes = {
        "sweep-integration-1-child-0": ["running", "completed"],
        "sweep-integration-1-child-1": ["running", "completed"],
    }

    def poll_fn(child):
        queue = poll_outcomes[child.sweep_child_id]
        return queue.pop(0)

    parent = orchestrate_sweep(
        spec,
        state={"prompt": "run a sweep"},
        config=SimpleNamespace(enable_sweep_orchestration=True),
        architect_fn=architect_fn,
        reviewer_fn=reviewer_fn,
        submit_fn=submit_fn,
        poll_fn=Mock(side_effect=poll_fn),
    )

    assert parent.total_count == 2
    assert parent.completed_count + parent.failed_count == parent.total_count
    assert parent.model_dump()
