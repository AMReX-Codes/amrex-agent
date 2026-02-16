#!/usr/bin/env python3
"""Benchmark runner scaffold for scaling case suites."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


DEFAULT_SCHEMA = Path("benchmark/specs/case_schema.yaml")
DEFAULT_CASES_DIR = Path("benchmark/cases")
DEFAULT_RUNS_DIR = Path("benchmark/runs")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_schema(schema_path: Path) -> dict[str, Any]:
    return _load_yaml(schema_path)


def _iter_case_files(cases_dir: Path) -> list[Path]:
    return sorted(cases_dir.glob("*.yaml"))


def _validate_file(data: dict[str, Any], schema: dict[str, Any], path: Path) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = []
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


def _collect_cases(cases_dir: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in _iter_case_files(cases_dir):
        data = _load_yaml(path)
        for case in data.get("cases", []):
            case = dict(case)
            case["_suite_id"] = data.get("suite_id")
            case["_suite_solver"] = data.get("solver")
            case["_source"] = str(path)
            cases.append(case)
    return cases


def _filter_cases(
    cases: list[dict[str, Any]], solver: str | None, case_ids: list[str]
) -> list[dict[str, Any]]:
    filtered = cases
    if solver:
        filtered = [case for case in filtered if case.get("solver") == solver]
    if case_ids:
        wanted = set(case_ids)
        filtered = [case for case in filtered if case.get("id") in wanted]
    return filtered


def _expand_case_runs(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _check_unique_ids(cases: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, str] = {}
    errors = []
    for case in cases:
        case_id = case.get("id")
        if not case_id:
            continue
        source = case.get("_source", "<unknown>")
        if case_id in seen:
            errors.append(f"Duplicate case id {case_id} in {source} (also {seen[case_id]})")
        else:
            seen[case_id] = source
    return errors


def _print_cases(cases: list[dict[str, Any]]) -> None:
    for case in cases:
        print(f"{case['id']}: {case['solver']} - {case['case_name']}")


def _print_plan(runs: list[dict[str, Any]]) -> None:
    for run in runs:
        print(
            f"{run['case_id']} [{run['size_label']}] "
            f"grid={run['grid']} amr={run['amr_levels']}"
        )


def _init_run_state(cases: list[dict[str, Any]]) -> dict[str, Any]:
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
    import subprocess  # Imported lazily to keep startup fast.

    working_dir = (case.get("run") or {}).get("working_dir") or case.get("case_dir")
    result = subprocess.run(command, shell=True, cwd=working_dir)
    if result.returncode == 0:
        return "complete", command
    return "failed", command


def _run_cases(
    cases: list[dict[str, Any]],
    run_dir: Path,
    resume: bool,
    dry_run: bool,
) -> int:
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "run_state.json"

    if resume:
        if not state_path.exists():
            print(f"Missing run state at {state_path}", file=sys.stderr)
            return 2
        state = _load_state(state_path)
    else:
        state = _init_run_state(cases)
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
                print(f"Failed: {case['id']} [{size['label']}]", file=sys.stderr)
                return 1
        if all(entry["status"] == "complete" for entry in case_state["sizes"].values()):
            case_state["status"] = "complete"
        elif all(entry["status"] == "skipped" for entry in case_state["sizes"].values()):
            case_state["status"] = "skipped"
        else:
            case_state["status"] = "in_progress"
        _write_state(state_path, state)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaling benchmark runner scaffold")
    parser.add_argument("--cases-dir", type=Path, default=DEFAULT_CASES_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--solver", choices=["PeleC", "PeleLMeX", "ERF", "REMORA"])
    parser.add_argument("--case-id", action="append", default=[])

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List benchmark cases")
    subparsers.add_parser("validate", help="Validate benchmark case files")
    subparsers.add_parser("plan", help="Print expanded run plan")

    run_parser = subparsers.add_parser("run", help="Execute benchmark cases (stub)")
    run_parser.add_argument("--run-dir", type=Path, default=None)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--execute", action="store_true")

    args = parser.parse_args()

    cases_dir = args.cases_dir
    schema = _load_schema(args.schema)

    if args.command == "validate":
        errors: list[str] = []
        for path in _iter_case_files(cases_dir):
            data = _load_yaml(path)
            errors.extend(_validate_file(data, schema, path))
        cases = _collect_cases(cases_dir)
        errors.extend(_check_unique_ids(cases))
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("All benchmark case files are valid.")
        return 0

    cases = _collect_cases(cases_dir)
    cases = _filter_cases(cases, args.solver, args.case_id)

    if args.command == "list":
        _print_cases(cases)
        return 0

    if args.command == "plan":
        runs = _expand_case_runs(cases)
        _print_plan(runs)
        return 0

    if args.command == "run":
        run_dir = args.run_dir
        if run_dir is None:
            run_dir = DEFAULT_RUNS_DIR / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dry_run = not args.execute
        return _run_cases(cases, run_dir, args.resume, dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
