#!/usr/bin/env python3
"""Aggregate workflow metrics JSONL into raw benchmark records."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable


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


def _write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in headers})


def _group_summary(records: list[dict[str, Any]], key: str, label: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        value = record.get(key) or "unknown"
        grouped.setdefault(str(value), []).append(record)

    rows = []
    for value, items in sorted(grouped.items(), key=lambda item: item[0]):
        rows.append(_summarize_items(items, label, value))
    return rows


def _latex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _render_latex_table(
    caption: str,
    label: str,
    headers: list[str],
    rows: list[list[Any]],
) -> str:
    columns = "l" + ("r" * (len(headers) - 1))
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        rf"\caption{{{_latex_escape(caption)}}}",
        rf"\label{{{_latex_escape(label)}}}",
        rf"\begin{{tabular}}{{{columns}}}",
        r"\toprule",
        " & ".join(rf"\textbf{{{_latex_escape(header)}}}" for header in headers) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(_latex_escape(value) for value in row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return "\n".join(lines) + "\n"


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _average_numeric(values: list[Any]) -> float:
    filtered = [value for value in values if isinstance(value, (int, float))]
    if not filtered:
        return 0.0
    return round(sum(filtered) / len(filtered), 2)


def _group_records(records: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        group_key = str(record.get(key) or "unknown")
        grouped.setdefault(group_key, []).append(record)
    return dict(sorted(grouped.items()))


def _iter_threshold_success(items: list[dict[str, Any]], threshold: int) -> int:
    count = 0
    for item in items:
        iteration = item.get("iteration")
        if not isinstance(iteration, int):
            continue
        if item.get("job_status") != "completed":
            continue
        if iteration <= threshold:
            count += 1
    return count


def _write_paper_tables(output_dir: Path, records: list[dict[str, Any]]) -> None:
    table_dir = output_dir / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    by_model = _group_records(records, "model_id")
    by_solver = _group_records(records, "solver")
    by_strategy = _group_records(records, "retrieval_strategy")

    model_rows = []
    for model, items in by_model.items():
        total = len(items)
        success = sum(1 for item in items if item.get("job_status") == "completed")
        model_rows.append([
            model,
            total,
            success,
            f"{_safe_ratio(success, total):.2%}",
            _average_numeric([item.get("tokens_total") for item in items]),
        ])
    (table_dir / "model_comparison.tex").write_text(
        _render_latex_table(
            "Table 1: Model Comparison",
            "tab:model_comparison",
            ["Model", "Total", "Success", "Success Rate", "Avg Tokens"],
            model_rows,
        ),
        encoding="utf-8",
    )

    strategy_rows = []
    for strategy, items in by_strategy.items():
        total = len(items)
        success = sum(1 for item in items if item.get("job_status") == "completed")
        strategy_rows.append([
            strategy,
            total,
            f"{_safe_ratio(success, total):.2%}",
            _average_numeric([item.get("tokens_total") for item in items]),
        ])
    (table_dir / "strategy_performance.tex").write_text(
        _render_latex_table(
            "Table 2: Strategy Performance",
            "tab:strategy_performance",
            ["Strategy", "Total", "Success Rate", "Avg Tokens"],
            strategy_rows,
        ),
        encoding="utf-8",
    )

    validation_rows = []
    for solver, items in by_solver.items():
        total = len(items)
        success = sum(1 for item in items if item.get("job_status") == "completed")
        validation_rows.append([solver, total, success, f"{_safe_ratio(success, total):.2%}"])
    (table_dir / "validation_effectiveness.tex").write_text(
        _render_latex_table(
            "Table 3: Validation Effectiveness",
            "tab:validation_effectiveness",
            ["Solver", "Total", "Passed", "Pass Rate"],
            validation_rows,
        ),
        encoding="utf-8",
    )

    cost_rows = []
    for model, items in by_model.items():
        input_avg = _average_numeric([item.get("tokens_total_input") for item in items])
        output_avg = _average_numeric([item.get("tokens_total_output") for item in items])
        cost_rows.append([model, input_avg, output_avg, round(input_avg + output_avg, 2)])
    (table_dir / "cost_analysis.tex").write_text(
        _render_latex_table(
            "Table 4: Cost Analysis",
            "tab:cost_analysis",
            ["Model", "Avg Input Tokens", "Avg Output Tokens", "Avg Total Tokens"],
            cost_rows,
        ),
        encoding="utf-8",
    )

    iteration_rows = []
    for model, items in by_model.items():
        total = len(items)
        iteration_rows.append([
            model,
            total,
            f"{_safe_ratio(_iter_threshold_success(items, 0), total):.2%}",
            f"{_safe_ratio(_iter_threshold_success(items, 1), total):.2%}",
            f"{_safe_ratio(_iter_threshold_success(items, 2), total):.2%}",
        ])
    (table_dir / "iteration_convergence.tex").write_text(
        _render_latex_table(
            "Table 5: Iteration Convergence",
            "tab:iteration_convergence",
            ["Model", "Total", "At Iter 0", "At Iter 1", "At Iter 2"],
            iteration_rows,
        ),
        encoding="utf-8",
    )

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
    output_path.parent.mkdir(parents=True, exist_ok=True)

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
    _write_paper_tables(output_dir, records)
    print(json.dumps({"output": str(output_path), "records": len(records)}, indent=2))


if __name__ == "__main__":
    main()
