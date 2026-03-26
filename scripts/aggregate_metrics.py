#!/usr/bin/env python3
"""Aggregate workflow metrics JSONL into raw benchmark records."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

STABLE_ERROR_TAXONOMY_VERSION = "v1"
STABLE_ERROR_REASON_CODES = frozenset(
    {
        "feature_a_dependency_unverified",
        "amendment_module_helper_extraction_missing",
        "global_function_complexity_threshold_exceeded",
        "level4_depth_guidance_missing",
        "level4_depth_guidance_out_of_range",
        "plan_generation_latency_missing",
        "plan_generation_p95_exceeded",
        "error_taxonomy_version_mismatch",
        "error_taxonomy_reason_code_unknown",
        "error_taxonomy_contract_invalid",
        "uc_traceability_rows_missing",
        "uc_traceable_artifact_missing",
        "uc_traceable_artifact_stale",
        "impl_tests_sync_missing",
        "impl_locations_missing",
        "tests_missing",
    }
)


def _iter_metric_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        return [path]
    return sorted(path.rglob("metrics*.jsonl"))


def _load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def _record_from_event(event: dict[str, Any], source: Path) -> dict[str, Any]:
    data = event.get("data", {})
    context = event.get("context", {})
    models = data.get("models") or []
    providers = data.get("providers") or []
    model_id = context.get("model_id") or (models[0] if models else "unknown")
    provider = context.get("provider") or (providers[0] if providers else None)
    strategy = context.get("strategy") or data.get("strategy") or _extract_strategy(data)
    taxonomy_version = data.get("error_taxonomy_version")
    if not isinstance(taxonomy_version, str) or not taxonomy_version:
        taxonomy_version = STABLE_ERROR_TAXONOMY_VERSION

    reason_codes = _collect_error_reason_codes(data)
    unknown_reason_codes = [code for code in reason_codes if code not in STABLE_ERROR_REASON_CODES]

    return {
        "model_id": model_id,
        "provider": provider,
        "prompt_id": context.get("prompt_id"),
        "prompt_excerpt": context.get("prompt_excerpt"),
        "case_id": context.get("case_id") or data.get("case_id"),
        "solver": context.get("solver") or data.get("solver"),
        "difficulty_tier": context.get("difficulty_tier") or data.get("difficulty_tier"),
        "novelty_tier": context.get("novelty_tier") or data.get("novelty_tier"),
        "retrieval_strategy": strategy,
        "job_status": data.get("job_status"),
        "iteration": data.get("iteration"),
        "run_directory": data.get("run_directory"),
        "selected_case": context.get("selected_case"),
        "tokens_total_input": data.get("tokens_total_input"),
        "tokens_total_output": data.get("tokens_total_output"),
        "tokens_total": data.get("tokens_total"),
        "tokens_by_stage": data.get("tokens_by_stage"),
        "stages": data.get("stages"),
        "error_taxonomy_version": taxonomy_version,
        "error_reason_codes": reason_codes,
        "error_reason_code_count": len(reason_codes),
        "error_reason_codes_unknown": unknown_reason_codes,
        "error_taxonomy_stable": (
            taxonomy_version == STABLE_ERROR_TAXONOMY_VERSION and not unknown_reason_codes
        ),
        "source": str(source),
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, default=str))
            handle.write("\n")


def _extract_strategy(data: dict[str, Any]) -> str | None:
    stages = data.get("stages") or {}
    for summary in stages.values():
        retrieval = summary.get("retrieval") if isinstance(summary, dict) else None
        if not retrieval:
            continue
        last = retrieval.get("last", {}) if isinstance(retrieval, dict) else {}
        strategy = last.get("strategy")
        if strategy:
            return strategy
    return None


def _collect_error_reason_codes(data: dict[str, Any]) -> list[str]:
    reason_codes: set[str] = set()

    errors_active = data.get("errors_active")
    if isinstance(errors_active, list):
        reason_codes.update(code for code in errors_active if isinstance(code, str) and code)

    gate_approvals = data.get("gate_approvals")
    if isinstance(gate_approvals, list):
        for approval in gate_approvals:
            if not isinstance(approval, dict):
                continue
            details = approval.get("details")
            if not isinstance(details, dict):
                continue
            reason_code = details.get("reason_code")
            if isinstance(reason_code, str) and reason_code:
                reason_codes.add(reason_code)

    return sorted(reason_codes)


def _write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in headers})


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _format_percent(value: str | float | int | None) -> str:
    if isinstance(value, str):
        try:
            numeric = float(value)
        except ValueError:
            return "N/A"
    elif isinstance(value, (int, float)):
        numeric = float(value)
    else:
        return "N/A"
    return f"{numeric * 100:.2f}%"


def _generate_strategy_table_text(summary_rows: list[dict[str, str]], strategy_rows: list[dict[str, str]]) -> str:
    overall = summary_rows[0] if summary_rows else {}
    lines = [
        "# Strategy Comparison",
        "",
        f"Overall runs: {overall.get('total_runs', '0')}",
        f"Overall success rate: {_format_percent(overall.get('success_rate'))}",
        "",
        "| Strategy | Success Rate | Success/Total | Avg Tokens (In/Out/Total) |",
        "| --- | --- | --- | --- |",
    ]

    for row in strategy_rows:
        strategy = row.get("retrieval_strategy", "unknown")
        success_rate = _format_percent(row.get("success_rate"))
        success_total = f"{row.get('success_runs', '0')}/{row.get('total_runs', '0')}"
        avg_tokens = (
            f"{row.get('avg_tokens_input', '0')}/"
            f"{row.get('avg_tokens_output', '0')}/"
            f"{row.get('avg_tokens_total', '0')}"
        )
        lines.append(f"| {strategy} | {success_rate} | {success_total} | {avg_tokens} |")

    lines.extend(
        [
            "",
            "Generated from `summary.csv` and `by_strategy.csv`.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_strategy_table_from_csvs(output_dir: Path) -> None:
    summary_rows = _read_csv_rows(output_dir / "summary.csv")
    strategy_rows = _read_csv_rows(output_dir / "by_strategy.csv")
    if not summary_rows or not strategy_rows:
        return
    table_text = _generate_strategy_table_text(summary_rows, strategy_rows)
    (output_dir / "strategy_comparison_table.md").write_text(table_text, encoding="utf-8")


def _group_summary(records: list[dict[str, Any]], key: str, label: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        value = record.get(key) or "unknown"
        grouped.setdefault(str(value), []).append(record)

    rows = []
    for value, items in sorted(grouped.items(), key=lambda item: item[0]):
        rows.append(_summarize_items(items, label, value))
    if label == "retrieval_strategy":
        _attach_naive_savings(rows)
    return rows


def _summarize_items(items: list[dict[str, Any]], label: str, value: str) -> dict[str, Any]:
    total = len(items)
    success = sum(1 for item in items if item.get("job_status") == "completed")
    tokens_total = _avg([item.get("tokens_total") for item in items])
    tokens_input = _avg([item.get("tokens_total_input") for item in items])
    tokens_output = _avg([item.get("tokens_total_output") for item in items])
    return {
        label: value,
        "total_runs": total,
        "success_runs": success,
        "success_rate": round(success / total, 4) if total else 0.0,
        "avg_tokens_total": tokens_total,
        "avg_tokens_input": tokens_input,
        "avg_tokens_output": tokens_output,
    }


def _attach_naive_savings(rows: list[dict[str, Any]]) -> None:
    naive_row = next(
        (row for row in rows if str(row.get("retrieval_strategy", "")).lower() == "naive"),
        None,
    )
    naive_avg_total = naive_row.get("avg_tokens_total") if isinstance(naive_row, dict) else None
    naive_avg_input = naive_row.get("avg_tokens_input") if isinstance(naive_row, dict) else None
    naive_avg_output = naive_row.get("avg_tokens_output") if isinstance(naive_row, dict) else None

    for row in rows:
        if isinstance(naive_avg_total, (int, float)):
            avg_total = row.get("avg_tokens_total")
            avg_input = row.get("avg_tokens_input")
            avg_output = row.get("avg_tokens_output")
            total_delta = (
                round(float(naive_avg_total) - float(avg_total), 2)
                if isinstance(avg_total, (int, float))
                else None
            )
            pct_delta = (
                round((total_delta / float(naive_avg_total)) * 100, 2)
                if isinstance(total_delta, (int, float)) and float(naive_avg_total) > 0
                else 0.0
            )
            row["naive_avg_tokens_total"] = round(float(naive_avg_total), 2)
            row["savings_tokens_total_vs_naive"] = total_delta
            row["savings_tokens_total_pct_vs_naive"] = pct_delta
            row["savings_tokens_input_vs_naive"] = (
                round(float(naive_avg_input) - float(avg_input), 2)
                if isinstance(naive_avg_input, (int, float)) and isinstance(avg_input, (int, float))
                else None
            )
            row["savings_tokens_output_vs_naive"] = (
                round(float(naive_avg_output) - float(avg_output), 2)
                if isinstance(naive_avg_output, (int, float)) and isinstance(avg_output, (int, float))
                else None
            )
        else:
            row["naive_avg_tokens_total"] = None
            row["savings_tokens_total_vs_naive"] = None
            row["savings_tokens_total_pct_vs_naive"] = None
            row["savings_tokens_input_vs_naive"] = None
            row["savings_tokens_output_vs_naive"] = None


def _avg(values: list[Any]) -> float:
    filtered = [v for v in values if isinstance(v, (int, float))]
    if not filtered:
        return 0.0
    return round(sum(filtered) / len(filtered), 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate metrics JSONL into raw benchmark records.")
    parser.add_argument("--input", required=True, help="Metrics JSONL file or directory.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output raw_metrics.jsonl path (defaults next to input).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else (input_path / "raw_metrics.jsonl")
    if input_path.is_file():
        output_path = Path(args.output) if args.output else input_path.parent / "raw_metrics.jsonl"

    records: list[dict[str, Any]] = []
    for path in _iter_metric_files(input_path):
        for event in _load_events(path):
            if event.get("type") != "workflow_summary":
                continue
            records.append(_record_from_event(event, path))

    _write_jsonl(output_path, records)
    output_dir = output_path.parent
    summary_headers = [
        "group",
        "total_runs",
        "success_runs",
        "success_rate",
        "avg_tokens_total",
        "avg_tokens_input",
        "avg_tokens_output",
    ]
    summary_row = [_summarize_items(records, "group", "all")]
    _write_csv(output_dir / "summary.csv", summary_row, summary_headers)

    by_model = _group_summary(records, "model_id", "model_id")
    _write_csv(output_dir / "by_model.csv", by_model, [
        "model_id",
        "total_runs",
        "success_runs",
        "success_rate",
        "avg_tokens_total",
        "avg_tokens_input",
        "avg_tokens_output",
    ])

    by_solver = _group_summary(records, "solver", "solver")
    _write_csv(output_dir / "by_solver.csv", by_solver, [
        "solver",
        "total_runs",
        "success_runs",
        "success_rate",
        "avg_tokens_total",
        "avg_tokens_input",
        "avg_tokens_output",
    ])

    by_strategy = _group_summary(records, "retrieval_strategy", "retrieval_strategy")
    _write_csv(output_dir / "by_strategy.csv", by_strategy, [
        "retrieval_strategy",
        "total_runs",
        "success_runs",
        "success_rate",
        "avg_tokens_total",
        "avg_tokens_input",
        "avg_tokens_output",
    ])

    by_difficulty = _group_summary(records, "difficulty_tier", "difficulty_tier")
    _write_csv(output_dir / "by_difficulty.csv", by_difficulty, [
        "difficulty_tier",
        "total_runs",
        "success_runs",
        "success_rate",
        "avg_tokens_total",
        "avg_tokens_input",
        "avg_tokens_output",
    ])

    by_novelty = _group_summary(records, "novelty_tier", "novelty_tier")
    _write_csv(output_dir / "by_novelty.csv", by_novelty, [
        "novelty_tier",
        "total_runs",
        "success_runs",
        "success_rate",
        "avg_tokens_total",
        "avg_tokens_input",
        "avg_tokens_output",
    ])
    _write_strategy_table_from_csvs(output_dir)
    print(json.dumps({"output": str(output_path), "records": len(records)}, indent=2))


if __name__ == "__main__":
    main()
