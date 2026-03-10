from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.models.sweep_schemas import (
    ChildJobStatus,
    ParentSweepState,
    SweepSpec,
    SweepType,
    validate_transition,
)
from src.services.sweep_orchestrator import (
    orchestrate_sweep,
    poll_child_status,
    update_parent_state,
)


def _spec(values, sweep_type=SweepType.execution) -> SweepSpec:
    return SweepSpec(
        sweep_type=sweep_type,
        parameter_name="amr.max_level",
        parameter_values=values,
        sweep_id="sweep-001",
        metadata={},
    )


def _config(enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(enable_sweep_orchestration=enabled)


class TestFanOut:
    def test_fanout_spawns_correct_child_count(self):
        spec = _spec([1, 2, 4])
        architect_fn = Mock(return_value={"plan": "P"})
        reviewer_fn = Mock()
        submit_fn = Mock(return_value={"job_id": "j", "status": "submitted"})
        poll_fn = Mock(return_value="completed")

        parent = orchestrate_sweep(
            spec,
            state={},
            config=_config(True),
            architect_fn=architect_fn,
            reviewer_fn=reviewer_fn,
            submit_fn=submit_fn,
            poll_fn=poll_fn,
        )

        assert parent.total_count == 3
        assert len(parent.children) == 3

    def test_each_child_has_unique_id(self):
        spec = _spec([1, 2, 4, 8])
        parent = orchestrate_sweep(
            spec,
            state={},
            config=_config(True),
            architect_fn=Mock(return_value={"plan": "P"}),
            reviewer_fn=Mock(),
            submit_fn=Mock(return_value={"status": "submitted"}),
            poll_fn=Mock(return_value="completed"),
        )

        child_ids = [child.sweep_child_id for child in parent.children]
        assert len(child_ids) == len(set(child_ids))

    def test_each_child_has_parameter_value(self):
        spec = _spec([1, 2, 4])
        parent = orchestrate_sweep(
            spec,
            state={},
            config=_config(True),
            architect_fn=Mock(return_value={"plan": "P"}),
            reviewer_fn=Mock(),
            submit_fn=Mock(return_value={"status": "submitted"}),
            poll_fn=Mock(return_value="completed"),
        )

        assert parent.children[0].parameter_value == 1
        assert parent.children[1].parameter_value == 2
        assert parent.children[2].parameter_value == 4


class TestExecutionSweep:
    def test_execution_sweep_architect_runs_once(self):
        spec = _spec([2, 4, 8], sweep_type=SweepType.execution)
        architect_fn = Mock(return_value={"plan": "shared"})
        submit_fn = Mock(return_value={"status": "submitted"})

        orchestrate_sweep(
            spec,
            state={"prompt": "sweep nodes"},
            config=_config(True),
            architect_fn=architect_fn,
            reviewer_fn=Mock(),
            submit_fn=submit_fn,
            poll_fn=Mock(return_value="completed"),
        )

        assert architect_fn.call_count == 1
        plans = [call.args[1] for call in submit_fn.call_args_list]
        assert len(plans) == 3
        assert all(plan == {"plan": "shared"} for plan in plans)

    def test_execution_sweep_children_get_plan(self):
        spec = _spec([2, 4], sweep_type=SweepType.execution)
        plan_p = {"plan": "P", "steps": ["a", "b"]}
        submit_fn = Mock(return_value={"status": "submitted"})

        orchestrate_sweep(
            spec,
            state={},
            config=_config(True),
            architect_fn=Mock(return_value=plan_p),
            reviewer_fn=Mock(),
            submit_fn=submit_fn,
            poll_fn=Mock(return_value="completed"),
        )

        for call in submit_fn.call_args_list:
            assert call.args[1] == plan_p


class TestPhysicsSweep:
    def test_physics_sweep_architect_runs_once(self):
        spec = _spec([10, 20], sweep_type=SweepType.physics)
        architect_fn = Mock(return_value={"plan": "base"})

        orchestrate_sweep(
            spec,
            state={},
            config=_config(True),
            architect_fn=architect_fn,
            reviewer_fn=Mock(side_effect=lambda child, plan: {**plan, "pv": child.parameter_value}),
            submit_fn=Mock(return_value={"status": "submitted"}),
            poll_fn=Mock(return_value="completed"),
        )

        assert architect_fn.call_count == 1

    def test_physics_sweep_reviewer_per_child(self):
        spec = _spec([10, 20, 30], sweep_type=SweepType.physics)
        reviewer_fn = Mock(side_effect=lambda child, plan: {**plan, "pv": child.parameter_value})

        orchestrate_sweep(
            spec,
            state={},
            config=_config(True),
            architect_fn=Mock(return_value={"plan": "base"}),
            reviewer_fn=reviewer_fn,
            submit_fn=Mock(return_value={"status": "submitted"}),
            poll_fn=Mock(return_value="completed"),
        )

        assert reviewer_fn.call_count == 3


class TestPolling:
    def test_polling_unchanged_status_does_not_fail_early(self):
        spec = _spec([1, 2])
        state_by_child = {
            "sweep-001-child-0": ["running", "running", "completed"],
            "sweep-001-child-1": ["running", "running", "completed"],
        }

        def poll_fn(child):
            sequence = state_by_child[child.sweep_child_id]
            return sequence.pop(0)

        parent = orchestrate_sweep(
            spec,
            state={},
            config=_config(True),
            architect_fn=Mock(return_value={"plan": "P"}),
            reviewer_fn=Mock(),
            submit_fn=Mock(return_value={"status": "submitted"}),
            poll_fn=Mock(side_effect=poll_fn),
        )

        assert parent.completed_count == 2
        assert parent.failed_count == 0

    def test_polling_updates_child_status(self):
        spec = _spec([1, 2])
        parent = ParentSweepState(
            sweep_id=spec.sweep_id,
            sweep_spec=spec,
            total_count=2,
            children=[
                {
                    "sweep_id": spec.sweep_id,
                    "sweep_child_id": "child-1",
                    "parameter_name": spec.parameter_name,
                    "parameter_value": 1,
                    "status": ChildJobStatus.submitted,
                },
                {
                    "sweep_id": spec.sweep_id,
                    "sweep_child_id": "child-2",
                    "parameter_name": spec.parameter_name,
                    "parameter_value": 2,
                    "status": ChildJobStatus.submitted,
                },
            ],
        )

        child = parent.children[0]
        poll_child_status(child, Mock(return_value="running"))

        assert child.status == ChildJobStatus.running

    def test_polling_completed_updates_count(self):
        spec = _spec([1, 2])
        parent = ParentSweepState(
            sweep_id=spec.sweep_id,
            sweep_spec=spec,
            total_count=1,
            children=[
                {
                    "sweep_id": spec.sweep_id,
                    "sweep_child_id": "child-1",
                    "parameter_name": spec.parameter_name,
                    "parameter_value": 1,
                    "status": ChildJobStatus.running,
                }
            ],
        )

        update_parent_state(parent, "child-1", ChildJobStatus.completed)

        assert parent.completed_count == 1

    def test_polling_failed_updates_count(self):
        spec = _spec([1, 2])
        parent = ParentSweepState(
            sweep_id=spec.sweep_id,
            sweep_spec=spec,
            total_count=1,
            children=[
                {
                    "sweep_id": spec.sweep_id,
                    "sweep_child_id": "child-1",
                    "parameter_name": spec.parameter_name,
                    "parameter_value": 1,
                    "status": ChildJobStatus.running,
                }
            ],
        )

        update_parent_state(parent, "child-1", ChildJobStatus.failed, failure_reason="mock error")

        assert parent.failed_count == 1
        assert parent.children[0].failure_reason == "mock error"

    def test_invalid_transition_rejected(self):
        spec = _spec([1, 2])
        parent = ParentSweepState(
            sweep_id=spec.sweep_id,
            sweep_spec=spec,
            total_count=1,
            children=[
                {
                    "sweep_id": spec.sweep_id,
                    "sweep_child_id": "child-1",
                    "parameter_name": spec.parameter_name,
                    "parameter_value": 1,
                    "status": ChildJobStatus.completed,
                }
            ],
        )

        allowed = validate_transition(ChildJobStatus.completed, ChildJobStatus.pending)
        update_parent_state(parent, "child-1", ChildJobStatus.pending)

        assert allowed is False
        assert parent.children[0].status == ChildJobStatus.completed


class TestFeatureFlag:
    def test_submit_failed_status_is_applied_from_pending(self):
        spec = _spec([1, 2])
        submit_fn = Mock(return_value={"status": "failed", "failure_reason": "submit error"})
        poll_fn = Mock()

        parent = orchestrate_sweep(
            spec,
            state={},
            config=_config(True),
            architect_fn=Mock(return_value={"plan": "P"}),
            reviewer_fn=Mock(),
            submit_fn=submit_fn,
            poll_fn=poll_fn,
        )

        assert parent.failed_count == 2
        assert parent.completed_count == 0
        assert all(child.status == ChildJobStatus.failed for child in parent.children)
        assert all(child.failure_reason == "submit error" for child in parent.children)
        assert poll_fn.call_count == 0

    def test_submit_running_status_is_applied_from_pending(self):
        spec = _spec([1, 2])
        submit_fn = Mock(return_value={"status": "running"})
        poll_fn = Mock(return_value="completed")

        parent = orchestrate_sweep(
            spec,
            state={},
            config=_config(True),
            architect_fn=Mock(return_value={"plan": "P"}),
            reviewer_fn=Mock(),
            submit_fn=submit_fn,
            poll_fn=poll_fn,
        )

        assert parent.completed_count == 2
        assert parent.failed_count == 0

    def test_flag_false_single_run(self):
        spec = _spec([1, 2, 4])
        submit_fn = Mock(return_value={"status": "submitted"})

        parent = orchestrate_sweep(
            spec,
            state={"prompt": "sweep over values"},
            config=_config(False),
            architect_fn=Mock(),
            reviewer_fn=Mock(),
            submit_fn=submit_fn,
            poll_fn=Mock(),
        )

        assert parent is None
        assert submit_fn.call_count == 1
