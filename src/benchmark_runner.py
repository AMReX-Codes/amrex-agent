"""Benchmark runners for case suites and model comparisons."""

from __future__ import annotations

import json
import os
import re
import hashlib
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from types import SimpleNamespace

import yaml
from jsonschema import Draft202012Validator

from src.utils.job_status import normalize_job_status

DEFAULT_BENCHMARK_SEED = 1729


# ===== Shared helpers =====
_FEATURE_BLOCK_HEADER_RE = re.compile(r"^##\s+\[([^\]]+)\]\s*(.+?)\s*$")
_TESTS_FIXTURES_LINE_RE = re.compile(r"^tests/fixtures\s*:\s*(.+)$", re.IGNORECASE)
_REPRODUCIBILITY_ORACLE_VOLATILE_KEYS = frozenset(
    {
        "timestamp",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
        "duration_seconds",
        "elapsed_seconds",
        "run_id",
        "benchmark_run_id",
        "benchmark_timestamp",
        "trace_id",
        "session_id",
        "seed",
        "reproducibility_seed",
        "reproducibility_oracle_digest",
        "reproducibility_oracle_expected_digest",
        "reproducibility_oracle_valid",
        "reproducibility_oracle_reason",
    }
)


def _first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_reproducibility_seed(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _oracle_canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, child in sorted(value.items(), key=lambda item: str(item[0])):
            key_text = str(key)
            if key_text.startswith("__"):
                continue
            if key_text in _REPRODUCIBILITY_ORACLE_VOLATILE_KEYS:
                continue
            normalized[key_text] = _oracle_canonicalize(child)
        return normalized
    if isinstance(value, list):
        return [_oracle_canonicalize(item) for item in value]
    return value


def _build_reproducibility_oracle_digest(seed: str, payload: dict[str, Any]) -> str:
    canonical_payload = _oracle_canonicalize(payload)
    digest_input = {"seed": seed, "payload": canonical_payload}
    digest_body = json.dumps(digest_input, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(digest_body.encode("utf-8")).hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_data(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix in {".yaml", ".yml"}:
        return _load_yaml(path)
    raise ValueError(f"Unsupported config type: {path}")


# ===== Case suite runner =====

def validate_case_files(schema_path: Path, cases_dir: Path) -> list[str]:
    schema = _load_yaml(schema_path)
    errors: list[str] = []
    validator = Draft202012Validator(schema)
    for path in sorted(cases_dir.glob("*.yaml")):
        data = _load_yaml(path)
        for error in sorted(validator.iter_errors(data), key=lambda err: list(err.path)):
            location = "/".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{path}: {location}: {error.message}")
        solver = data.get("solver")
        for case in data.get("cases", []):
            case_solver = case.get("solver")
            if solver and case_solver and solver != case_solver:
                errors.append(
                    f"{path}: cases/{case.get('id', 'unknown')}: solver {case_solver} "
                    f"does not match suite solver {solver}"
                )
    return errors


def collect_cases(cases_dir: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(cases_dir.glob("*.yaml")):
        data = _load_yaml(path)
        for case in data.get("cases", []):
            case = dict(case)
            case["_suite_id"] = data.get("suite_id")
            case["_suite_solver"] = data.get("solver")
            case["_source"] = str(path)
            cases.append(case)
    return cases


def filter_cases(
    cases: list[dict[str, Any]], solver: str | None, case_ids: list[str]
) -> list[dict[str, Any]]:
    filtered = cases
    if solver:
        filtered = [case for case in filtered if case.get("solver") == solver]
    if case_ids:
        wanted = set(case_ids)
        filtered = [case for case in filtered if case.get("id") in wanted]
    return filtered


def expand_case_runs(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for case in cases:
        for size in case["scaling"]["sizes"]:
            runs.append(
                {
                    "case_id": case["id"],
                    "solver": case["solver"],
                    "case_name": case["case_name"],
                    "size_label": size["label"],
                    "grid": size["grid"],
                    "amr_levels": size["amr_levels"],
                    "source": case["_source"],
                }
            )
    return runs


def init_case_run_state(cases: list[dict[str, Any]]) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).isoformat()
    state = {
        "schema_version": 1,
        "run_id": f"run_{created_at.replace(':', '').replace('-', '')}",
        "created_at": created_at,
        "cases": {},
    }
    for case in cases:
        sizes = {}
        for size in case["scaling"]["sizes"]:
            sizes[size["label"]] = {
                "grid": size["grid"],
                "amr_levels": size["amr_levels"],
                "status": "pending",
            }
        state["cases"][case["id"]] = {
            "solver": case["solver"],
            "case_name": case["case_name"],
            "source": case["_source"],
            "status": "pending",
            "sizes": sizes,
        }
    return state


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_state(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_command(case: dict[str, Any], size: dict[str, Any]) -> str | None:
    run_info = case.get("run") or {}
    command = run_info.get("command")
    if not command:
        return None
    return command.format(
        solver=case.get("solver"),
        case_dir=case.get("case_dir"),
        inputs=case.get("inputs"),
        grid=size.get("grid"),
        label=size.get("label"),
    )


def _execute_case(case: dict[str, Any], size: dict[str, Any], dry_run: bool) -> tuple[str, str]:
    command = _format_command(case, size)
    if not command:
        return "skipped", "no command defined"
    if dry_run:
        return "planned", command

    working_dir = (case.get("run") or {}).get("working_dir") or case.get("case_dir")
    result = subprocess.run(command, shell=True, cwd=working_dir)
    if result.returncode == 0:
        return "complete", command
    return "failed", command


def run_case_suite(
    cases: list[dict[str, Any]],
    run_dir: Path,
    resume: bool,
    dry_run: bool,
) -> int:
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "run_state.json"

    if resume:
        if not state_path.exists():
            raise FileNotFoundError(f"Missing run state at {state_path}")
        state = _load_state(state_path)
    else:
        state = init_case_run_state(cases)
        _write_state(state_path, state)

    for case in cases:
        case_state = state["cases"].get(case["id"])
        if not case_state:
            continue
        for size in case["scaling"]["sizes"]:
            size_state = case_state["sizes"][size["label"]]
            if size_state["status"] == "complete":
                continue
            status, detail = _execute_case(case, size, dry_run)
            size_state["status"] = status
            size_state["detail"] = detail
            if status == "failed":
                case_state["status"] = "failed"
                _write_state(state_path, state)
                return 1
        if all(entry["status"] == "complete" for entry in case_state["sizes"].values()):
            case_state["status"] = "complete"
        elif all(entry["status"] == "skipped" for entry in case_state["sizes"].values()):
            case_state["status"] = "skipped"
        else:
            case_state["status"] = "in_progress"
        _write_state(state_path, state)

    return 0


# ===== Multi-model benchmark runner =====

def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = {**base[key], **value}
        else:
            merged[key] = value
    return merged


def _ensure_prompt_entry(entry: Any, index: int) -> dict[str, Any]:
    if isinstance(entry, str):
        return {"id": f"prompt_{index:03d}", "prompt": entry}
    if isinstance(entry, dict):
        prompt_id = entry.get("id") or f"prompt_{index:03d}"
        return {
            "id": prompt_id,
            "prompt": entry.get("prompt"),
            "prompt_path": entry.get("prompt_path"),
            "case_id": entry.get("case_id"),
            "solver": entry.get("solver"),
            "difficulty_tier": entry.get("difficulty_tier"),
            "novelty_tier": entry.get("novelty_tier"),
        }
    raise ValueError(f"Invalid prompt entry at index {index}: {entry!r}")


def _load_prompt_text(entry: dict[str, Any]) -> str | None:
    prompt = entry.get("prompt")
    if prompt:
        return str(prompt)
    prompt_path = entry.get("prompt_path")
    if prompt_path:
        path = Path(prompt_path)
        return path.read_text().strip()
    return None


def _build_config_for_model(model: dict[str, Any], output_dir: Path) -> Path | None:
    base_config = {}
    config_path = model.get("config_path")
    if config_path:
        base_config = _load_data(Path(config_path))
    overrides = model.get("overrides") or {}
    merged = _merge_dicts(base_config, overrides)
    if not merged:
        return None
    config_dir = output_dir / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    model_id = model.get("id", "model")
    model_slug = _slugify(model_id)
    config_file = config_dir / f"{model_slug}.json"
    config_file.write_text(json.dumps(merged, indent=2))
    return config_file


def _build_command(
    config_path: Path | None,
    prompt_entry: dict[str, Any],
    output_dir: Path,
    run_args: dict[str, Any],
    benchmark_context: Path | None,
) -> list[str]:
    cmd = [os.environ.get("AMREX_AGENT_PYTHON", "python"), "amrex_agent.py", "--json"]
    if prompt_entry.get("prompt"):
        cmd.extend(["--prompt", prompt_entry["prompt"]])
    elif prompt_entry.get("prompt_path"):
        cmd.extend(["--prompt-path", prompt_entry["prompt_path"]])
    else:
        raise ValueError(f"Prompt entry missing prompt text/path: {prompt_entry!r}")

    if config_path:
        cmd.extend(["--config", str(config_path)])
    cmd.extend(["--output-dir", str(output_dir)])
    if benchmark_context:
        cmd.extend(["--benchmark-context", str(benchmark_context)])

    flag_map = {
        "run_mode": "--run-mode",
        "environment": "--environment",
        "inputs_file_strategy": "--inputs-file-strategy",
        "remap_strategy": "--remap-strategy",
        "inputs_file_override": "--inputs-file-override",
        "baseline_override": "--baseline-override",
        "baseline_switch_after_retries": "--baseline-switch-after-retries",
        "llm_gate_strategy": "--llm-gate-strategy",
        "indexing_strategy": "--indexing-strategy",
        "run_ntasks": "--run-ntasks",
    }
    for key, flag in flag_map.items():
        value = run_args.get(key)
        if value is not None:
            cmd.extend([flag, str(value)])

    if run_args.get("run_serial"):
        cmd.append("--run-serial")
    if run_args.get("dry_run"):
        cmd.append("--dry-run")
    if run_args.get("preconfirm"):
        cmd.append("--preconfirm")
    if run_args.get("save_workflow"):
        cmd.append("--save-workflow")
    if run_args.get("save_transcript"):
        cmd.append("--save-transcript")
    if run_args.get("save_log"):
        cmd.append("--save-log")
    if run_args.get("verbose"):
        cmd.append("--verbose")

    extra_args = run_args.get("extra_args") or []
    if extra_args:
        cmd.extend([str(arg) for arg in extra_args])

    return cmd


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_violations(payload: dict[str, Any], graph_state: dict[str, Any]) -> list[dict[str, Any]]:
    review_analysis = payload.get("review_analysis")
    if not isinstance(review_analysis, dict):
        review_analysis = graph_state.get("review_analysis")
    if not isinstance(review_analysis, dict):
        return []
    violations = review_analysis.get("violations")
    if not isinstance(violations, list):
        return []
    return [item for item in violations if isinstance(item, dict)]


def _derive_validation_fields(payload: dict[str, Any], graph_state: dict[str, Any]) -> dict[str, Any]:
    violations = _extract_violations(payload, graph_state)
    schema_errors = [v.get("message") for v in violations if "schema" in str(v.get("rule_name", "")).lower()]
    schema_errors = [msg for msg in schema_errors if isinstance(msg, str) and msg]

    physics_warnings = [
        v.get("message")
        for v in violations
        if "physics" in str(v.get("rule_name", "")).lower()
        and str(v.get("severity", "")).lower() == "warning"
        and isinstance(v.get("message"), str)
    ]

    has_physics_error = any(
        "physics" in str(v.get("rule_name", "")).lower()
        and str(v.get("severity", "error")).lower() == "error"
        for v in violations
    )
    has_resource_error = any(
        (
            "resource" in str(v.get("rule_name", "")).lower()
            or "build" in str(v.get("rule_name", "")).lower()
        )
        and str(v.get("severity", "error")).lower() == "error"
        for v in violations
    )

    schema_valid = payload.get("schema_valid")
    if not isinstance(schema_valid, bool):
        schema_valid = len(schema_errors) == 0 if violations else False

    physics_valid = payload.get("physics_valid")
    if not isinstance(physics_valid, bool):
        physics_valid = (not has_physics_error) if violations else False

    resource_valid = payload.get("resource_valid")
    if not isinstance(resource_valid, bool):
        resource_valid = (not has_resource_error) if violations else False

    if schema_valid and not schema_errors:
        schema_errors = []

    return {
        "schema_valid": schema_valid,
        "physics_valid": physics_valid,
        "resource_valid": resource_valid,
        "schema_errors": schema_errors,
        "physics_warnings": physics_warnings or [],
    }


def _derive_iteration_fields(payload: dict[str, Any], graph_state: dict[str, Any]) -> dict[str, Any]:
    iteration_count = _as_int(payload.get("iteration_count"))
    if iteration_count is None:
        iteration_count = _as_int(payload.get("iteration"))
    if iteration_count is None:
        iteration_count = _as_int(graph_state.get("iteration"))

    reviewer_retry_count = _as_int(payload.get("reviewer_retry_count"))
    if reviewer_retry_count is None:
        reviewer_retry_count = _as_int(payload.get("retry_count"))
    if reviewer_retry_count is None:
        reviewer_retry_count = _as_int(graph_state.get("retry_count"))

    out: dict[str, Any] = {
        "iteration_count": iteration_count,
        "reviewer_retry_count": reviewer_retry_count,
    }
    if iteration_count is None:
        out["iteration_count_unavailable_reason"] = "graph_state.iteration_missing"
    if reviewer_retry_count is None:
        out["reviewer_retry_count_unavailable_reason"] = "graph_state.retry_count_missing"
    return out


def _derive_benchmark_metrics_fields(payload: dict[str, Any], graph_state: dict[str, Any]) -> dict[str, Any]:
    wall_time_seconds = _as_float(payload.get("wall_time_seconds"))
    if wall_time_seconds is None:
        wall_time_seconds = _as_float(payload.get("duration_seconds"))
    if wall_time_seconds is None:
        wall_time_seconds = _as_float(graph_state.get("wall_time_seconds"))
    if wall_time_seconds is None:
        wall_time_seconds = _as_float(graph_state.get("duration_seconds"))
    if wall_time_seconds is None:
        wall_time_seconds = 0.0

    architect_time_seconds = _as_float(payload.get("architect_time_seconds"))
    if architect_time_seconds is None:
        architect_time_seconds = _as_float(graph_state.get("architect_time_seconds"))
    if architect_time_seconds is None:
        architect_time_seconds = 0.0

    llm_call_count = _as_int(payload.get("llm_call_count"))
    if llm_call_count is None:
        llm_total = (((graph_state.get("metrics") or {}).get("stages") or {}).get("architect") or {}).get("llm")
        llm_call_count = _as_int((llm_total or {}).get("total_calls"))
    if llm_call_count is None:
        llm_call_count = 0

    converged = payload.get("converged")
    if not isinstance(converged, bool):
        status = str(payload.get("analysis_status") or graph_state.get("job_status") or "").lower()
        converged = status in {"success", "completed"}

    return {
        "converged": converged,
        "wall_time_seconds": wall_time_seconds,
        "architect_time_seconds": architect_time_seconds,
        "llm_call_count": llm_call_count,
    }


def _derive_gate_approval_fields(payload: dict[str, Any], graph_state: dict[str, Any]) -> dict[str, Any]:
    gate_approvals = payload.get("gate_approvals")
    if gate_approvals is None:
        gate_approvals = graph_state.get("gate_approvals", [])
    if not isinstance(gate_approvals, list):
        gate_approvals = []

    return {
        "gate_approval_count": len(gate_approvals),
        "gate_approvals": gate_approvals,
    }


def _is_non_empty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return value is not None


def _extract_migration_candidates(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = [manifest]
    migration_plan = manifest.get("migration_plan")
    if isinstance(migration_plan, dict):
        candidates.append(migration_plan)

    sessions = manifest.get("sessions")
    if isinstance(sessions, dict):
        for key in ("unnumbered_161", "migration_plan", "db_migration"):
            entry = sessions.get(key)
            if isinstance(entry, dict):
                candidates.append(entry)
    return candidates


def _migration_mapping_and_rollback_flags(manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    mapping_any = False
    rollback_any = False
    ready_any = False
    for candidate in _extract_migration_candidates(manifest):
        has_mapping = any(
            _is_non_empty(candidate.get(key))
            for key in ("schema_mapping", "schema_map", "field_mapping", "table_mapping")
        )
        has_rollback = any(
            _is_non_empty(candidate.get(key))
            for key in ("rollback", "rollback_plan", "rollback_steps", "rollback_sql")
        )
        mapping_any = mapping_any or has_mapping
        rollback_any = rollback_any or has_rollback
        ready_any = ready_any or (has_mapping and has_rollback)
    return mapping_any, rollback_any, ready_any


def has_migration_plan_schema_mapping_and_rollback(context: dict[str, Any]) -> bool:
    """
    Return True when validation_manifest contains both mapping and rollback artifacts.
    """
    manifest = context.get("validation_manifest")
    if not isinstance(manifest, dict):
        return False
    _, _, ready = _migration_mapping_and_rollback_flags(manifest)
    return ready


def _derive_migration_plan_fields(payload: dict[str, Any], graph_state: dict[str, Any]) -> dict[str, Any]:
    manifest = payload.get("validation_manifest")
    if not isinstance(manifest, dict):
        manifest = graph_state.get("validation_manifest")
    if not isinstance(manifest, dict):
        return {
            "migration_plan_schema_mapping_present": False,
            "migration_plan_rollback_present": False,
            "migration_plan_ready": False,
        }
    mapping_present, rollback_present, ready = _migration_mapping_and_rollback_flags(manifest)
    return {
        "migration_plan_schema_mapping_present": mapping_present,
        "migration_plan_rollback_present": rollback_present,
        "migration_plan_ready": ready,
    }


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _split_mapping_values(value: Any) -> list[str]:
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, str):
        candidates = re.split(r"[,;\n]", value)
    elif value is None:
        candidates = []
    else:
        candidates = [value]

    return [str(item).strip() for item in candidates if str(item).strip()]


def _classify_mapping_path(path: str) -> str:
    lowered = path.lower()
    if "fixture" in lowered or lowered.endswith((".json", ".yaml", ".yml")):
        return "fixture"
    return "test"


def _normalize_feature_mapping_entries(entries: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        feature_id = f"F-{index:03d}"
        feature_label = f"feature_{index:03d}"
        tests: list[str] = []
        fixtures: list[str] = []

        if isinstance(entry, dict):
            feature_id = str(entry.get("feature_id") or entry.get("id") or feature_id)
            feature_label = str(entry.get("feature_label") or entry.get("title") or feature_label)
            tests = _split_mapping_values(entry.get("tests") or entry.get("test_files"))
            fixtures = _split_mapping_values(entry.get("fixtures") or entry.get("fixture_files"))
            if not tests and not fixtures:
                combined = _split_mapping_values(entry.get("tests_fixtures"))
                for candidate in combined:
                    if _classify_mapping_path(candidate) == "fixture":
                        fixtures.append(candidate)
                    else:
                        tests.append(candidate)
        elif isinstance(entry, str):
            feature_label = entry

        normalized.append(
            {
                "feature_id": feature_id,
                "feature_label": feature_label,
                "tests": tests,
                "fixtures": fixtures,
                "mapping_complete": bool(tests) and bool(fixtures),
            }
        )
    return normalized


def _parse_feature_mapping_from_markdown(markdown: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        header_match = _FEATURE_BLOCK_HEADER_RE.match(line)
        if header_match:
            if current is not None:
                current["mapping_complete"] = bool(current["tests"]) and bool(current["fixtures"])
                entries.append(current)
            current = {
                "feature_id": header_match.group(1).strip(),
                "feature_label": line,
                "tests": [],
                "fixtures": [],
                "mapping_complete": False,
            }
            continue
        if current is None:
            continue
        mapping_match = _TESTS_FIXTURES_LINE_RE.match(line)
        if not mapping_match:
            continue
        for candidate in _split_mapping_values(mapping_match.group(1)):
            if _classify_mapping_path(candidate) == "fixture":
                current["fixtures"].append(candidate)
            else:
                current["tests"].append(candidate)

    if current is not None:
        current["mapping_complete"] = bool(current["tests"]) and bool(current["fixtures"])
        entries.append(current)

    return entries


def _derive_claim_evidence_fields(payload: dict[str, Any], graph_state: dict[str, Any]) -> dict[str, Any]:
    claims = _as_list(payload.get("claims") or graph_state.get("claims"))
    evidence = _as_list(payload.get("evidence") or graph_state.get("evidence"))
    raw_matrix = _as_list(payload.get("claim_evidence_matrix") or graph_state.get("claim_evidence_matrix"))

    matrix: list[dict[str, Any]] = []
    if raw_matrix:
        for idx, row in enumerate(raw_matrix, start=1):
            if not isinstance(row, dict):
                continue
            claim_id = row.get("claim_id") or f"claim_{idx:03d}"
            evidence_refs = _as_list(row.get("evidence_refs"))
            matrix.append(
                {
                    "claim_id": str(claim_id),
                    "claim": row.get("claim") or row.get("text") or "",
                    "evidence_refs": [str(ref) for ref in evidence_refs if ref is not None],
                    "covered": bool(evidence_refs),
                }
            )
    else:
        for idx, claim in enumerate(claims, start=1):
            claim_id = f"claim_{idx:03d}"
            claim_text = claim
            evidence_refs: list[str] = []
            if isinstance(claim, dict):
                claim_id = str(claim.get("id") or claim_id)
                claim_text = claim.get("claim") or claim.get("text") or ""
                evidence_refs = [str(ref) for ref in _as_list(claim.get("evidence_refs")) if ref is not None]
            matrix.append(
                {
                    "claim_id": claim_id,
                    "claim": str(claim_text or ""),
                    "evidence_refs": evidence_refs,
                    "covered": bool(evidence_refs),
                }
            )

    claim_count = len(matrix)
    covered_claim_count = sum(1 for row in matrix if row["covered"])
    uncovered_claim_ids = [row["claim_id"] for row in matrix if not row["covered"]]
    status = "missing"
    if claim_count > 0:
        status = "complete" if covered_claim_count == claim_count else "partial"

    return {
        "claim_evidence_matrix": matrix,
        "claim_count": claim_count,
        "evidence_count": len(evidence),
        "covered_claim_count": covered_claim_count,
        "uncovered_claim_ids": uncovered_claim_ids,
        "claim_evidence_matrix_status": status,
    }


def _derive_uc_summary_traceability_fields(
    payload: dict[str, Any],
    graph_state: dict[str, Any],
) -> dict[str, Any]:
    raw_entries = (
        payload.get("uc_summary_entries")
        or payload.get("uc_summary")
        or graph_state.get("uc_summary_entries")
        or graph_state.get("uc_summary")
    )
    entries = _as_list(raw_entries)

    normalized_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        uc_id = f"uc_{index:03d}"
        summary = ""
        artifacts: list[str] = []

        if isinstance(entry, dict):
            uc_id = str(
                entry.get("uc_id")
                or entry.get("use_case_id")
                or entry.get("id")
                or entry.get("case_id")
                or uc_id
            )
            summary = str(
                entry.get("summary")
                or entry.get("use_case_summary")
                or entry.get("description")
                or ""
            )
            artifact_candidates = (
                _as_list(entry.get("artifacts"))
                + _as_list(entry.get("artifact_refs"))
                + _as_list(entry.get("traceability_artifacts"))
                + _as_list(entry.get("tests"))
                + _as_list(entry.get("fixtures"))
                + _as_list(entry.get("benchmarks"))
            )
            artifacts = [
                str(item).strip()
                for item in artifact_candidates
                if str(item).strip()
            ]
        else:
            summary = str(entry or "")

        normalized_entries.append(
            {
                "uc_id": uc_id,
                "summary": summary,
                "artifacts": artifacts,
                "traceable": bool(artifacts),
            }
        )

    uc_summary_count = len(normalized_entries)
    traceable_count = sum(1 for entry in normalized_entries if entry["traceable"])
    untraceable_ids = [
        str(entry["uc_id"])
        for entry in normalized_entries
        if not entry["traceable"]
    ]

    status = "missing"
    if uc_summary_count:
        status = "complete" if traceable_count == uc_summary_count else "partial"

    return {
        "uc_summary_entries": normalized_entries,
        "uc_summary_count": uc_summary_count,
        "uc_summary_traceable_count": traceable_count,
        "uc_summary_untraceable_ids": untraceable_ids,
        "uc_summary_traceability_status": status,
    }


def _derive_feature_fixture_mapping_fields(
    payload: dict[str, Any],
    graph_state: dict[str, Any],
) -> dict[str, Any]:
    raw_entries = payload.get("feature_test_fixture_mapping")
    if raw_entries is None:
        raw_entries = graph_state.get("feature_test_fixture_mapping")

    mapping_entries: list[dict[str, Any]] = []
    if raw_entries is not None:
        mapping_entries = _normalize_feature_mapping_entries(_as_list(raw_entries))
    else:
        markdown = payload.get("feature_blocks_markdown")
        if not isinstance(markdown, str):
            markdown = graph_state.get("feature_blocks_markdown")
        if isinstance(markdown, str):
            mapping_entries = _parse_feature_mapping_from_markdown(markdown)

    total_features = len(mapping_entries)
    complete_features = sum(1 for entry in mapping_entries if entry["mapping_complete"])
    missing_features = [
        entry["feature_label"]
        for entry in mapping_entries
        if not entry["mapping_complete"]
    ]

    status = "missing"
    if total_features:
        status = "complete" if complete_features == total_features else "partial"

    return {
        "feature_test_fixture_mapping": mapping_entries,
        "feature_test_fixture_mapping_count": total_features,
        "feature_test_fixture_mapping_complete_count": complete_features,
        "feature_test_fixture_mapping_missing": missing_features,
        "feature_test_fixture_mapping_complete": total_features > 0 and complete_features == total_features,
        "feature_test_fixture_mapping_status": status,
    }


def _derive_reproducibility_oracle_fields(
    payload: dict[str, Any],
    graph_state: dict[str, Any],
) -> dict[str, Any]:
    enabled = bool(
        payload.get("reproducibility_oracle_enabled")
        or graph_state.get("reproducibility_oracle_enabled")
    )
    seed = _normalize_reproducibility_seed(
        _first_non_none(
            payload.get("seed"),
            payload.get("reproducibility_seed"),
            graph_state.get("seed"),
            graph_state.get("reproducibility_seed"),
        )
    )

    if not enabled and seed is None:
        return {
            "reproducibility_oracle_enabled": False,
            "reproducibility_oracle_seed": None,
            "reproducibility_oracle_digest": None,
            "reproducibility_oracle_valid": True,
            "reproducibility_oracle_reason": None,
        }

    if seed is None:
        return {
            "reproducibility_oracle_enabled": True,
            "reproducibility_oracle_seed": None,
            "reproducibility_oracle_digest": None,
            "reproducibility_oracle_valid": False,
            "reproducibility_oracle_reason": "seed_missing",
        }

    oracle_payload = payload.get("reproducibility_oracle_payload")
    if not isinstance(oracle_payload, dict):
        oracle_payload = graph_state if graph_state else payload
    digest = _build_reproducibility_oracle_digest(seed, oracle_payload)

    expected_digest = payload.get("reproducibility_oracle_expected_digest")
    if not isinstance(expected_digest, str):
        expected_digest = graph_state.get("reproducibility_oracle_expected_digest")
    expected_digest = expected_digest.strip() if isinstance(expected_digest, str) else None

    valid = True
    reason = None
    if expected_digest and expected_digest != digest:
        valid = False
        reason = "seed_locked_oracle_mismatch"

    return {
        "reproducibility_oracle_enabled": True,
        "reproducibility_oracle_seed": seed,
        "reproducibility_oracle_digest": digest,
        "reproducibility_oracle_expected_digest": expected_digest,
        "reproducibility_oracle_valid": valid,
        "reproducibility_oracle_reason": reason,
    }


def _normalize_benchmark_record(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    graph_state = normalized.pop("__graph_state", None)
    if not isinstance(graph_state, dict):
        graph_state = {}

    normalized.update(_derive_validation_fields(normalized, graph_state))
    normalized.update(_derive_iteration_fields(normalized, graph_state))
    normalized.update(_derive_benchmark_metrics_fields(normalized, graph_state))
    normalized.update(_derive_gate_approval_fields(normalized, graph_state))
    normalized.update(_derive_migration_plan_fields(normalized, graph_state))
    normalized.update(_derive_claim_evidence_fields(normalized, graph_state))
    normalized.update(_derive_uc_summary_traceability_fields(normalized, graph_state))
    normalized.update(_derive_feature_fixture_mapping_fields(normalized, graph_state))
    normalized.update(_derive_reproducibility_oracle_fields(normalized, graph_state))
    return normalized


def _write_jsonl(path: Path, payload: dict[str, Any], config: Any | None = None) -> dict[str, Any]:
    payload = _normalize_benchmark_record(payload)
    with path.open("a", encoding="utf-8") as handle:
        if config is not None:
            from src.utils.privacy import sanitize_payload

            payload = sanitize_payload(payload, config=config)
        handle.write(json.dumps(payload, default=str))
        handle.write("\n")
    return payload


def _build_claim_evidence_coverage_matrix(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_claims = sum(int(record.get("claim_count", 0) or 0) for record in records)
    total_covered = sum(int(record.get("covered_claim_count", 0) or 0) for record in records)
    coverage_ratio = (float(total_covered) / float(total_claims)) if total_claims else 0.0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(records),
        "total_claims": total_claims,
        "total_covered_claims": total_covered,
        "coverage_ratio": coverage_ratio,
        "records": records,
    }


def _build_uc_summary_traceability_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_uc_summaries = sum(int(record.get("uc_summary_count", 0) or 0) for record in records)
    total_traceable = sum(int(record.get("uc_summary_traceable_count", 0) or 0) for record in records)
    coverage_ratio = (float(total_traceable) / float(total_uc_summaries)) if total_uc_summaries else 0.0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(records),
        "total_uc_summaries": total_uc_summaries,
        "total_traceable_uc_summaries": total_traceable,
        "coverage_ratio": coverage_ratio,
        "records": records,
    }


def _privacy_config(run_args: dict[str, Any]) -> Any | None:
    mode = run_args.get("privacy_mode")
    if not mode:
        return None
    return SimpleNamespace(
        privacy_mode=mode,
        privacy_scrubber=run_args.get("privacy_scrubber", "builtin"),
        privacy_hash_salt=run_args.get("privacy_hash_salt"),
    )


def _slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def _build_determinism_controls(run_args: dict[str, Any], config_path: Path) -> dict[str, Any]:
    seed = run_args.get("seed", run_args.get("deterministic_seed", DEFAULT_BENCHMARK_SEED))
    try:
        deterministic_seed = int(seed)
    except (TypeError, ValueError) as exc:
        raise ValueError("run_args.seed must be an integer for deterministic benchmark runs.") from exc

    enforce_replay = run_args.get("enforce_replay", run_args.get("deterministic_replay", True))
    if enforce_replay is False:
        raise ValueError("run_args.enforce_replay cannot be false for deterministic benchmark runs.")

    replay_basis = {
        "benchmark_config": str(config_path),
        "run_args": run_args,
        "seed": deterministic_seed,
    }
    replay_fingerprint = hashlib.sha256(
        json.dumps(replay_basis, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return {
        "seed": deterministic_seed,
        "enforce_replay": True,
        "replay_fingerprint": replay_fingerprint,
    }


def _deterministic_env_overrides(controls: dict[str, Any]) -> dict[str, str]:
    seed = str(controls["seed"])
    return {
        "PYTHONHASHSEED": seed,
        "AMREX_AGENT_BENCHMARK_SEED": seed,
        "AMREX_AGENT_DETERMINISTIC_REPLAY": "1",
        "AMREX_AGENT_REPLAY_FINGERPRINT": str(controls["replay_fingerprint"]),
    }


def run_model_benchmark(config_path: Path, output_dir: Path, run_name: str | None) -> dict[str, Any]:
    bench_config = _load_data(config_path)

    prompts_raw = bench_config.get("prompts") or []
    if not prompts_raw:
        raise ValueError("Benchmark config must include prompts.")
    models = bench_config.get("models") or []
    if not models:
        raise ValueError("Benchmark config must include models.")

    run_args = bench_config.get("run_args") or {}
    env_common = bench_config.get("env") or {}
    privacy_config = _privacy_config(run_args)
    determinism_controls = _build_determinism_controls(run_args, config_path)
    deterministic_env = _deterministic_env_overrides(determinism_controls)

    run_name = run_name or datetime.now().strftime("bench_%Y%m%d_%H%M%S")
    run_dir = output_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = run_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_name": run_name,
        "created_at": datetime.now().isoformat(),
        "benchmark_config": str(config_path),
        "models": [],
        "prompts": [],
        "run_args": run_args,
        "env_keys": sorted(set(env_common.keys())),
        "determinism": {
            "seed": determinism_controls["seed"],
            "enforce_replay": determinism_controls["enforce_replay"],
            "replay_fingerprint": determinism_controls["replay_fingerprint"],
            "replay_manifest": "replay_manifest.json",
        },
    }
    replay_manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_name": run_name,
        "benchmark_config": str(config_path),
        "seed": determinism_controls["seed"],
        "enforce_replay": determinism_controls["enforce_replay"],
        "replay_fingerprint": determinism_controls["replay_fingerprint"],
        "planned_runs": [],
        "runs": [],
    }

    prompt_entries = []
    for idx, entry in enumerate(prompts_raw, start=1):
        normalized = _ensure_prompt_entry(entry, idx)
        prompt_text = _load_prompt_text(normalized)
        if not prompt_text:
            raise ValueError(f"Prompt entry missing text/path: {normalized!r}")
        prompt_entries.append({**normalized, "prompt": prompt_text})
        prompt_manifest = {
            "id": normalized["id"],
            "prompt_path": normalized.get("prompt_path"),
            "prompt_excerpt": prompt_text[:160],
        }
        if privacy_config is not None:
            from src.utils.privacy import sanitize_payload

            prompt_manifest = sanitize_payload(prompt_manifest, config=privacy_config)
        manifest["prompts"].append(prompt_manifest)

    raw_metrics_path = run_dir / "benchmark_runs.jsonl"
    matrix_records: list[dict[str, Any]] = []
    uc_traceability_records: list[dict[str, Any]] = []

    for model in models:
        model_id = model.get("id")
        if not model_id:
            raise ValueError("Each model must include an id.")
        model_slug = _slugify(model_id)
        model_env = dict(env_common)
        model_env.update(model.get("env") or {})
        provider = (model.get("overrides") or {}).get("llm_provider")

        model_config_path = _build_config_for_model(model, run_dir)
        model_manifest = {
            "id": model_id,
            "slug": model_slug,
            "config_path": str(model_config_path) if model_config_path else None,
            "config_source": model.get("config_path"),
            "override_keys": sorted((model.get("overrides") or {}).keys()),
            "env_keys": sorted((model.get("env") or {}).keys()),
        }
        if privacy_config is not None:
            from src.utils.privacy import sanitize_payload

            model_manifest = sanitize_payload(model_manifest, config=privacy_config)
        manifest["models"].append(model_manifest)

        for prompt in prompt_entries:
            prompt_id = prompt["id"]
            prompt_dir = runs_dir / model_slug / prompt_id
            prompt_dir.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env.update({k: str(v) for k, v in model_env.items()})
            env.update(deterministic_env)
            benchmark_context = prompt_dir / "benchmark_context.json"
            context_payload = {
                "prompt_id": prompt_id,
                "prompt_excerpt": prompt["prompt"][:160],
                "case_id": prompt.get("case_id"),
                "solver": prompt.get("solver"),
                "difficulty_tier": prompt.get("difficulty_tier"),
                "novelty_tier": prompt.get("novelty_tier"),
                "model_id": model_id,
                "provider": provider,
                "deterministic_seed": determinism_controls["seed"],
                "replay_fingerprint": determinism_controls["replay_fingerprint"],
            }
            if privacy_config is not None:
                from src.utils.privacy import sanitize_payload

                context_payload = sanitize_payload(context_payload, config=privacy_config)
            benchmark_context.write_text(json.dumps(context_payload, indent=2, default=str))

            cmd = _build_command(model_config_path, prompt, prompt_dir, run_args, benchmark_context)
            replay_command = cmd if privacy_config is None else "[REDACTED]"
            replay_manifest["planned_runs"].append(
                {
                    "model_id": model_id,
                    "prompt_id": prompt_id,
                    "command": replay_command,
                    "output_dir": str(prompt_dir),
                }
            )
            replay_manifest["runs"].append(
                {
                    "model_id": model_id,
                    "prompt_id": prompt_id,
                    "command": replay_command,
                    "output_dir": str(prompt_dir),
                }
            )

            started_at = datetime.now().isoformat()
            start_time = time.time()
            result_data: dict[str, Any] | None = None
            error = None
            exit_code = None
            stdout = ""
            stderr = ""
            try:
                timeout = run_args.get("timeout_seconds")
                proc = subprocess.run(
                    cmd,
                    cwd=Path(__file__).resolve().parents[1],
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=timeout,
                )
                exit_code = proc.returncode
                stdout = proc.stdout
                stderr = proc.stderr
                if stdout.strip():
                    result_data = json.loads(stdout)
            except subprocess.TimeoutExpired as exc:
                error = f"timeout_after_{exc.timeout}s"
                stdout = exc.stdout or ""
                stderr = exc.stderr or ""
            except json.JSONDecodeError as exc:
                error = f"json_parse_failed: {exc}"
            except Exception as exc:
                error = f"runner_error: {exc}"

            ended_at = datetime.now().isoformat()
            duration = time.time() - start_time

            analysis_report = None
            run_directory = None
            job_status = None
            selected_case = None
            if result_data:
                run_directory = result_data.get("run_directory")
                job_status = normalize_job_status(
                    result_data.get("job_status"),
                    default="unknown",
                )
                selected_case = result_data.get("selected_case")
                analysis_report = result_data.get("analysis_report")

            if not analysis_report and run_directory:
                report_path = Path(run_directory) / "analysis_report.json"
                if report_path.exists():
                    try:
                        analysis_report = json.loads(report_path.read_text())
                    except Exception:
                        analysis_report = None

            record = {
                "model_id": model_id,
                "prompt_id": prompt_id,
                "prompt_excerpt": prompt["prompt"][:200],
                "job_status": normalize_job_status(job_status, default="unknown"),
                "analysis_status": (analysis_report or {}).get("status"),
                "analysis_performance": (analysis_report or {}).get("performance"),
                "analysis_issues": (analysis_report or {}).get("issues"),
                "run_directory": run_directory,
                "selected_case": selected_case,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": duration,
                "exit_code": exit_code,
                "error": error,
                "stderr_excerpt": stderr[:2000] if stderr else None,
                "deterministic_seed": determinism_controls["seed"],
                "replay_fingerprint": determinism_controls["replay_fingerprint"],
                "__graph_state": result_data,
            }
            normalized_record = _write_jsonl(raw_metrics_path, record, config=privacy_config)
            matrix_records.append(
                {
                    "model_id": normalized_record.get("model_id"),
                    "prompt_id": normalized_record.get("prompt_id"),
                    "claim_count": normalized_record.get("claim_count", 0),
                    "covered_claim_count": normalized_record.get("covered_claim_count", 0),
                    "claim_evidence_matrix_status": normalized_record.get("claim_evidence_matrix_status"),
                    "uncovered_claim_ids": normalized_record.get("uncovered_claim_ids", []),
                    "claim_evidence_matrix": normalized_record.get("claim_evidence_matrix", []),
                }
            )
            uc_traceability_records.append(
                {
                    "model_id": normalized_record.get("model_id"),
                    "prompt_id": normalized_record.get("prompt_id"),
                    "uc_summary_count": normalized_record.get("uc_summary_count", 0),
                    "uc_summary_traceable_count": normalized_record.get("uc_summary_traceable_count", 0),
                    "uc_summary_traceability_status": normalized_record.get("uc_summary_traceability_status"),
                    "uc_summary_untraceable_ids": normalized_record.get("uc_summary_untraceable_ids", []),
                    "uc_summary_entries": normalized_record.get("uc_summary_entries", []),
                }
            )

            per_run = prompt_dir / "result.json"
            per_run_payload = {
                "command": cmd,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "result": result_data,
                "record": record,
            }
            if privacy_config is not None:
                from src.utils.privacy import sanitize_payload

                per_run_payload = sanitize_payload(per_run_payload, config=privacy_config)
            per_run.write_text(json.dumps(per_run_payload, indent=2, default=str))

    if privacy_config is not None:
        from src.utils.privacy import sanitize_payload

        manifest = sanitize_payload(manifest, config=privacy_config)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (run_dir / "replay_manifest.json").write_text(json.dumps(replay_manifest, indent=2))
    (run_dir / "claim_evidence_coverage_matrix.json").write_text(
        json.dumps(_build_claim_evidence_coverage_matrix(matrix_records), indent=2)
    )
    (run_dir / "uc_summary_traceability.json").write_text(
        json.dumps(_build_uc_summary_traceability_report(uc_traceability_records), indent=2)
    )
    return {"run_dir": str(run_dir), "metrics": str(raw_metrics_path)}
