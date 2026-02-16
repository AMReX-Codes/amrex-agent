#!/usr/bin/env python3
"""Aggregate workflow metrics JSONL into raw benchmark records."""

from __future__ import annotations

import argparse
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

    return {
        "model_id": model_id,
        "provider": provider,
        "prompt_id": context.get("prompt_id"),
        "prompt_excerpt": context.get("prompt_excerpt"),
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
    print(json.dumps({"output": str(output_path), "records": len(records)}, indent=2))


if __name__ == "__main__":
    main()
