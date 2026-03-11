#!/usr/bin/env python3
"""Aggregate workflow metrics JSONL into raw benchmark records."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable


_SUCCESS_STATUSES = {"completed", "success", "succeeded", "ok"}


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
    job_status = data.get("job_status")

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
        "job_status": job_status,
        "accuracy": _extract_accuracy(data),
        "latency_seconds": _extract_latency_seconds(event, data),
        "cost_usd": _extract_cost_usd(data),
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


def _extract_accuracy(data: dict[str, Any]) -> float | None:
    direct = _as_score(data.get("accuracy"))
    if direct is not None:
        return direct

    for key in ("accuracy_score", "success_rate"):
        value = _as_score(data.get(key))
        if value is not None:
            return value

    for key in ("is_correct", "correct", "success", "converged"):
        value = data.get(key)
        if isinstance(value, bool):
            return 1.0 if value else 0.0

    return None


def _extract_latency_seconds(event: dict[str, Any], data: dict[str, Any]) -> float | None:
    for key in ("wall_time_seconds", "duration_seconds", "latency_seconds"):
        value = _as_float(data.get(key))
        if value is not None:
            return value

    for key in ("stage_latency_ms", "node_latency_ms"):
        value = _as_float(event.get(key))
        if value is not None:
            return round(value / 1000.0, 3)
    return None


def _extract_cost_usd(data: dict[str, Any]) -> float | None:
    for key in ("cost_usd", "total_cost_usd"):
        value = _as_float(data.get(key))
        if value is not None:
            return value

    cost_breakdown = data.get("cost_breakdown")
    if isinstance(cost_breakdown, dict):
        value = _as_float(cost_breakdown.get("total_usd"))
        if value is not None:
            return value
    return None


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
    if key == "retrieval_strategy":
        rows = _add_naive_savings(rows, label)
    return rows


def _summarize_items(items: list[dict[str, Any]], label: str, value: str) -> dict[str, Any]:
    total = len(items)
    success = sum(1 for item in items if str(item.get("job_status") or "").lower() in _SUCCESS_STATUSES)
    tokens_total = _avg([item.get("tokens_total") for item in items])
    tokens_input = _avg([item.get("tokens_total_input") for item in items])
    tokens_output = _avg([item.get("tokens_total_output") for item in items])
    accuracy_values = _number_values(items, "accuracy")
    latency_values = _number_values(items, "latency_seconds")
    cost_values = _number_values(items, "cost_usd")
    if accuracy_values:
        avg_accuracy = round(sum(accuracy_values) / len(accuracy_values), 4)
        accuracy_sample_count = len(accuracy_values)
    else:
        avg_accuracy = round(success / total, 4) if total else 0.0
        accuracy_sample_count = total
    return {
        label: value,
        "total_runs": total,
        "success_runs": success,
        "success_rate": round(success / total, 4) if total else 0.0,
        "avg_accuracy": avg_accuracy,
        "accuracy_sample_count": accuracy_sample_count,
        "avg_latency_seconds": _avg(latency_values),
        "latency_sample_count": len(latency_values),
        "avg_cost_usd": _avg(cost_values),
        "cost_sample_count": len(cost_values),
        "avg_tokens_total": tokens_total,
        "avg_tokens_input": tokens_input,
        "avg_tokens_output": tokens_output,
    }


def _add_naive_savings(rows: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    naive_row = next((row for row in rows if row.get(label) == "naive"), None)
    if naive_row is None:
        for row in rows:
            row.update(_empty_savings_fields())
        return rows

    baseline_total = _numeric_or_none(naive_row.get("avg_tokens_total"))
    baseline_input = _numeric_or_none(naive_row.get("avg_tokens_input"))
    baseline_output = _numeric_or_none(naive_row.get("avg_tokens_output"))

    for row in rows:
        row.update({
            "naive_avg_tokens_total": baseline_total,
            "naive_avg_tokens_input": baseline_input,
            "naive_avg_tokens_output": baseline_output,
            "savings_tokens_total_vs_naive": _savings_abs(
                baseline_total,
                _numeric_or_none(row.get("avg_tokens_total")),
            ),
            "savings_tokens_input_vs_naive": _savings_abs(
                baseline_input,
                _numeric_or_none(row.get("avg_tokens_input")),
            ),
            "savings_tokens_output_vs_naive": _savings_abs(
                baseline_output,
                _numeric_or_none(row.get("avg_tokens_output")),
            ),
            "savings_tokens_total_pct_vs_naive": _savings_pct(
                baseline_total,
                _numeric_or_none(row.get("avg_tokens_total")),
            ),
            "savings_tokens_input_pct_vs_naive": _savings_pct(
                baseline_input,
                _numeric_or_none(row.get("avg_tokens_input")),
            ),
            "savings_tokens_output_pct_vs_naive": _savings_pct(
                baseline_output,
                _numeric_or_none(row.get("avg_tokens_output")),
            ),
        })

    return rows


def _empty_savings_fields() -> dict[str, None]:
    return {
        "naive_avg_tokens_total": None,
        "naive_avg_tokens_input": None,
        "naive_avg_tokens_output": None,
        "savings_tokens_total_vs_naive": None,
        "savings_tokens_input_vs_naive": None,
        "savings_tokens_output_vs_naive": None,
        "savings_tokens_total_pct_vs_naive": None,
        "savings_tokens_input_pct_vs_naive": None,
        "savings_tokens_output_pct_vs_naive": None,
    }


def _numeric_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _savings_abs(naive_avg: float | None, strategy_avg: float | None) -> float | None:
    if naive_avg is None or strategy_avg is None:
        return None
    return round(naive_avg - strategy_avg, 2)


def _savings_pct(naive_avg: float | None, strategy_avg: float | None) -> float | None:
    if naive_avg is None or strategy_avg is None or naive_avg == 0:
        return None
    return round(((naive_avg - strategy_avg) / naive_avg) * 100, 2)


def _avg(values: list[Any]) -> float:
    filtered = [v for v in values if isinstance(v, (int, float))]
    if not filtered:
        return 0.0
    return round(sum(filtered) / len(filtered), 2)


def _number_values(items: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for item in items:
        value = _as_float(item.get(key))
        if value is not None:
            values.append(value)
    return values


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _as_score(value: Any) -> float | None:
    score = _as_float(value)
    if score is None:
        return None
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


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
        "avg_accuracy",
        "accuracy_sample_count",
        "avg_latency_seconds",
        "latency_sample_count",
        "avg_cost_usd",
        "cost_sample_count",
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
        "avg_accuracy",
        "accuracy_sample_count",
        "avg_latency_seconds",
        "latency_sample_count",
        "avg_cost_usd",
        "cost_sample_count",
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
        "avg_accuracy",
        "accuracy_sample_count",
        "avg_latency_seconds",
        "latency_sample_count",
        "avg_cost_usd",
        "cost_sample_count",
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
        "avg_accuracy",
        "accuracy_sample_count",
        "avg_latency_seconds",
        "latency_sample_count",
        "avg_cost_usd",
        "cost_sample_count",
        "avg_tokens_total",
        "avg_tokens_input",
        "avg_tokens_output",
        "naive_avg_tokens_total",
        "naive_avg_tokens_input",
        "naive_avg_tokens_output",
        "savings_tokens_total_vs_naive",
        "savings_tokens_input_vs_naive",
        "savings_tokens_output_vs_naive",
        "savings_tokens_total_pct_vs_naive",
        "savings_tokens_input_pct_vs_naive",
        "savings_tokens_output_pct_vs_naive",
    ])

    by_difficulty = _group_summary(records, "difficulty_tier", "difficulty_tier")
    _write_csv(output_dir / "by_difficulty.csv", by_difficulty, [
        "difficulty_tier",
        "total_runs",
        "success_runs",
        "success_rate",
        "avg_accuracy",
        "accuracy_sample_count",
        "avg_latency_seconds",
        "latency_sample_count",
        "avg_cost_usd",
        "cost_sample_count",
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
        "avg_accuracy",
        "accuracy_sample_count",
        "avg_latency_seconds",
        "latency_sample_count",
        "avg_cost_usd",
        "cost_sample_count",
        "avg_tokens_total",
        "avg_tokens_input",
        "avg_tokens_output",
    ])
    print(json.dumps({"output": str(output_path), "records": len(records)}, indent=2))


if __name__ == "__main__":
    main()
