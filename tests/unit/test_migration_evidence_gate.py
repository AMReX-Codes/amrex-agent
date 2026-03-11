"""Migration evidence and index-growth proof tests."""

from __future__ import annotations

from pathlib import Path

from src.graph import (
    PHASE1_FEATURE_TRACE_MARKER,
    REQUIRED_BEHAVIOR_MARKER,
    _has_phase1_feature_trace,
    _has_required_behavior_item,
    _paper_validator_enabled,
    _route_after_clarification,
    _route_after_complexity_evidence,
    _route_after_paper_validator,
    _route_after_phase1_traceability,
    _route_after_postgresql_migration_evidence,
    _route_after_required_behavior_item,
    _route_after_sweep_detection,
    clarification_handler_node,
    complexity_evidence_handler_node,
    complexity_evidence_node,
    create_graph,
    paper_validator_node,
    phase1_traceability_handler_node,
    postgresql_migration_handler_node,
    required_behavior_handler_node,
    session_dependency_handler_node,
    sweep_execution_handler_node,
)
from src.services.workflow_store import (
    POSTGRESQL_MIGRATION_EVIDENCE_MARKER,
    WorkflowStore,
    _non_empty_str,
    collect_postgresql_migration_evidence,
    has_postgresql_migration_index_growth_proof,
)
from src.session_manager import SESSION_DEPENDENCY_COMPLETION_MARKER


def test_workflow_store_postgresql_migration_evidence_and_roundtrip(monkeypatch, tmp_path: Path):
    assert _non_empty_str(None) is None
    assert _non_empty_str(7) is None
    assert _non_empty_str("   ") is None
    assert _non_empty_str(" runbook.md ") == "runbook.md"

    assert collect_postgresql_migration_evidence({}) == {
        "migration_runbook_ref": None,
        "index_growth_proof_ref": None,
        "proof_complete": False,
    }
    assert collect_postgresql_migration_evidence(
        {"postgresql_migration_runbook_ref": "migration.md", "index_growth_proof_ref": "proof.csv"}
    ) == {
        "migration_runbook_ref": "migration.md",
        "index_growth_proof_ref": "proof.csv",
        "proof_complete": True,
    }
    assert collect_postgresql_migration_evidence(
        {
            POSTGRESQL_MIGRATION_EVIDENCE_MARKER: {
                "migration_runbook_ref": "docs/runbook.md",
                "index_growth_proof_ref": "artifacts/index_growth.json",
            }
        }
    ) == {
        "migration_runbook_ref": "docs/runbook.md",
        "index_growth_proof_ref": "artifacts/index_growth.json",
        "proof_complete": True,
    }

    assert has_postgresql_migration_index_growth_proof(None) is False
    assert has_postgresql_migration_index_growth_proof({}) is False
    assert has_postgresql_migration_index_growth_proof({"migration_runbook_ref": "x"}) is False
    assert (
        has_postgresql_migration_index_growth_proof(
            {"migration_runbook_ref": "runbook.md", "index_growth_proof_ref": "growth.md"}
        )
        is True
    )

    db_path = tmp_path / "nested" / "workflow_store.db"
    monkeypatch.setattr("src.services.workflow_store._utc_now", lambda: "2026-03-10T00:00:00+00:00")
    store = WorkflowStore(db_path)
    assert store.get_session("missing") is None

    store.upsert_session("sess-1", {"status": "created"})
    loaded = store.get_session("sess-1")
    assert loaded is not None
    assert loaded.session_id == "sess-1"
    assert loaded.state["status"] == "created"
    assert loaded.created_at == "2026-03-10T00:00:00+00:00"
    assert loaded.updated_at == "2026-03-10T00:00:00+00:00"

    monkeypatch.setattr("src.services.workflow_store._utc_now", lambda: "2026-03-10T00:00:01+00:00")
    store.upsert_session("sess-1", {"status": "updated"})
    updated = store.get_session("sess-1")
    assert updated is not None
    assert updated.state["status"] == "updated"
    assert updated.created_at == "2026-03-10T00:00:00+00:00"
    assert updated.updated_at == "2026-03-10T00:00:01+00:00"


def test_graph_postgresql_migration_gate_and_routes(monkeypatch):
    monkeypatch.setattr(
        "src.graph.collect_radon_complexity_evidence",
        lambda: {"radon_available": False, "passed": False},
    )

    assert _paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _paper_validator_enabled({"paper_source": "2401.12345"}) is True
    assert _paper_validator_enabled({}) is False

    assert _route_after_paper_validator({"paper_validator_enabled": True}) == "paper_validator_node"
    assert _route_after_paper_validator({}) == "input_writer_node"

    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"paper_source": "paper"}) == "paper_validator_node"
    assert _route_after_clarification({}) == "input_writer_node"

    assert _route_after_sweep_detection({}) == "architect_node"
    assert (
        _route_after_sweep_detection(
            {"sweep_id": "sweep", "enforce_session_dependency_gate": True}
        )
        == "session_dependency_handler"
    )
    assert _route_after_sweep_detection(
        {"sweep_id": "sweep", "session_markers": {SESSION_DEPENDENCY_COMPLETION_MARKER: True}}
    ) == "sweep_execution_handler"

    assert _has_phase1_feature_trace({}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: "invalid"}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"BAD": ["F1.1"]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": []}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": [1]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": ["X1"]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": "F1.1"}}) is True
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC2": ["F2B", "F6.2"]}}) is True

    assert _has_required_behavior_item({}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ""}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: "   "}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: 1}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: []}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ["ok", ""]}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: "must be true"}) is True
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ["must", "be true"]}) is True

    assert _route_after_postgresql_migration_evidence({}) == "end"
    assert (
        _route_after_postgresql_migration_evidence({"enforce_postgresql_migration_evidence": True})
        == "postgresql_migration_handler"
    )
    assert (
        _route_after_postgresql_migration_evidence(
            {
                "enforce_postgresql_migration_evidence": True,
                POSTGRESQL_MIGRATION_EVIDENCE_MARKER: {
                    "migration_runbook_ref": "docs/runbook.md",
                    "index_growth_proof_ref": "artifacts/index-growth.json",
                },
            }
        )
        == "end"
    )

    assert _route_after_required_behavior_item({}) == "end"
    assert (
        _route_after_required_behavior_item({"enforce_postgresql_migration_evidence": True})
        == "postgresql_migration_handler"
    )
    assert (
        _route_after_required_behavior_item({"enforce_required_behavior_item": True})
        == "required_behavior_handler"
    )
    assert (
        _route_after_required_behavior_item(
            {
                "enforce_required_behavior_item": True,
                REQUIRED_BEHAVIOR_MARKER: "must be true",
                "enforce_postgresql_migration_evidence": True,
            }
        )
        == "postgresql_migration_handler"
    )

    assert _route_after_phase1_traceability({}) == "end"
    assert (
        _route_after_phase1_traceability({"enforce_phase1_feature_trace": True})
        == "phase1_traceability_handler"
    )
    assert (
        _route_after_phase1_traceability(
            {
                "enforce_phase1_feature_trace": True,
                PHASE1_FEATURE_TRACE_MARKER: {"UC1": "F1.1"},
                "enforce_postgresql_migration_evidence": True,
            }
        )
        == "postgresql_migration_handler"
    )

    assert _route_after_complexity_evidence({}) == "end"
    assert (
        _route_after_complexity_evidence({"enforce_postgresql_migration_evidence": True})
        == "postgresql_migration_handler"
    )
    assert (
        _route_after_complexity_evidence({"enforce_required_behavior_item": True})
        == "required_behavior_handler"
    )
    assert (
        _route_after_complexity_evidence({"enforce_radon_complexity_evidence": True})
        == "complexity_evidence_handler"
    )
    assert (
        _route_after_complexity_evidence(
            {
                "enforce_radon_complexity_evidence": True,
                "radon_complexity_evidence": {"radon_available": True},
                "enforce_postgresql_migration_evidence": True,
            }
        )
        == "postgresql_migration_handler"
    )

    assert session_dependency_handler_node({})["required_marker"] == SESSION_DEPENDENCY_COMPLETION_MARKER

    enforced = complexity_evidence_node({"enforce_radon_complexity_evidence": True})
    assert enforced["radon_complexity_evidence"]["radon_available"] is False
    unchanged = complexity_evidence_node({"enforce_radon_complexity_evidence": False})
    assert "radon_complexity_evidence" not in unchanged

    complexity_handler = complexity_evidence_handler_node({})
    assert complexity_handler["required_marker"] == "radon_complexity_evidence"
    assert "Radon complexity evidence" in complexity_handler["dependency_error"]

    phase1_handler = phase1_traceability_handler_node({})
    assert phase1_handler["required_marker"] == PHASE1_FEATURE_TRACE_MARKER
    assert "traceability is required" in phase1_handler["dependency_error"]

    required_handler = required_behavior_handler_node({})
    assert required_handler["required_marker"] == REQUIRED_BEHAVIOR_MARKER
    assert "required behavior item is required" in required_handler["dependency_error"]

    postgres_handler = postgresql_migration_handler_node({})
    assert postgres_handler["required_marker"] == POSTGRESQL_MIGRATION_EVIDENCE_MARKER
    assert "PostgreSQL migration runbook and index growth proof" in postgres_handler["dependency_error"]
    assert postgres_handler[POSTGRESQL_MIGRATION_EVIDENCE_MARKER]["proof_complete"] is False

    existing = postgresql_migration_handler_node(
        {
            "dependency_error": "existing",
            "required_marker": "existing_marker",
            POSTGRESQL_MIGRATION_EVIDENCE_MARKER: {
                "migration_runbook_ref": "docs/migration.md",
                "index_growth_proof_ref": "artifacts/proof.json",
                "proof_complete": True,
            },
        }
    )
    assert existing["dependency_error"] == "existing"
    assert existing["required_marker"] == "existing_marker"
    assert existing[POSTGRESQL_MIGRATION_EVIDENCE_MARKER]["proof_complete"] is True

    assert clarification_handler_node({"clarification_questions": ["q1"]}) == {"clarification_questions": ["q1"]}
    assert sweep_execution_handler_node({"sweep_id": "id", "sweep_parameter": "p"})["sweep_id"] == "id"
    state = {"x": 1}
    assert paper_validator_node(state) is state

    app = create_graph().compile()
    graph_def = app.get_graph()
    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("complexity_evidence_node", "postgresql_migration_handler") in edges
    assert ("postgresql_migration_handler", "__end__") in edges
