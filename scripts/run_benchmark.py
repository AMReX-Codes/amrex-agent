#!/usr/bin/env python3
"""Run benchmark suites (case grids or multi-model prompt runs)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _render_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        f"| {' | '.join(headers)} |",
        f"| {' | '.join(['---'] * len(headers))} |",
    ]
    for row in rows:
        lines.append(f"| {' | '.join(row)} |")
    return "\n".join(lines)


def _write_camera_ready_tables(comparison_dir: Path) -> list[str]:
    summary_rows = _read_csv_rows(comparison_dir / "summary.csv")
    by_model_rows = _read_csv_rows(comparison_dir / "by_model.csv")
    by_solver_rows = _read_csv_rows(comparison_dir / "generalization_by_solver.csv")

    sections = ["# Camera-ready Benchmark Tables", ""]
    generated_tables: list[str] = []

    if summary_rows:
        row = summary_rows[0]
        sections.extend(
            [
                "## Table 1: Run Summary",
                "",
                _render_markdown_table(
                    ["Total Models", "Total Runs", "Completed", "Failed", "Skipped"],
                    [[
                        str(row.get("total_models", "0")),
                        str(row.get("total_runs", "0")),
                        str(row.get("completed_runs", "0")),
                        str(row.get("failed_runs", "0")),
                        str(row.get("skipped_runs", "0")),
                    ]],
                ),
                "",
            ]
        )
        generated_tables.append("summary.csv")

    if by_model_rows:
        sections.extend(
            [
                "## Table 2: Model Comparison",
                "",
                _render_markdown_table(
                    ["Model", "Runs", "Success Rate", "Analysis Success Rate"],
                    [[
                        str(row.get("model_id", "unknown")),
                        str(row.get("total_runs", "0")),
                        str(row.get("success_rate", "0")),
                        str(row.get("analysis_success_rate", "0")),
                    ] for row in by_model_rows],
                ),
                "",
            ]
        )
        generated_tables.append("by_model.csv")

    if by_solver_rows:
        sections.extend(
            [
                "## Table 3: Cross-solver Generalization",
                "",
                _render_markdown_table(
                    ["Solver", "Runs", "Success Rate", "Unique Models", "Unique Cases"],
                    [[
                        str(row.get("solver", "unknown")),
                        str(row.get("total_runs", "0")),
                        str(row.get("success_rate", "0")),
                        str(row.get("unique_models", "0")),
                        str(row.get("unique_selected_cases", "0")),
                    ] for row in by_solver_rows],
                ),
                "",
            ]
        )
        generated_tables.append("generalization_by_solver.csv")

    output_path = comparison_dir / "camera_ready_tables.md"
    output_path.write_text("\n".join(sections), encoding="utf-8")
    return generated_tables


def _build_camera_ready_pipeline_contract(run_dir: Path, comparison_dir: Path) -> dict:
    required_artifacts = [
        run_dir / "benchmark_runs.jsonl",
        comparison_dir / "summary.csv",
        comparison_dir / "by_model.csv",
        comparison_dir / "camera_ready_tables.md",
    ]
    missing_artifacts = [str(path) for path in required_artifacts if not path.exists()]
    return {
        "criterion": "UNNUMBERED-094",
        "camera_ready_pipeline": [
            {
                "phase_id": "benchmark_execution",
                "implementation_locations": [
                    "scripts/run_benchmark.py::main",
                    "src/benchmark_runner.py::run_model_benchmark",
                ],
                "tests": [
                    "tests/unit/test_benchmark_runner.py::test_run_model_benchmark_writes_manifest_and_metrics",
                ],
            },
            {
                "phase_id": "aggregation",
                "implementation_locations": ["scripts/compare_models.py::main"],
                "tests": [
                    "tests/integration/test_oracle_benchmarks.py::test_oracle_gate_benchmark_alignment_contract",
                ],
            },
            {
                "phase_id": "table_generation",
                "implementation_locations": ["scripts/run_benchmark.py::_write_camera_ready_tables"],
                "tests": [
                    "tests/unit/test_benchmark_runner.py::test_run_benchmark_camera_ready_pipeline_writes_contract",
                ],
            },
        ],
        "required_artifacts": [str(path) for path in required_artifacts],
        "missing_artifacts": missing_artifacts,
        "passes": not missing_artifacts,
    }


def _run_camera_ready_pipeline(run_dir: Path) -> dict:
    comparison_dir = run_dir / "camera_ready"
    comparison_dir.mkdir(parents=True, exist_ok=True)
    compare_cmd = [
        os.environ.get("AMREX_AGENT_PYTHON", sys.executable),
        "scripts/compare_models.py",
        "--run-dir",
        str(run_dir),
        "--output-dir",
        str(comparison_dir),
    ]
    compare_result = subprocess.run(
        compare_cmd,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
    )
    if compare_result.returncode != 0:
        raise RuntimeError(compare_result.stderr.strip() or "compare_models.py failed")

    generated_from_csvs = _write_camera_ready_tables(comparison_dir)
    contract = _build_camera_ready_pipeline_contract(run_dir, comparison_dir)
    contract["generated_from_csvs"] = generated_from_csvs
    contract["comparison_stdout"] = compare_result.stdout.strip()
    contract_path = run_dir / "camera_ready_pipeline.json"
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")

    if not contract["passes"]:
        missing = ", ".join(contract["missing_artifacts"])
        raise RuntimeError(f"camera-ready pipeline missing artifacts: {missing}")
    return contract


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
        contract = _run_camera_ready_pipeline(Path(result["run_dir"]))
        result["camera_ready_pipeline"] = str(Path(result["run_dir"]) / "camera_ready_pipeline.json")
        result["camera_ready_contract_passes"] = contract["passes"]
        print(result)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
