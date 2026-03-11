"""Unit tests for risk-owner and release-gate validation paths."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

GRAPH_MODULE_NAME = "src/graph.py"
GRAPH_PATH = Path(__file__).resolve().parents[2] / "src" / "graph.py"
GRAPH_SPEC = importlib.util.spec_from_file_location(GRAPH_MODULE_NAME, GRAPH_PATH)
assert GRAPH_SPEC is not None and GRAPH_SPEC.loader is not None
GRAPH_MODULE = importlib.util.module_from_spec(GRAPH_SPEC)
sys.modules[GRAPH_MODULE_NAME] = GRAPH_MODULE
GRAPH_SPEC.loader.exec_module(GRAPH_MODULE)

METRICS_MODULE_NAME = "src/utils/metrics.py"
METRICS_PATH = Path(__file__).resolve().parents[2] / "src" / "utils" / "metrics.py"
METRICS_SPEC = importlib.util.spec_from_file_location(METRICS_MODULE_NAME, METRICS_PATH)
assert METRICS_SPEC is not None and METRICS_SPEC.loader is not None
METRICS_MODULE = importlib.util.module_from_spec(METRICS_SPEC)
sys.modules[METRICS_MODULE_NAME] = METRICS_MODULE
METRICS_SPEC.loader.exec_module(METRICS_MODULE)


class _FakeUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class _FakeResponse:
    def __init__(self, model: str, usage: _FakeUsage) -> None:
        self.model = model
        self.usage = usage


def test_validate_risk_owner_status_updates_paths() -> None:
    assert METRICS_MODULE.validate_risk_owner_status_updates([], []) == {
        "passed": False,
        "failed_risks": [],
        "reason": "missing_release_gate_milestones",
    }

    assert (
        METRICS_MODULE.validate_risk_owner_status_updates([], ["design", "release"])["reason"]
        == "missing_risk_entries"
    )

    failed = METRICS_MODULE.validate_risk_owner_status_updates(
        [
            "invalid",
            {"risk_id": "R-1", "owner": "", "status_updates": {"design": "open", "release": "open"}},
            {"risk_id": "R-2", "owner": "alice", "status_updates": {"design": "closed"}},
        ],
        ["design", "release"],
    )
    assert failed["passed"] is False
    assert failed["reason"] == "risk_owner_status_updates_not_met"
    assert failed["failed_risks"] == ["risk_001", "R-1", "R-2"]

    passed = METRICS_MODULE.validate_risk_owner_status_updates(
        [
            {
                "risk_id": "R-3",
                "owner": "bob",
                "status_updates": {"design": "open", "release": "mitigated"},
            }
        ],
        ["design", "release"],
    )
    assert passed == {"passed": True, "failed_risks": [], "reason": "ok"}


def test_metrics_collector_core_paths() -> None:
    collector = METRICS_MODULE.MetricsCollector()

    with METRICS_MODULE.metrics_context("architect", node="architect", iteration=2):
        event = collector.record_event("custom", {"ok": True})
    assert event["stage"] == "architect"
    assert event["node"] == "architect"
    assert event["iteration"] == 2

    with METRICS_MODULE.metrics_context("architect", node="architect", iteration=2):
        with METRICS_MODULE.metrics_extra({"run_id": "r-1"}):
            annotated = collector.record_event("annotated", {"x": 1})
        plain = collector.record_event("plain", {"x": 2})
        usage_event = collector.record_llm_usage(_FakeResponse("m-a", _FakeUsage(4, 6)), provider="p1")
    assert annotated["context"] == {"run_id": "r-1"}
    assert "context" not in plain
    assert usage_event is not None

    no_context = collector.record_event("free", {"ok": True})
    assert no_context["stage"] == "unknown"
    assert no_context["node"] == "unknown"

    summary = collector.summarize_stage("architect", iteration=2)
    assert "llm" in summary

    workflow = collector.build_workflow_summary()
    assert workflow["tokens_total"] == 10
    assert workflow["models"] == ["m-a"]
    assert workflow["providers"] == ["p1"]

    events = collector.events()
    assert len(events) >= 5
    events.append({"type": "tampered"})
    assert len(collector.events()) < len(events)

    collector.reset()
    assert collector.events() == []

    assert METRICS_MODULE._latency_ms(None) is None
    assert METRICS_MODULE._latency_ms(2.0, 1.0) == 0.0


def test_graph_validators_and_risk_owner_status_gate() -> None:
    bypass_state = {"risk_owner_status_validation_required": False}
    assert GRAPH_MODULE._risk_owner_status_updates_valid(bypass_state) is True
    assert "risk_owner_status_validation" not in bypass_state

    fail_state = {
        "risk_owner_status_validation_required": True,
        "release_gate_milestones": ["design", "release"],
        "risk_entries": [{"risk_id": "R-1", "owner": "", "status_updates": {"design": "open"}}],
    }
    assert GRAPH_MODULE._risk_owner_status_updates_valid(fail_state) is False
    assert fail_state["risk_owner_status_validation"]["reason"] == "risk_owner_status_updates_not_met"
    assert fail_state["risk_owner_status_validation_complete"] is False

    pass_state = {
        "risk_owner_status_validation_required": True,
        "release_gate_milestones": ["design", "release"],
        "risk_entries": [
            {
                "risk_id": "R-2",
                "owner": "alice",
                "status_updates": {"design": "open", "release": "closed"},
            }
        ],
    }
    assert GRAPH_MODULE._risk_owner_status_updates_valid(pass_state) is True
    assert pass_state["risk_owner_status_validation"]["passed"] is True


def test_confidence_interval_and_strategy_reporting_paths() -> None:
    empty = GRAPH_MODULE.compute_confidence_interval([])
    assert empty["confidence_interval_available"] is False
    assert empty["sample_size"] == 0

    single = GRAPH_MODULE.compute_confidence_interval([0.4])
    assert single["confidence_interval_available"] is False
    assert single["sample_size"] == 1

    multi = GRAPH_MODULE.compute_confidence_interval([0.4, 0.8, 0.6], confidence_level=0.99)
    assert multi["confidence_interval_available"] is True
    assert multi["sample_size"] == 3

    assert GRAPH_MODULE._get_z_score(0.90) == 1.645
    assert GRAPH_MODULE._get_z_score(0.95) == 1.96
    assert GRAPH_MODULE._get_z_score(0.99) == 2.576
    assert GRAPH_MODULE._get_z_score(0.83) == 1.96

    assert GRAPH_MODULE._extract_strategy_samples({"confidence_scores": [1, "x", 0.5]}) == [1.0, 0.5]
    assert GRAPH_MODULE._extract_strategy_samples([0.2, None, 0.3]) == [0.2, 0.3]
    assert GRAPH_MODULE._extract_strategy_samples("invalid") == []

    state = {
        "strategy_confidence_level": 0.9,
        "strategy_metrics": {
            "rag": {"confidence_scores": [0.5, 0.7, 0.9]},
            "llm": [0.6],
        },
    }
    GRAPH_MODULE._build_strategy_confidence_report(state)
    assert state["strategy_confidence_intervals"]["rag"]["confidence_interval_available"] is True
    assert state["strategy_reporting"]["strategies_with_intervals"] == ["rag"]

    no_metrics_state = {}
    GRAPH_MODULE._build_strategy_confidence_report(no_metrics_state)
    assert "strategy_confidence_intervals" not in no_metrics_state


def test_traceability_and_mapping_branch_matrix() -> None:
    precomputed_true = {
        "uc_summary_traceability_required": True,
        "uc_summary_traceability_complete": True,
    }
    assert GRAPH_MODULE._uc_summary_traceability_valid(precomputed_true) is True
    assert precomputed_true["uc_summary_traceability_validation"]["reason"] == "ok"

    precomputed_false = {
        "uc_summary_traceability_required": True,
        "uc_summary_traceability_complete": False,
    }
    assert GRAPH_MODULE._uc_summary_traceability_valid(precomputed_false) is False
    assert precomputed_false["uc_summary_traceability_validation"]["reason"] == "traceability_not_met"

    mixed_entries = {
        "uc_summary_traceability_required": True,
        "uc_summary_entries": [
            "invalid",
            {"id": "UC-2", "tests": []},
            {"uc_id": "UC-3", "artifacts": ["tests/unit/test_ok.py"]},
        ],
    }
    assert GRAPH_MODULE._uc_summary_traceability_valid(mixed_entries) is False
    assert mixed_entries["uc_summary_traceability_validation"]["failed_use_cases"] == ["uc_001", "UC-2"]

    mapping_precomputed_true = {
        "feature_test_fixture_mapping_required": True,
        "feature_test_fixture_mapping_complete": True,
    }
    assert GRAPH_MODULE._feature_fixture_mapping_valid(mapping_precomputed_true) is True

    mapping_precomputed_false = {
        "feature_test_fixture_mapping_required": True,
        "feature_test_fixture_mapping_complete": False,
    }
    assert GRAPH_MODULE._feature_fixture_mapping_valid(mapping_precomputed_false) is False

    mapping_list = {
        "feature_test_fixture_mapping_required": True,
        "feature_test_fixture_mapping": [
            "invalid",
            {"id": "F-2", "tests": ["tests/unit/t.py"], "fixtures": []},
            {"feature_label": "F-3", "tests": "tests/unit/t.py", "fixtures": "tests/fixtures/f.json"},
        ],
    }
    assert GRAPH_MODULE._feature_fixture_mapping_valid(mapping_list) is False
    assert mapping_list["feature_test_fixture_mapping_validation"]["missing_features"] == ["feature_001", "F-2"]

    mapping_missing_markdown = {"feature_test_fixture_mapping_required": True}
    assert GRAPH_MODULE._feature_fixture_mapping_valid(mapping_missing_markdown) is False
    assert mapping_missing_markdown["feature_test_fixture_mapping_validation"]["reason"] == "missing_feature_blocks_markdown"

    mapping_markdown = {
        "feature_test_fixture_mapping_required": True,
        "feature_blocks_markdown": (
            "## [F-1] One\n"
            "Tests/Fixtures: tests/unit/test_one.py, tests/fixtures/one.json\n"
            "## [F-2] Two\n"
            "Tests/Fixtures: tests/unit/test_two.py\n"
        ),
    }
    assert GRAPH_MODULE._feature_fixture_mapping_valid(mapping_markdown) is False
    assert mapping_markdown["feature_test_fixture_mapping_validation"]["missing_features"] == ["## [F-2] Two"]


def test_route_after_paper_validator_enforces_risk_owner_status_updates() -> None:
    fail_route_state = {
        "paper_validation_passed": True,
        "risk_owner_status_validation_required": True,
        "release_gate_milestones": ["design", "release"],
        "risk_entries": [{"risk_id": "R-1", "owner": "", "status_updates": {"design": "open"}}],
    }
    assert GRAPH_MODULE._route_after_paper_validator(fail_route_state) == "end"
    assert fail_route_state["risk_owner_status_validation"]["passed"] is False

    pass_route_state = {
        "paper_validation_passed": True,
        "risk_owner_status_validation_required": True,
        "release_gate_milestones": ["design", "release"],
        "risk_entries": [
            {
                "risk_id": "R-2",
                "owner": "alice",
                "status_updates": {"design": "open", "release": "closed"},
            }
        ],
        "release_gate_validation_required": True,
        "release_gate_criteria": [{"id": "ci", "passed": True}],
    }
    assert GRAPH_MODULE._route_after_paper_validator(pass_route_state) == "intent_extraction_node"


def test_route_after_paper_validator_branch_matrix() -> None:
    assert GRAPH_MODULE._route_after_paper_validator({"paper_validation_passed": False}) == "end"

    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": "## [F-1] Missing\nScope: docs-only",
            }
        )
        == "end"
    )

    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_validation_required": True,
                "feature_blocks_validation_passed": False,
            }
        )
        == "end"
    )
    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_validation_required": True,
                "feature_blocks_validation_passed": False,
                "feature_blocks_markdown": "## [F-11] Complete\nTests/Fixtures: tests/unit/test_ok.py",
            }
        )
        == "end"
    )

    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "new_file_helper_extraction_validation_required": True,
                "new_file_helper_extraction_validation_passed": False,
            }
        )
        == "end"
    )

    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "claim_evidence_matrix_required": True,
                "claim_evidence_matrix_complete": False,
            }
        )
        == "end"
    )

    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "uc_summary_traceability_required": True,
            }
        )
        == "end"
    )

    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_test_fixture_mapping_required": True,
                "feature_blocks_markdown": "## [F-10] Missing\nTests/Fixtures: tests/unit/test_only.py",
            }
        )
        == "end"
    )

    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "risk_owner_status_validation_required": True,
                "release_gate_milestones": ["design"],
                "risk_entries": [{"risk_id": "R-1", "owner": "", "status_updates": {}}],
            }
        )
        == "end"
    )

    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "release_gate_validation_required": True,
                "release_gate_criteria": [{"id": "ci", "passed": False}],
            }
        )
        == "end"
    )

    helper_fail_markdown = (
        "## [F-100] Large File\n"
        "Tests/Fixtures: tests/unit/test_ok.py\n"
        "New files:\n"
        "- src/new_big.py (120 LOC)\n"
    )
    assert (
        GRAPH_MODULE._route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "feature_blocks_markdown": helper_fail_markdown,
            }
        )
        == "end"
    )

    helper_pass_markdown = (
        "## [F-101] Large File\n"
        "Tests/Fixtures: tests/unit/test_ok.py, tests/fixtures/ok.json\n"
        "New files:\n"
        "- src/new_big.py (120 LOC)\n"
        "Helper extraction: extracted to src/helpers.py\n"
    )
    helper_pass_state = {
        "paper_validation_passed": True,
        "feature_blocks_markdown": helper_pass_markdown,
        "new_file_helper_extraction_validation_required": True,
        "claim_evidence_matrix_required": True,
        "claim_evidence_matrix_complete": True,
        "release_gate_validation_required": True,
        "release_gate_criteria": [{"id": "ci", "passed": True}],
    }
    assert GRAPH_MODULE._route_after_paper_validator(helper_pass_state) == "intent_extraction_node"
    assert helper_pass_state["new_file_helper_extraction_validation_passed"] is True


def test_existing_graph_wiring_and_validators_still_hold() -> None:
    assert GRAPH_MODULE._route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert GRAPH_MODULE._route_after_clarification({}) == "input_writer_node"

    assert GRAPH_MODULE._route_after_sweep_detection({"sweep_id": "sweep-1"}) == "sweep_execution_handler"
    assert GRAPH_MODULE._route_after_sweep_detection({}) == "architect_node"

    assert GRAPH_MODULE._paper_validator_enabled({"config": {"paper_validator_enabled": True}}) is True
    assert GRAPH_MODULE._paper_validator_enabled({"config": {"paper_validator_enabled": False}}) is False
    assert GRAPH_MODULE._paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True
    assert GRAPH_MODULE._paper_validator_enabled({}) is False

    assert GRAPH_MODULE._route_after_architect({"config": {"paper_validator_enabled": True}}) == "paper_validator_node"
    assert GRAPH_MODULE._route_after_architect({"config": {"paper_validator_enabled": False}}) == "intent_extraction_node"

    uc_missing = {"uc_summary_traceability_required": True}
    assert GRAPH_MODULE._uc_summary_traceability_valid(uc_missing) is False
    assert uc_missing["uc_summary_traceability_validation"]["reason"] == "missing_uc_summary_entries"

    uc_ok = {
        "uc_summary_traceability_required": True,
        "uc_summary_entries": [{"uc_id": "UC-1", "artifacts": ["tests/unit/test_ok.py"]}],
    }
    assert GRAPH_MODULE._uc_summary_traceability_valid(uc_ok) is True

    mapping_missing = {
        "feature_test_fixture_mapping_required": True,
        "feature_blocks_markdown": "## [F-001] Feature\nTests/Fixtures: tests/unit/test_ok.py",
    }
    assert GRAPH_MODULE._feature_fixture_mapping_valid(mapping_missing) is False

    mapping_ok = {
        "feature_test_fixture_mapping_required": True,
        "feature_test_fixture_mapping": [
            {"feature_label": "F-001", "tests": ["tests/unit/test_ok.py"], "fixtures": ["tests/fixtures/f.json"]}
        ],
    }
    assert GRAPH_MODULE._feature_fixture_mapping_valid(mapping_ok) is True

    release_missing = {"release_gate_validation_required": True}
    assert GRAPH_MODULE._release_gate_criteria_valid(release_missing) is False

    release_fail = {
        "release_gate_validation_required": True,
        "release_gate_criteria": [{"id": "ci", "passed": False}, "invalid"],
    }
    assert GRAPH_MODULE._release_gate_criteria_valid(release_fail) is False

    release_ok = {
        "release_gate_validation_required": True,
        "release_gate_criteria": [{"id": "ci", "passed": True}, {"id": "docs", "status": "ok"}],
    }
    assert GRAPH_MODULE._release_gate_criteria_valid(release_ok) is True

    clarification_state = {"clarification_questions": ["q1"]}
    sweep_state = {"sweep_id": "sweep-1", "sweep_parameter": "max_step"}
    assert GRAPH_MODULE.clarification_handler_node(clarification_state) is clarification_state
    assert GRAPH_MODULE.sweep_execution_handler_node(sweep_state) is sweep_state

    app = GRAPH_MODULE.create_graph().compile()
    graph_def = app.get_graph()
    nodes = set(graph_def.nodes.keys())
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert "architect_node" in nodes
    assert "paper_validator_node" in nodes
    assert "input_writer_node" in nodes
    assert ("__start__", "sweep_detection_node") in edges
    assert ("paper_validator_node", "__end__") in edges
