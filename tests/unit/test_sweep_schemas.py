"""Unit tests for sweep schema models and transition validation."""

import pytest
from pydantic import ValidationError

from src.models.sweep_schemas import (
    ChildJobStatus,
    ChildWorkflowState,
    ParentSweepState,
    SweepSpec,
    SweepType,
    validate_transition,
)


def _make_valid_sweep_spec() -> SweepSpec:
    return SweepSpec(
        sweep_type=SweepType.execution,
        parameter_name="amr.max_grid_size",
        parameter_values=[32, 64],
        sweep_id="sweep-001",
    )


# SweepSpec tests

def test_sweep_spec_valid_execution_type():
    """SweepSpec with sweep_type='execution' validates"""
    spec = SweepSpec(
        sweep_type=SweepType.execution,
        parameter_name="resources.nodes",
        parameter_values=[1, 2],
        sweep_id="sweep-exec",
    )

    assert spec.sweep_type is SweepType.execution


def test_sweep_spec_valid_physics_type():
    """SweepSpec with sweep_type='physics' validates"""
    spec = SweepSpec(
        sweep_type=SweepType.physics,
        parameter_name="prob.nu",
        parameter_values=[0.1, 0.2],
        sweep_id="sweep-phys",
    )

    assert spec.sweep_type is SweepType.physics


def test_sweep_spec_valid_resolution_type():
    """SweepSpec with sweep_type='resolution' validates"""
    spec = SweepSpec(
        sweep_type=SweepType.resolution,
        parameter_name="amr.n_cell",
        parameter_values=[[32, 32, 32], [64, 64, 64]],
        sweep_id="sweep-res",
    )

    assert spec.sweep_type is SweepType.resolution


def test_sweep_spec_invalid_type_raises():
    """SweepSpec with sweep_type='invalid' raises ValidationError"""
    with pytest.raises(ValidationError):
        SweepSpec(
            sweep_type="invalid",
            parameter_name="prob.nu",
            parameter_values=[0.1, 0.2],
            sweep_id="sweep-invalid",
        )


def test_sweep_spec_requires_parameter_values():
    """SweepSpec without parameter_values raises"""
    with pytest.raises(ValidationError):
        SweepSpec(
            sweep_type=SweepType.physics,
            parameter_name="prob.nu",
            sweep_id="sweep-no-values",
        )


def test_sweep_spec_requires_at_least_two_values():
    """SweepSpec with one value raises - a sweep needs at least 2 points"""
    with pytest.raises(ValidationError):
        SweepSpec(
            sweep_type=SweepType.physics,
            parameter_name="prob.nu",
            parameter_values=[0.1],
            sweep_id="sweep-one-value",
        )


# ChildJobStatus tests

def test_child_job_status_pending_valid():
    """'pending' is valid ChildJobStatus"""
    assert ChildJobStatus("pending") is ChildJobStatus.pending


def test_child_job_status_invalid_raises():
    """'unknown' is not valid ChildJobStatus"""
    with pytest.raises(ValueError):
        ChildJobStatus("unknown")


def test_child_job_transitions_pending_to_submitted():
    """Status transition pending->submitted is valid"""
    assert validate_transition(ChildJobStatus.pending, ChildJobStatus.submitted)


def test_child_job_transitions_submitted_to_running():
    """Status transition submitted->running is valid"""
    assert validate_transition(ChildJobStatus.submitted, ChildJobStatus.running)


def test_child_job_transitions_running_to_completed():
    """Status transition running->completed is valid"""
    assert validate_transition(ChildJobStatus.running, ChildJobStatus.completed)


def test_child_job_transitions_running_to_failed():
    """Status transition running->failed is valid"""
    assert validate_transition(ChildJobStatus.running, ChildJobStatus.failed)


def test_child_job_no_backward_transition():
    """Transition completed->pending is invalid"""
    assert not validate_transition(ChildJobStatus.completed, ChildJobStatus.pending)


# ChildWorkflowState tests

def test_child_workflow_state_validates_correctly():
    """Valid ChildWorkflowState instantiates"""
    child = ChildWorkflowState(
        sweep_id="sweep-001",
        sweep_child_id="child-001",
        parameter_name="prob.nu",
        parameter_value=0.1,
    )

    assert child.status is ChildJobStatus.pending


def test_child_workflow_state_has_sweep_id():
    """ChildWorkflowState carries parent sweep_id"""
    child = ChildWorkflowState(
        sweep_id="sweep-abc",
        sweep_child_id="child-001",
        parameter_name="prob.nu",
        parameter_value=0.2,
    )

    assert child.sweep_id == "sweep-abc"


def test_child_workflow_state_has_parameter_value():
    """ChildWorkflowState carries its parameter value"""
    child = ChildWorkflowState(
        sweep_id="sweep-001",
        sweep_child_id="child-002",
        parameter_name="prob.nu",
        parameter_value=0.3,
    )

    assert child.parameter_value == 0.3


def test_child_workflow_state_serializes_to_dict():
    """model_dump() returns plain dict for state storage"""
    child = ChildWorkflowState(
        sweep_id="sweep-001",
        sweep_child_id="child-003",
        parameter_name="prob.nu",
        parameter_value=0.4,
        status=ChildJobStatus.running,
    )

    data = child.model_dump()

    assert isinstance(data, dict)
    assert data["status"] == ChildJobStatus.running


# ParentSweepState tests

def test_parent_sweep_state_validates_correctly():
    """Valid ParentSweepState instantiates"""
    spec = _make_valid_sweep_spec()

    parent = ParentSweepState(sweep_id="sweep-001", sweep_spec=spec, total_count=2)

    assert parent.sweep_id == "sweep-001"


def test_parent_sweep_state_children_list():
    """children field is List[ChildWorkflowState]"""
    spec = _make_valid_sweep_spec()
    child = ChildWorkflowState(
        sweep_id="sweep-001",
        sweep_child_id="child-001",
        parameter_name="amr.max_grid_size",
        parameter_value=32,
    )

    parent = ParentSweepState(
        sweep_id="sweep-001",
        sweep_spec=spec,
        children=[child],
        total_count=1,
    )

    assert len(parent.children) == 1
    assert isinstance(parent.children[0], ChildWorkflowState)


def test_parent_sweep_state_tracks_completion():
    """completed_count + failed_count <= total_count"""
    spec = _make_valid_sweep_spec()

    valid_parent = ParentSweepState(
        sweep_id="sweep-001",
        sweep_spec=spec,
        total_count=3,
        completed_count=1,
        failed_count=2,
    )
    assert valid_parent.total_count == 3

    with pytest.raises(ValidationError):
        ParentSweepState(
            sweep_id="sweep-001",
            sweep_spec=spec,
            total_count=2,
            completed_count=2,
            failed_count=1,
        )


def test_parent_sweep_state_serializes_cleanly():
    """Full parent state with children serializes to nested dict - no Pydantic objects in output"""
    spec = _make_valid_sweep_spec()
    child = ChildWorkflowState(
        sweep_id="sweep-001",
        sweep_child_id="child-001",
        parameter_name="amr.max_grid_size",
        parameter_value=32,
        status=ChildJobStatus.completed,
    )

    parent = ParentSweepState(
        sweep_id="sweep-001",
        sweep_spec=spec,
        children=[child],
        total_count=1,
        completed_count=1,
        failed_count=0,
    )

    data = parent.model_dump()

    assert isinstance(data, dict)
    assert isinstance(data["sweep_spec"], dict)
    assert isinstance(data["children"], list)
    assert isinstance(data["children"][0], dict)
