"""Unit tests for use-case summary traceability enforcement."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from src.benchmark_runner import (
    _build_uc_summary_traceability_report,
    _derive_uc_summary_traceability_fields,
    _normalize_benchmark_record,
    run_model_benchmark,
)

# Coverage compatibility for file-path based coverage targets.
sys.modules["src/benchmark_runner.py"] = sys.modules["src.benchmark_runner"]

GRAPH_MODULE_NAME = "src/graph.py"
GRAPH_PATH = Path(__file__).resolve().parents[2] / "src" / "graph.py"
SPEC = importlib.util.spec_from_file_location(GRAPH_MODULE_NAME, GRAPH_PATH)
assert SPEC is not None and SPEC.loader is not None
GRAPH_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[GRAPH_MODULE_NAME] = GRAPH_MODULE
SPEC.loader.exec_module(GRAPH_MODULE)


def test_uc_summary_traceability_derivation_from_payload_and_graph_state() -> None:
    payload = {
        "uc_summary_entries": [
            {"uc_id": "UC-1", "summary": "covered via tests", "tests": ["tests/unit/test_one.py"]},
            {"use_case_id": "UC-2", "summary": "covered via fixture", "fixtures": ["tests/fixtures/a.json"]},
            {"id": "UC-3", "summary": "covered via benchmark", "benchmarks": ["benchmarks/run_01"]},
            {"uc_id": "UC-4", "summary": "missing mappings"},
        ]
    }
    fields = _derive_uc_summary_traceability_fields(payload, {})

    assert fields["uc_summary_count"] == 4
    assert fields["uc_summary_traceable_count"] == 3
    assert fields["uc_summary_traceability_status"] == "partial"
    assert fields["uc_summary_untraceable_ids"] == ["UC-4"]

    fallback = _derive_uc_summary_traceability_fields({}, {"uc_summary": [{"id": "UC-X"}]})
    assert fallback["uc_summary_count"] == 1
    assert fallback["uc_summary_traceable_count"] == 0
    assert fallback["uc_summary_traceability_status"] == "partial"


def test_normalization_includes_uc_summary_traceability_fields() -> None:
    normalized = _normalize_benchmark_record(
        {
            "model_id": "m1",
            "prompt_id": "p1",
            "uc_summary_entries": [
                {"uc_id": "UC-1", "summary": "one", "artifact_refs": ["tests/unit/test_one.py"]},
                {"uc_id": "UC-2", "summary": "two"},
            ],
        }
    )

    assert normalized["uc_summary_count"] == 2
    assert normalized["uc_summary_traceable_count"] == 1
    assert normalized["uc_summary_traceability_status"] == "partial"
    assert normalized["uc_summary_untraceable_ids"] == ["UC-2"]
    assert normalized["uc_summary_entries"][0]["traceable"] is True
    assert normalized["uc_summary_entries"][1]["traceable"] is False


def test_uc_summary_traceability_report_aggregation() -> None:
    report = _build_uc_summary_traceability_report(
        [
            {"uc_summary_count": 2, "uc_summary_traceable_count": 1},
            {"uc_summary_count": 1, "uc_summary_traceable_count": 1},
        ]
    )
    assert report["total_records"] == 2
    assert report["total_uc_summaries"] == 3
    assert report["total_traceable_uc_summaries"] == 2
    assert 0.0 < report["coverage_ratio"] < 1.0


def test_run_model_benchmark_writes_uc_traceability_artifact(tmp_path, monkeypatch) -> None:
    config = {
        "prompts": [{"id": "p1", "prompt": "Prompt one"}],
        "models": [{"id": "m1", "overrides": {"llm_provider": "cborg", "llm_model": "x"}}],
        "run_args": {"dry_run": True},
    }
    config_path = tmp_path / "bench.json"
    config_path.write_text(json.dumps(config))

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "job_status": "completed",
                    "uc_summary_entries": [
                        {"uc_id": "UC-1", "summary": "Mapped", "tests": ["tests/unit/test_one.py"]},
                        {"uc_id": "UC-2", "summary": "Unmapped"},
                    ],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("src.benchmark_runner.subprocess.run", fake_run)

    result = run_model_benchmark(config_path, tmp_path, run_name="uc_summary_traceability")
    run_dir = Path(result["run_dir"])
    traceability_file = run_dir / "uc_summary_traceability.json"
    assert traceability_file.exists()

    traceability = json.loads(traceability_file.read_text())
    assert traceability["total_uc_summaries"] == 2
    assert traceability["total_traceable_uc_summaries"] == 1
    assert traceability["coverage_ratio"] == 0.5

    metrics_line = json.loads((run_dir / "benchmark_runs.jsonl").read_text().splitlines()[0])
    assert metrics_line["uc_summary_traceability_status"] == "partial"
    assert metrics_line["uc_summary_untraceable_ids"] == ["UC-2"]


def test_graph_uc_summary_traceability_validation_paths() -> None:
    bypass_state = {"uc_summary_traceability_required": False}
    assert GRAPH_MODULE._uc_summary_traceability_valid(bypass_state) is True
    assert "uc_summary_traceability_validation" not in bypass_state

    missing_state = {"uc_summary_traceability_required": True}
    assert GRAPH_MODULE._uc_summary_traceability_valid(missing_state) is False
    assert missing_state["uc_summary_traceability_validation"]["reason"] == "missing_uc_summary_entries"

    failing_state = {
        "uc_summary_traceability_required": True,
        "uc_summary_entries": [
            {"uc_id": "UC-1", "summary": "covered", "tests": ["tests/unit/test_one.py"]},
            {"uc_id": "UC-2", "summary": "missing artifacts"},
        ],
    }
    assert GRAPH_MODULE._uc_summary_traceability_valid(failing_state) is False
    assert failing_state["uc_summary_traceability_validation"]["failed_use_cases"] == ["UC-2"]

    passing_state = {
        "uc_summary_traceability_required": True,
        "uc_summary_entries": [
            {"uc_id": "UC-1", "summary": "covered", "tests": ["tests/unit/test_one.py"]},
            {"uc_id": "UC-2", "summary": "covered", "fixtures": ["tests/fixtures/example.json"]},
            {"uc_id": "UC-3", "summary": "covered", "benchmarks": ["benchmarks/uc3"]},
        ],
    }
    assert GRAPH_MODULE._uc_summary_traceability_valid(passing_state) is True
    assert passing_state["uc_summary_traceability_validation"]["passed"] is True

    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "uc_summary_traceability_required": True,
                "uc_summary_entries": [{"uc_id": "UC-1", "summary": "unmapped"}],
            }
        )
        == "end"
    )
    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "uc_summary_traceability_required": True,
                "uc_summary_entries": [
                    {"uc_id": "UC-1", "summary": "covered", "artifact_refs": ["tests/unit/test_one.py"]},
                ],
            }
        )
        == "intent_extraction_node"
    )
