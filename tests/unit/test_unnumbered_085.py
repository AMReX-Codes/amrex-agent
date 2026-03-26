"""Session 29 tests for UNNUMBERED-085 reproducibility oracle behavior."""

from __future__ import annotations

from src.benchmark_runner import (
    _derive_reproducibility_oracle_fields,
    _normalize_benchmark_record,
)
from src.graph import _route_after_manifest_validation, create_graph


def test_reproducibility_oracle_digest_is_stable_for_same_seed() -> None:
    first = _derive_reproducibility_oracle_fields(
        {
            "reproducibility_oracle_enabled": True,
            "seed": 42,
            "analysis_status": "success",
            "started_at": "2026-01-01T00:00:00",
            "duration_seconds": 0.12,
        },
        {},
    )
    second = _derive_reproducibility_oracle_fields(
        {
            "reproducibility_oracle_enabled": True,
            "seed": "42",
            "analysis_status": "success",
            "started_at": "2026-01-02T00:00:00",
            "duration_seconds": 9.87,
        },
        {},
    )

    assert first["reproducibility_oracle_valid"] is True
    assert second["reproducibility_oracle_valid"] is True
    assert first["reproducibility_oracle_seed"] == "42"
    assert second["reproducibility_oracle_seed"] == "42"
    assert first["reproducibility_oracle_digest"] == second["reproducibility_oracle_digest"]


def test_reproducibility_oracle_detects_seed_locked_mismatch() -> None:
    baseline = _derive_reproducibility_oracle_fields(
        {
            "reproducibility_oracle_enabled": True,
            "seed": 7,
            "analysis_status": "success",
            "selected_case": "case-A",
        },
        {},
    )
    candidate = _derive_reproducibility_oracle_fields(
        {
            "reproducibility_oracle_enabled": True,
            "seed": 7,
            "analysis_status": "success",
            "selected_case": "case-B",
            "reproducibility_oracle_expected_digest": baseline["reproducibility_oracle_digest"],
        },
        {},
    )

    assert candidate["reproducibility_oracle_valid"] is False
    assert candidate["reproducibility_oracle_reason"] == "seed_locked_oracle_mismatch"


def test_reproducibility_oracle_requires_seed_when_enabled() -> None:
    result = _derive_reproducibility_oracle_fields(
        {"reproducibility_oracle_enabled": True},
        {},
    )
    assert result["reproducibility_oracle_valid"] is False
    assert result["reproducibility_oracle_reason"] == "seed_missing"


def test_normalize_benchmark_record_embeds_reproducibility_oracle_fields() -> None:
    normalized = _normalize_benchmark_record(
        {
            "model_id": "m1",
            "prompt_id": "p1",
            "reproducibility_oracle_enabled": True,
            "seed": 123,
            "__graph_state": {"job_status": "completed"},
        }
    )

    assert normalized["reproducibility_oracle_enabled"] is True
    assert normalized["reproducibility_oracle_seed"] == "123"
    assert isinstance(normalized["reproducibility_oracle_digest"], str)
    assert normalized["reproducibility_oracle_valid"] is True


def test_route_after_manifest_validation_blocks_on_failed_oracle() -> None:
    assert (
        _route_after_manifest_validation(
            {
                "paper_manifest_valid": True,
                "reproducibility_oracle_enabled": True,
                "reproducibility_oracle_valid": False,
            }
        )
        == "clarification_handler"
    )
    assert (
        _route_after_manifest_validation(
            {
                "paper_manifest_valid": True,
                "reproducibility_oracle_enabled": True,
                "reproducibility_oracle_valid": True,
            }
        )
        == "input_writer_node"
    )


def test_route_after_manifest_validation_still_blocks_manifest_failures() -> None:
    assert _route_after_manifest_validation({"paper_manifest_valid": False}) == "clarification_handler"


def test_create_graph_compiles_with_oracle_manifest_route() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()
    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("paper_manifest_gate_node", "clarification_handler") in edges
    assert ("paper_manifest_gate_node", "input_writer_node") in edges
