"""Session 70 tests for UNNUMBERED-023 use-case-to-artifact mapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.test_oracle_benchmarks import ORACLE_USE_CASE_ARTIFACT_MAP


@pytest.fixture
def unnumbered_023_rows() -> list[tuple[str, str]]:
    """Parse strict 1:1 mapping rows from coverage_map.md."""
    lines = Path("docs/coverage_map.md").read_text(encoding="utf-8").splitlines()
    header = "## UNNUMBERED-023: Use Case to Artifact Mapping"

    try:
        start = lines.index(header) + 1
    except ValueError as exc:
        raise AssertionError(f"Missing required header: {header}") from exc

    rows: list[tuple[str, str]] = []
    in_table = False
    for raw in lines[start:]:
        line = raw.strip()
        if line.startswith("## ") and in_table:
            break
        if not line:
            continue
        if not line.startswith("|"):
            continue
        if "| use_case_id | validation_artifact |" in line.lower():
            in_table = True
            continue
        if line.startswith("|---"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) != 2:
            continue
        rows.append((parts[0], parts[1]))

    assert rows, "No mapping rows parsed under UNNUMBERED-023 header."
    return rows


@pytest.mark.parametrize(
    ("use_case_id", "artifact_ref"),
    list(ORACLE_USE_CASE_ARTIFACT_MAP.items()),
)
def test_unnumbered_023_expected_artifact_ref_format(use_case_id: str, artifact_ref: str) -> None:
    assert artifact_ref == (
        f"tests/integration/test_oracle_benchmarks.py::test_oracle_gate_routing[{use_case_id}]"
    )


def test_unnumbered_023_docs_mapping_matches_oracle_contract(
    unnumbered_023_rows: list[tuple[str, str]],
) -> None:
    mapping = dict(unnumbered_023_rows)
    assert len(mapping) == len(unnumbered_023_rows), "Duplicate use_case_id rows found."
    assert len(set(mapping.values())) == len(mapping), "Artifacts must be unique across use cases."
    assert mapping == ORACLE_USE_CASE_ARTIFACT_MAP
