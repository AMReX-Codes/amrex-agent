#!/usr/bin/env python3
"""Aggregate benchmark metrics into comparison tables."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


SOLVER_ALIASES: dict[str, tuple[str, ...]] = {
    "AMReX": ("amrex",),
    "PeleC": ("pelec",),
    "PeleLMeX": ("pelelmex",),
    "ERF": ("erf",),
    "incflo": ("incflo",),
    "IAMR": ("iamr",),
    "REMORA": ("remora",),
    "WarpX": ("warpx",),
}


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


def _normalize_solver_name(value: str) -> str | None:
    normalized = value.strip().lower()
    if not normalized:
        return None
    for canonical, aliases in SOLVER_ALIASES.items():
        if normalized == canonical.lower() or normalized in aliases:
            return canonical
    return None


def _infer_solver(record: dict[str, Any]) -> str:
    direct_solver = record.get("solver")
    if isinstance(direct_solver, str):
        normalized_direct = _normalize_solver_name(direct_solver)
        if normalized_direct:
            return normalized_direct

    probes = [
        record.get("selected_case"),
        record.get("prompt_id"),
        record.get("case_id"),
        record.get("prompt_excerpt"),
    ]
    probe_text = " ".join(str(item).lower() for item in probes if isinstance(item, str))
    for canonical, aliases in SOLVER_ALIASES.items():
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", probe_text) for alias in aliases):
            return canonical
    return "unknown"


def _build_generalization_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_solver: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_solver.setdefault(_infer_solver(record), []).append(record)

    rows: list[dict[str, Any]] = []
    for solver, items in sorted(by_solver.items()):
        completed = sum(1 for item in items if item.get("job_status") == "completed")
        durations = [item["duration_seconds"] for item in items if isinstance(item.get("duration_seconds"), (int, float))]
        selected_cases = {
            str(item.get("selected_case")).strip()
            for item in items
            if isinstance(item.get("selected_case"), str) and str(item.get("selected_case")).strip()
        }
        model_ids = {
            str(item.get("model_id")).strip()
            for item in items
            if isinstance(item.get("model_id"), str) and str(item.get("model_id")).strip()
        }
        rows.append({
            "solver": solver,
            "total_runs": len(items),
            "completed_runs": completed,
            "success_rate": (completed / len(items)) if items else 0.0,
            "unique_models": len(model_ids),
            "unique_selected_cases": len(selected_cases),
            "avg_duration_seconds": _mean(durations),
        })

    return rows


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
    generalization_rows = _build_generalization_rows(records)
    known_solver_rows = [row for row in generalization_rows if row["solver"] != "unknown"]
    known_total_runs = sum(int(row["total_runs"]) for row in known_solver_rows)
    known_completed_runs = sum(int(row["completed_runs"]) for row in known_solver_rows)
    summary_row.update(
        {
            "generalization_solver_count": len(known_solver_rows),
            "generalization_unknown_runs": sum(int(row["total_runs"]) for row in generalization_rows if row["solver"] == "unknown"),
            "generalization_cross_solver_success_rate": (
                (known_completed_runs / known_total_runs) if known_total_runs else 0.0
            ),
        }
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
