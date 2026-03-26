"""Unit tests for claim/evidence coverage matrix artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.benchmark_runner import (
    _as_float,
    _as_int,
    _build_claim_evidence_coverage_matrix,
    _build_command,
    _build_config_for_model,
    _derive_benchmark_metrics_fields,
    _derive_claim_evidence_fields,
    _derive_gate_approval_fields,
    _derive_iteration_fields,
    _derive_validation_fields,
    _ensure_prompt_entry,
    _execute_case,
    _extract_violations,
    _format_command,
    _load_data,
    _load_prompt_text,
    _merge_dicts,
    _normalize_benchmark_record,
    _privacy_config,
    _slugify,
    _write_jsonl,
    collect_cases,
    expand_case_runs,
    filter_cases,
    init_case_run_state,
    run_case_suite,
    run_model_benchmark,
    validate_case_files,
)
from src.graph import (
    _paper_validator_enabled,
    _route_after_architect,
    _route_after_clarification,
    _route_after_paper_validator,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    sweep_execution_handler_node,
)

# Coverage compatibility for file-path based coverage targets.
sys.modules["src/benchmark_runner.py"] = sys.modules["src.benchmark_runner"]
sys.modules["src/graph.py"] = sys.modules["src.graph"]


def test_case_suite_helpers_and_loaders(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        """
$schema: https://json-schema.org/draft/2020-12/schema
required: [solver, cases]
properties:
  solver:
    type: string
  cases:
    type: array
    items:
      type: object
      required: [id, solver, case_name, scaling]
      properties:
        id: {type: string}
        solver: {type: string}
        case_name: {type: string}
        scaling:
          type: object
          required: [sizes]
          properties:
            sizes:
              type: array
""".strip()
    )

    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "good.yaml").write_text(
        """
suite_id: suite.good
solver: castro
cases:
  - id: c1
    solver: castro
    case_name: Case One
    scaling:
      sizes:
        - label: tiny
          grid: [32, 32, 32]
          amr_levels: 1
""".strip()
    )
    (cases_dir / "bad.yaml").write_text(
        """
suite_id: suite.bad
solver: castro
cases:
  - id: c2
    solver: pele
    case_name: Case Two
    scaling:
      sizes:
        - label: mid
          grid: [64, 64, 64]
          amr_levels: 2
""".strip()
    )

    errors = validate_case_files(schema_path, cases_dir)
    assert any("does not match suite solver" in err for err in errors)

    collected = collect_cases(cases_dir)
    assert len(collected) == 2
    assert collected[0]["_suite_id"].startswith("suite")

    filtered = filter_cases(collected, solver="castro", case_ids=["c1"])
    assert [case["id"] for case in filtered] == ["c1"]

    runs = expand_case_runs(filtered)
    assert runs[0]["case_id"] == "c1"
    assert runs[0]["size_label"] == "tiny"

    run_state = init_case_run_state(filtered)
    assert run_state["cases"]["c1"]["sizes"]["tiny"]["status"] == "pending"

    json_path = tmp_path / "config.json"
    yaml_path = tmp_path / "config.yaml"
    txt_path = tmp_path / "config.txt"
    json_path.write_text('{"k": 1}')
    yaml_path.write_text("k: 2\n")
    txt_path.write_text("k=3")

    assert _load_data(json_path) == {"k": 1}
    assert _load_data(yaml_path) == {"k": 2}
    with pytest.raises(ValueError):
        _load_data(txt_path)


def test_execute_and_run_case_suite_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = {
        "id": "c1",
        "solver": "castro",
        "case_name": "Case One",
        "case_dir": str(tmp_path),
        "run": {"command": "echo {solver} {label}", "working_dir": str(tmp_path)},
        "scaling": {"sizes": [{"label": "tiny", "grid": [8, 8, 8], "amr_levels": 1}]},
        "_source": "suite.yaml",
    }
    size = case["scaling"]["sizes"][0]

    assert _format_command({"run": {}}, size) is None
    assert _execute_case({"run": {}}, size, dry_run=False) == ("skipped", "no command defined")

    status, detail = _execute_case(case, size, dry_run=True)
    assert status == "planned"
    assert "castro tiny" in detail

    monkeypatch.setattr(
        "src.benchmark_runner.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    assert _execute_case(case, size, dry_run=False)[0] == "complete"

    monkeypatch.setattr(
        "src.benchmark_runner.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=2),
    )
    assert _execute_case(case, size, dry_run=False)[0] == "failed"

    run_dir = tmp_path / "run"
    rc = run_case_suite([case], run_dir, resume=False, dry_run=True)
    assert rc == 0
    assert (run_dir / "run_state.json").exists()

    with pytest.raises(FileNotFoundError):
        run_case_suite([case], tmp_path / "missing_resume", resume=True, dry_run=False)


def test_prompt_config_command_and_basic_converters(tmp_path: Path) -> None:
    merged = _merge_dicts({"a": {"x": 1}, "b": 2}, {"a": {"y": 3}, "c": 4})
    assert merged == {"a": {"x": 1, "y": 3}, "b": 2, "c": 4}

    s_entry = _ensure_prompt_entry("hello", 1)
    d_entry = _ensure_prompt_entry({"id": "p2", "prompt": "world"}, 2)
    assert s_entry["id"] == "prompt_001"
    assert d_entry["id"] == "p2"
    with pytest.raises(ValueError):
        _ensure_prompt_entry(3.14, 3)

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("  from file  ")
    assert _load_prompt_text({"prompt": "inline"}) == "inline"
    assert _load_prompt_text({"prompt_path": str(prompt_path)}) == "from file"
    assert _load_prompt_text({}) is None

    base_config_path = tmp_path / "base.json"
    base_config_path.write_text('{"llm_provider":"cborg","temperature":0.1}')
    cfg = _build_config_for_model(
        {
            "id": "model A",
            "config_path": str(base_config_path),
            "overrides": {"temperature": 0.0},
        },
        tmp_path,
    )
    assert cfg is not None
    assert json.loads(cfg.read_text())["temperature"] == 0.0
    assert _build_config_for_model({"id": "empty", "overrides": {}}, tmp_path) is None

    cmd = _build_command(
        cfg,
        {"prompt": "hi"},
        tmp_path,
        {
            "run_mode": "batch",
            "environment": "ci",
            "inputs_file_strategy": "strict",
            "remap_strategy": "none",
            "inputs_file_override": "in", 
            "baseline_override": "base",
            "baseline_switch_after_retries": 2,
            "llm_gate_strategy": "strict",
            "indexing_strategy": "hybrid",
            "run_ntasks": 4,
            "run_serial": True,
            "dry_run": True,
            "preconfirm": True,
            "save_workflow": True,
            "save_transcript": True,
            "save_log": True,
            "verbose": True,
            "extra_args": ["--x", 1],
        },
        tmp_path / "ctx.json",
    )
    assert "--config" in cmd
    assert "--benchmark-context" in cmd
    assert "--run-serial" in cmd
    assert "--x" in cmd

    cmd_with_prompt_path = _build_command(
        None,
        {"prompt_path": str(prompt_path)},
        tmp_path,
        {},
        None,
    )
    assert "--prompt-path" in cmd_with_prompt_path

    with pytest.raises(ValueError):
        _build_command(None, {}, tmp_path, {}, None)

    assert _as_int("7") == 7
    assert _as_int("x") is None
    assert _as_float("7.5") == 7.5
    assert _as_float("x") is None


def test_record_derivation_and_jsonl_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "model_id": "m1",
        "prompt_id": "p1",
        "analysis_status": "completed",
        "review_analysis": {
            "violations": [
                {"rule_name": "SchemaRule", "message": "schema mismatch", "severity": "error"},
                {"rule_name": "PhysicsRule", "message": "watch physics", "severity": "warning"},
                {"rule_name": "PhysicsRule", "message": "bad physics", "severity": "error"},
                {"rule_name": "ResourceRule", "message": "resource bad", "severity": "error"},
            ]
        },
        "claims": [{"id": "cl1", "claim": "c1", "evidence_refs": ["ev1"]}, "c2"],
        "evidence": [{"id": "ev1"}],
        "iteration": 3,
        "retry_count": 1,
        "duration_seconds": 1.5,
    }

    violations = _extract_violations(payload, {})
    assert len(violations) == 4
    assert _extract_violations({}, {"review_analysis": {"violations": [{"rule_name": "X"}]}})

    validation = _derive_validation_fields(payload, {})
    assert validation["schema_valid"] is False
    assert validation["physics_valid"] is False
    assert validation["resource_valid"] is False
    assert validation["schema_errors"] == ["schema mismatch"]

    iteration = _derive_iteration_fields(payload, {})
    assert iteration["iteration_count"] == 3
    assert iteration["reviewer_retry_count"] == 1

    iteration_missing = _derive_iteration_fields({}, {})
    assert iteration_missing["iteration_count"] is None
    assert iteration_missing["iteration_count_unavailable_reason"] == "graph_state.iteration_missing"

    metrics = _derive_benchmark_metrics_fields(payload, {"metrics": {"stages": {"architect": {"llm": {"total_calls": 9}}}}})
    assert metrics["converged"] is True
    assert metrics["wall_time_seconds"] == 1.5
    assert metrics["llm_call_count"] == 9

    approvals = _derive_gate_approval_fields({}, {"gate_approvals": [{"decision": "approved"}]})
    assert approvals["gate_approval_count"] == 1

    claim_fields = _derive_claim_evidence_fields(payload, {})
    assert claim_fields["claim_count"] == 2
    assert claim_fields["covered_claim_count"] == 1
    assert claim_fields["claim_evidence_matrix_status"] == "partial"

    raw_matrix_fields = _derive_claim_evidence_fields(
        {"claim_evidence_matrix": [{"claim_id": "c1", "claim": "Claim", "evidence_refs": ["E1"]}]},
        {},
    )
    assert raw_matrix_fields["claim_evidence_matrix_status"] == "complete"

    normalized = _normalize_benchmark_record(payload)
    assert normalized["claim_count"] == 2
    assert normalized["gate_approval_count"] == 0

    jsonl_path = tmp_path / "bench.jsonl"
    written = _write_jsonl(jsonl_path, payload)
    line = json.loads(jsonl_path.read_text().splitlines()[0])
    assert line["prompt_id"] == "p1"
    assert written["claim_count"] == 2

    def fake_sanitize(item, config):
        item = dict(item)
        item["sanitized"] = config.privacy_mode
        return item

    monkeypatch.setattr("src.utils.privacy.sanitize_payload", fake_sanitize)
    cfg = _privacy_config({"privacy_mode": "strict", "privacy_hash_salt": "salt"})
    assert cfg is not None
    sanitized = _write_jsonl(tmp_path / "sanitized.jsonl", payload, config=cfg)
    assert sanitized["sanitized"] == "strict"

    assert _privacy_config({}) is None
    assert _slugify("model alpha/beta") == "model_alpha_beta"


def test_matrix_builder_and_graph_routes_compile() -> None:
    matrix = _build_claim_evidence_coverage_matrix(
        [
            {"claim_count": 2, "covered_claim_count": 1},
            {"claim_count": 1, "covered_claim_count": 1},
        ]
    )
    assert matrix["total_claims"] == 3
    assert matrix["total_covered_claims"] == 2
    assert 0.0 < matrix["coverage_ratio"] < 1.0

    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"
    assert _route_after_sweep_detection({"sweep_id": "sweep"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"
    assert _paper_validator_enabled({"config": {"paper_validator_enabled": True}}) is True
    assert _paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=False)}) is False
    assert _route_after_architect({"config": {"paper_validator_enabled": True}}) == "paper_validator_node"
    assert _route_after_architect({"config": {"paper_validator_enabled": False}}) == "intent_extraction_node"
    assert _route_after_paper_validator({"paper_validation_passed": False}) == "end"
    assert (
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "claim_evidence_matrix_required": True,
                "claim_evidence_matrix_complete": False,
            }
        )
        == "end"
    )
    assert (
        _route_after_paper_validator(
            {
                "paper_validation_passed": True,
                "claim_evidence_matrix_required": True,
                "claim_evidence_matrix_complete": True,
            }
        )
        == "intent_extraction_node"
    )

    clarification_state = {"clarification_questions": ["q1"]}
    sweep_state = {"sweep_id": "sweep-1", "sweep_parameter": "max_step"}
    assert clarification_handler_node(clarification_state) is clarification_state
    assert sweep_execution_handler_node(sweep_state) is sweep_state

    graph_def = create_graph().compile().get_graph()
    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("architect_node", "paper_validator_node") in edges
    assert ("paper_validator_node", "__end__") in edges


def test_run_model_benchmark_writes_matrix_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("prompt from file")

    bench_config = {
        "prompts": [
            "inline prompt",
            {"id": "p2", "prompt_path": str(prompt_path), "case_id": "case-2", "solver": "castro"},
        ],
        "models": [
            {
                "id": "m1",
                "overrides": {"llm_provider": "cborg", "llm_model": "x"},
                "env": {"FOO": "bar"},
            }
        ],
        "run_args": {"dry_run": True, "timeout_seconds": 1},
        "env": {"GLOBAL": "1"},
    }
    config_path = tmp_path / "bench.json"
    config_path.write_text(json.dumps(bench_config))

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "job_status": "completed",
                    "claims": [
                        {"id": "c1", "claim": "Claim 1", "evidence_refs": ["e1"]},
                        {"id": "c2", "claim": "Claim 2", "evidence_refs": []},
                    ],
                    "evidence": [{"id": "e1"}],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("src.benchmark_runner.subprocess.run", fake_run)

    result = run_model_benchmark(config_path, tmp_path, run_name="claim_evidence_matrix")
    run_dir = Path(result["run_dir"])
    matrix_file = run_dir / "claim_evidence_coverage_matrix.json"

    assert matrix_file.exists()
    matrix = json.loads(matrix_file.read_text())
    assert matrix["total_records"] == 2
    assert matrix["total_claims"] == 4
    assert matrix["total_covered_claims"] == 2

    metrics_line = json.loads((run_dir / "benchmark_runs.jsonl").read_text().splitlines()[0])
    assert metrics_line["claim_evidence_matrix_status"] == "partial"


def test_run_model_benchmark_handles_timeout_parse_and_runner_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = {
        "prompts": [{"id": "p1", "prompt": "hello"}],
        "models": [{"id": "m1", "overrides": {"llm_provider": "cborg"}}],
        "run_args": {"dry_run": False, "timeout_seconds": 1},
    }
    config_path = tmp_path / "bench.json"
    config_path.write_text(json.dumps(config))

    timeout_exc = subprocess.TimeoutExpired(cmd=["x"], timeout=1)

    monkeypatch.setattr("src.benchmark_runner.subprocess.run", lambda *args, **kwargs: (_ for _ in ()).throw(timeout_exc))
    out_timeout = run_model_benchmark(config_path, tmp_path, run_name="timeout_run")
    timeout_record = json.loads((Path(out_timeout["run_dir"]) / "benchmark_runs.jsonl").read_text().splitlines()[0])
    assert timeout_record["error"].startswith("timeout_after_")

    monkeypatch.setattr(
        "src.benchmark_runner.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="not-json", stderr=""),
    )
    out_parse = run_model_benchmark(config_path, tmp_path, run_name="parse_run")
    parse_record = json.loads((Path(out_parse["run_dir"]) / "benchmark_runs.jsonl").read_text().splitlines()[0])
    assert parse_record["error"].startswith("json_parse_failed")

    monkeypatch.setattr(
        "src.benchmark_runner.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    out_error = run_model_benchmark(config_path, tmp_path, run_name="error_run")
    error_record = json.loads((Path(out_error["run_dir"]) / "benchmark_runs.jsonl").read_text().splitlines()[0])
    assert error_record["error"].startswith("runner_error")
