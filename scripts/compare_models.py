#!/usr/bin/env python3
"""Aggregate benchmark metrics into comparison tables."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _infer_solver(record: dict[str, Any]) -> str:
    solver = record.get("solver")
    if isinstance(solver, str) and solver.strip():
        return solver
    selected_case = str(record.get("selected_case") or "").lower()
    if "warpx" in selected_case:
        return "WarpX"
    if "amrex" in selected_case or "amrcore" in selected_case:
        return "AMReX"
    if "pelec" in selected_case:
        return "PeleC"
    if "pelelmex" in selected_case:
        return "PeleLMeX"
    if "erf" in selected_case:
        return "ERF"
    return "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate model comparison tables.")
    parser.add_argument("--run-dir", help="Benchmark run directory (contains benchmark_runs.jsonl).")
    parser.add_argument("--input", help="Path to benchmark_runs.jsonl.")
    parser.add_argument(
        "--output-dir",
        help="Directory to write CSV outputs (default: run dir).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.run_dir and not args.input:
        raise ValueError("Provide --run-dir or --input.")

    run_dir = Path(args.run_dir) if args.run_dir else None
    input_path = Path(args.input) if args.input else (run_dir / "benchmark_runs.jsonl")
    output_dir = Path(args.output_dir) if args.output_dir else (run_dir or input_path.parent)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = _read_jsonl(input_path)
    if not records:
        raise ValueError(f"No records found in {input_path}")

    by_model: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        model_id = record.get("model_id", "unknown")
        by_model.setdefault(model_id, []).append(record)

    by_model_rows = []
    for model_id, items in sorted(by_model.items()):
        durations = [r["duration_seconds"] for r in items if isinstance(r.get("duration_seconds"), (int, float))]
        perf_values = []
        for item in items:
            perf = (item.get("analysis_performance") or {}).get("avg_cells_per_sec")
            if isinstance(perf, (int, float)):
                perf_values.append(perf)
        total = len(items)
        completed = sum(1 for r in items if r.get("job_status") == "completed")
        failed = sum(1 for r in items if r.get("job_status") == "failed")
        skipped = sum(1 for r in items if r.get("job_status") == "skipped")
        analysis_success = sum(1 for r in items if r.get("analysis_status") == "success")
        by_model_rows.append({
            "model_id": model_id,
            "total_runs": total,
            "completed_runs": completed,
            "failed_runs": failed,
            "skipped_runs": skipped,
            "analysis_success_runs": analysis_success,
            "success_rate": (completed / total) if total else 0.0,
            "analysis_success_rate": (analysis_success / total) if total else 0.0,
            "avg_duration_seconds": _mean(durations),
            "avg_cells_per_sec": _mean(perf_values),
        })

    by_prompt_rows = []
    for record in records:
        by_prompt_rows.append({
            "prompt_id": record.get("prompt_id"),
            "model_id": record.get("model_id"),
            "job_status": record.get("job_status"),
            "analysis_status": record.get("analysis_status"),
            "duration_seconds": record.get("duration_seconds"),
            "avg_cells_per_sec": (record.get("analysis_performance") or {}).get("avg_cells_per_sec"),
            "run_directory": record.get("run_directory"),
            "prompt_excerpt": record.get("prompt_excerpt"),
        })

    summary_row = {
        "total_models": len(by_model),
        "total_runs": len(records),
        "completed_runs": sum(1 for r in records if r.get("job_status") == "completed"),
        "failed_runs": sum(1 for r in records if r.get("job_status") == "failed"),
        "skipped_runs": sum(1 for r in records if r.get("job_status") == "skipped"),
    }

    by_solver: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        solver = _infer_solver(record)
        by_solver.setdefault(solver, []).append(record)

    generalization_rows = []
    for solver, items in sorted(by_solver.items(), key=lambda item: item[0]):
        total = len(items)
        completed = sum(1 for item in items if item.get("job_status") == "completed")
        generalization_rows.append(
            {
                "solver": solver,
                "total_runs": total,
                "completed_runs": completed,
            }
        )

    non_unknown = [item for item in records if _infer_solver(item) != "unknown"]
    non_unknown_completed = sum(1 for item in non_unknown if item.get("job_status") == "completed")
    summary_row["generalization_solver_count"] = sum(1 for solver in by_solver if solver != "unknown")
    summary_row["generalization_unknown_runs"] = len(by_solver.get("unknown", []))
    summary_row["generalization_cross_solver_success_rate"] = (
        (non_unknown_completed / len(non_unknown)) if non_unknown else 0.0
    )

    def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    write_csv(output_dir / "by_model.csv", by_model_rows)
    write_csv(output_dir / "by_prompt.csv", by_prompt_rows)
    write_csv(output_dir / "generalization_by_solver.csv", generalization_rows)
    write_csv(output_dir / "summary.csv", [summary_row])

    print(json.dumps({
        "input": str(input_path),
        "output_dir": str(output_dir),
        "rows": len(records),
    }, indent=2))


if __name__ == "__main__":
    main()
