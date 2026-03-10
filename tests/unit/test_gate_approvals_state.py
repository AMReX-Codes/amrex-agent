"""Unit tests for gate approval record schema and state storage."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.models.gate_approval import GateApprovalRecord


def test_gate_approval_record_validates_correctly():
    """Valid GateApprovalRecord instantiates without error"""
    record = GateApprovalRecord(
        gate_id="g-001",
        gate_type="preconfirm",
        decision="approved",
        interface_path="cli",
        details={"node": "architect"},
    )

    assert record.gate_id == "g-001"
    assert record.gate_type == "preconfirm"
    assert record.decision == "approved"
    assert record.interface_path == "cli"


def test_gate_approval_record_missing_required_field():
    """Missing required field raises ValidationError"""
    with pytest.raises(ValidationError):
        GateApprovalRecord(
            gate_id="g-002",
            gate_type="interactive",
            decision="approved",
            details={"surface": "mcp"},
        )


def test_gate_approval_record_serializes_to_dict():
    """model_dump() returns plain dict, no Pydantic objects"""
    record = GateApprovalRecord(
        gate_id="g-003",
        gate_type="interactive",
        decision="rejected",
        interface_path="mcp",
        details={"tool": "run_simulation"},
    )

    payload = record.model_dump()

    assert isinstance(payload, dict)
    assert isinstance(payload["details"], dict)
    assert not hasattr(payload, "model_dump")


def test_gate_approvals_list_accepts_serialized_record():
    """gate_approvals: List[Dict] accepts model_dump output"""
    state = SimpleNamespace(gate_approvals=[])
    record = GateApprovalRecord(
        gate_id="g-004",
        gate_type="interactive",
        decision="approved",
        interface_path="mcp",
    )

    state.gate_approvals.append(record.model_dump())

    assert len(state.gate_approvals) == 1
    assert state.gate_approvals[0]["gate_id"] == "g-004"


def test_interface_path_recorded_for_cli_gate():
    """CLI gate produces interface_path = 'cli'"""
    build_details = Mock(return_value={"source": "preconfirm"})
    record = GateApprovalRecord(
        gate_id="g-005",
        gate_type="preconfirm",
        decision="approved",
        interface_path="cli",
        details=build_details(),
    )

    assert record.interface_path == "cli"


def test_interface_path_recorded_for_mcp_gate():
    """MCP gate produces interface_path = 'mcp'"""
    record = GateApprovalRecord(
        gate_id="g-006",
        gate_type="interactive",
        decision="approved",
        interface_path="mcp",
        details={"surface": "mcp"},
    )

    assert record.interface_path == "mcp"


def test_two_gates_both_written_to_state():
    """Appending two records produces list of length 2"""
    state = {"gate_approvals": []}
    first = GateApprovalRecord(
        gate_id="g-007",
        gate_type="preconfirm",
        decision="approved",
        interface_path="cli",
    )
    second = GateApprovalRecord(
        gate_id="g-008",
        gate_type="interactive",
        decision="rejected",
        interface_path="mcp",
    )

    state["gate_approvals"].append(first.model_dump())
    state["gate_approvals"].append(second.model_dump())

    assert len(state["gate_approvals"]) == 2


def test_gate_approvals_independent_across_state_copies():
    """Two separate state dicts have independent lists"""
    base_state = {"gate_approvals": []}
    state_one = deepcopy(base_state)
    state_two = deepcopy(base_state)

    state_one["gate_approvals"].append(
        GateApprovalRecord(
            gate_id="g-009",
            gate_type="preconfirm",
            decision="approved",
            interface_path="cli",
        ).model_dump()
    )

    assert len(state_one["gate_approvals"]) == 1
    assert state_two["gate_approvals"] == []
