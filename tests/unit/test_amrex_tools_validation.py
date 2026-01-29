"""Unit tests for generic AMReX tools validation."""

from pathlib import Path
import json

from amrex_tools import validate_amrex_inputs


def test_validate_amrex_inputs_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing_inputs"
    result = validate_amrex_inputs.invoke({"inputs_file": str(missing)})
    payload = json.loads(result)
    assert payload["errors"]
    assert "File not found" in payload["errors"][0]


def test_validate_amrex_inputs_parses_ok(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.write_text("amr.n_cell = 16 16 16\n")
    result = validate_amrex_inputs.invoke({"inputs_file": str(inputs)})
    payload = json.loads(result)
    assert payload["errors"] == []
