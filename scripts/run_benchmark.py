#!/usr/bin/env python3
"""Run benchmark suites (case grids or multi-model prompt runs)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from src.benchmark_runner import (
    collect_cases,
    expand_case_runs,
    filter_cases,
    run_case_suite,
    run_model_benchmark,
    validate_case_files,
)


DEFAULT_SCHEMA = Path("benchmark/specs/case_schema.yaml")
DEFAULT_CASES_DIR = Path("benchmark/cases")
DEFAULT_RUNS_DIR = Path("benchmark/runs")


def _print_cases(cases: list[dict]) -> None:
    for case in cases:
        print(f"{case['id']}: {case['solver']} - {case['case_name']}")


def _print_plan(runs: list[dict]) -> None:
    for run in runs:
        print(
            f"{run['case_id']} [{run['size_label']}] "
            f"grid={run['grid']} amr={run['amr_levels']}"
        )


def _cases_parser(subparsers: argparse._SubParsersAction) -> None:
    cases_parser = subparsers.add_parser("cases", help="Operate on benchmark case suites")
    cases_parser.add_argument("--cases-dir", type=Path, default=DEFAULT_CASES_DIR)
    cases_parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    cases_parser.add_argument("--solver", choices=["PeleC", "PeleLMeX", "ERF", "REMORA"])
    cases_parser.add_argument("--case-id", action="append", default=[])

    case_sub = cases_parser.add_subparsers(dest="command", required=True)
    case_sub.add_parser("list", help="List benchmark cases")
    case_sub.add_parser("validate", help="Validate benchmark case files")
    case_sub.add_parser("plan", help="Print expanded run plan")

    run_parser = case_sub.add_parser("run", help="Execute benchmark cases (stub)")
    run_parser.add_argument("--run-dir", type=Path, default=None)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--execute", action="store_true")


def _models_parser(subparsers: argparse._SubParsersAction) -> None:
    model_parser = subparsers.add_parser("models", help="Run multi-model prompt benchmarks")
    model_parser.add_argument("--config", required=True, help="Benchmark config file (json/yaml).")
    model_parser.add_argument(
        "--output-dir",
        default="output/benchmarks",
        help="Base output directory for benchmark artifacts.",
    )
    model_parser.add_argument("--run-name", default=None, help="Optional run name override.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark runner")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    _cases_parser(subparsers)
    _models_parser(subparsers)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.mode == "cases":
        if args.command == "validate":
            errors = validate_case_files(args.schema, args.cases_dir)
            if errors:
                for error in errors:
                    print(error)
                return 1
            print("All benchmark case files are valid.")
            return 0

        cases = collect_cases(args.cases_dir)
        cases = filter_cases(cases, args.solver, args.case_id)

        if args.command == "list":
            _print_cases(cases)
            return 0

        if args.command == "plan":
            runs = expand_case_runs(cases)
            _print_plan(runs)
            return 0

        if args.command == "run":
            run_dir = args.run_dir
            if run_dir is None:
                run_dir = DEFAULT_RUNS_DIR / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dry_run = not args.execute
            return run_case_suite(cases, run_dir, args.resume, dry_run)

    if args.mode == "models":
        result = run_model_benchmark(Path(args.config), Path(args.output_dir), args.run_name)
        print(result)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
