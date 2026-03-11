"""Unit tests for explicit feature test/fixture mapping validation."""

from __future__ import annotations

import json
import sys

from src.benchmark_runner import _write_jsonl
from src.graph import _route_after_paper_validator

# Coverage compatibility for file-path based coverage targets.
sys.modules["src/benchmark_runner.py"] = sys.modules["src.benchmark_runner"]
sys.modules["src/graph.py"] = sys.modules["src.graph"]


def _read_first_jsonl(path):
    return json.loads(path.read_text(encoding="utf-8").splitlines()[0])


def test_benchmark_runner_derives_explicit_mapping_from_markdown(tmp_path) -> None:
    path = tmp_path / "bench.jsonl"
    _write_jsonl(
        path,
        {
            "model_id": "m1",
            "prompt_id": "p1",
            "__graph_state": {
                "feature_blocks_markdown": (
                    "## [F-001] Feature One\n"
                    "Tests/Fixtures: tests/unit/test_one.py, tests/fixtures/one.json\n\n"
                    "## [F-002] Feature Two\n"
                    "Tests/Fixtures: tests/unit/test_two.py"
                )
            },
        },
    )

    record = _read_first_jsonl(path)
    assert record["feature_test_fixture_mapping_count"] == 2
    assert record["feature_test_fixture_mapping_complete_count"] == 1
    assert record["feature_test_fixture_mapping_status"] == "partial"
    assert record["feature_test_fixture_mapping_complete"] is False
    assert record["feature_test_fixture_mapping_missing"] == ["## [F-002] Feature Two"]


def test_benchmark_runner_preserves_structured_explicit_mapping(tmp_path) -> None:
    path = tmp_path / "bench.jsonl"
    _write_jsonl(
        path,
        {
            "model_id": "m1",
            "prompt_id": "p1",
            "feature_test_fixture_mapping": [
                {
                    "feature_id": "F-100",
                    "feature_label": "F-100 Explicit",
                    "tests": ["tests/unit/test_ok.py"],
                    "fixtures": ["tests/fixtures/ok.json"],
                }
            ],
        },
    )

    record = _read_first_jsonl(path)
    assert record["feature_test_fixture_mapping_status"] == "complete"
    assert record["feature_test_fixture_mapping_complete"] is True
    assert record["feature_test_fixture_mapping_missing"] == []
    assert record["feature_test_fixture_mapping"][0]["mapping_complete"] is True


def test_route_after_paper_validator_rejects_missing_explicit_mapping() -> None:
    state = {
        "paper_validation_passed": True,
        "feature_test_fixture_mapping_required": True,
        "feature_blocks_markdown": "## [F-010] Missing Fixtures\nTests/Fixtures: tests/unit/test_ok.py",
    }

    route = _route_after_paper_validator(state)

    assert route == "end"
    assert state["feature_test_fixture_mapping_validation"]["passed"] is False
    assert state["feature_test_fixture_mapping_validation"]["missing_features"] == [
        "## [F-010] Missing Fixtures"
    ]


def test_route_after_paper_validator_accepts_explicit_mapping_when_complete() -> None:
    state = {
        "paper_validation_passed": True,
        "feature_test_fixture_mapping_required": True,
        "feature_test_fixture_mapping": [
            {
                "feature_id": "F-011",
                "feature_label": "F-011 Complete",
                "tests": ["tests/unit/test_ok.py"],
                "fixtures": ["tests/fixtures/ok.json"],
            }
        ],
    }

    route = _route_after_paper_validator(state)

    assert route == "intent_extraction_node"
    assert state["feature_test_fixture_mapping_validation"]["passed"] is True
    assert state["feature_test_fixture_mapping_complete"] is True
