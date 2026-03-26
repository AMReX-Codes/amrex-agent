"""Unit tests for B2b sweep detection and SweepSpec creation."""

from pydantic import ValidationError

from src.models.sweep_schemas import SweepSpec, SweepType
from src.nodes.sweep_detection_node import sweep_detection_node
from src.services.sweep_detector import create_sweep_spec, detect_sweep_request


def test_no_sweep_language_returns_none() -> None:
    """
    Given: 'run a squall line simulation'
    When:  detect_sweep_request(prompt) runs
    Then:  returns None
    """
    prompt = "run a squall line simulation"
    assert detect_sweep_request(prompt) is None


def test_vary_keyword_detected() -> None:
    """
    Given: 'vary max_level from 2 to 4'
    When:  detect_sweep_request(prompt) runs
    Then:  returns non-None result
    """
    prompt = "vary max_level from 2 to 4"
    detected = detect_sweep_request(prompt)
    assert detected is not None


def test_resolution_study_detected() -> None:
    """
    Given: 'run a resolution study with n_cell 64 128 256'
    When:  detect_sweep_request(prompt) runs
    Then:  sweep_type == SweepType.resolution
    """
    prompt = "run a resolution study with n_cell 64 128 256"
    detected = detect_sweep_request(prompt)

    assert detected is not None
    assert detected["sweep_type"] == SweepType.resolution


def test_parameter_scan_detected() -> None:
    """
    Given: 'parameter scan over viscosity 0.1 0.01 0.001'
    When:  detect_sweep_request(prompt) runs
    Then:  sweep_type == SweepType.physics
           parameter_name contains 'viscosity'
    """
    prompt = "parameter scan over viscosity 0.1 0.01 0.001"
    detected = detect_sweep_request(prompt)

    assert detected is not None
    assert detected["sweep_type"] == SweepType.physics
    assert detected["parameter_name"] is not None
    assert "viscosity" in detected["parameter_name"]


def test_sweep_spec_created_from_detection() -> None:
    """
    Given: detection returns sweep type and values
    When:  create_sweep_spec(detection_result) runs
    Then:  returns valid SweepSpec
           len(parameter_values) >= 2
    """
    detection = {
        "sweep_type": SweepType.resolution,
        "parameter_name": "n_cell",
        "parameter_values": [64, 128, 256],
        "raw_match": "resolution study",
    }

    spec = create_sweep_spec(detection)

    assert isinstance(spec, SweepSpec)
    assert len(spec.parameter_values) >= 2


def test_sweep_spec_has_unique_sweep_id() -> None:
    """
    Given: two calls to create_sweep_spec
    When:  same input prompt
    Then:  sweep_id differs between calls
           (uuid-based, not deterministic)
    """
    detection = {
        "sweep_type": SweepType.physics,
        "parameter_name": "viscosity",
        "parameter_values": [0.1, 0.01],
        "raw_match": "vary",
    }

    spec_one = create_sweep_spec(detection)
    spec_two = create_sweep_spec(detection)

    assert spec_one.sweep_id != spec_two.sweep_id


def test_sweep_spec_written_to_state() -> None:
    """
    Given: sweep detected from prompt
    When:  sweep_detection_node runs
    Then:  state['sweep_id'] is set
           state['sweep_parameter'] is set
           state['sweep_parameter_value'] is None
           (None at parent level — set per child)
    """
    state = {
        "prompt": "vary max_level from 2 to 4",
        "sweep_id": None,
        "sweep_parameter": None,
        "sweep_parameter_value": None,
    }

    updates = sweep_detection_node(state)

    assert updates["sweep_id"] is not None
    assert updates["sweep_parameter"] is not None
    assert updates["sweep_parameter_value"] is None


def test_no_sweep_leaves_state_unchanged() -> None:
    """
    Given: no sweep in prompt
    When:  sweep_detection_node runs
    Then:  state['sweep_id'] is None
           state['sweep_parameter'] is None
    """
    state = {
        "prompt": "run a squall line simulation",
        "sweep_id": None,
        "sweep_parameter": None,
    }

    updates = sweep_detection_node(state)

    assert updates["sweep_id"] is None
    assert updates["sweep_parameter"] is None


def test_sweep_spec_validates_against_schema() -> None:
    """
    Given: create_sweep_spec returns a SweepSpec
    When:  SweepSpec.model_validate(spec.model_dump())
    Then:  no ValidationError
    """
    detection = {
        "sweep_type": SweepType.execution,
        "parameter_name": "nodes",
        "parameter_values": [1, 2, 4],
        "raw_match": "scaling study",
    }

    spec = create_sweep_spec(detection)

    try:
        SweepSpec.model_validate(spec.model_dump())
    except ValidationError as exc:
        raise AssertionError("SweepSpec should validate") from exc
