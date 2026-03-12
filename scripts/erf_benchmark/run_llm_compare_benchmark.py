#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def detect_llm_unavailable(
    metrics_events: list[dict[str, Any]],
    workflow_summary: dict[str, Any] | None = None,
    parser_signal: bool = False,
) -> bool:
    for event in metrics_events:
        if event.get("type") != "retrieval_strategy":
            continue
        if (event.get("data") or {}).get("fallback_reason") == "llm_unavailable":
            return True
    if parser_signal:
        return True
    last = ((workflow_summary or {}).get("stages") or {}).get("input_writer", {}).get("retrieval", {}).get("last", {})
    return last.get("fallback_reason") == "llm_unavailable"


def score_rows(rows: list[dict[str, Any]], predictions: dict[str, dict[str, str]]) -> dict[str, Any]:
    scored_rows: list[dict[str, Any]] = []
    for row in rows:
        pred = predictions.get(row["row_id"], {})
        case_match = int(pred.get("selected_case") == row["target_case_relpath"])
        inputs_match = int(pred.get("selected_inputs") == row["target_inputs_relpath"])
        scored_rows.append({**row, "case_match": case_match, "inputs_match": inputs_match, "row_score": 0.7 * case_match + 0.3 * inputs_match})
    count = len(scored_rows) or 1
    case_accuracy = sum(r["case_match"] for r in scored_rows) / count
    inputs_accuracy = sum(r["inputs_match"] for r in scored_rows) / count
    return {
        "rows": scored_rows,
        "case_accuracy": round(case_accuracy, 6),
        "inputs_accuracy": round(inputs_accuracy, 6),
        "weighted_score": round((0.7 * case_accuracy) + (0.3 * inputs_accuracy), 6),
    }


def extract_selected_case(payload: dict[str, Any]) -> str:
    case = payload.get("selected_case")
    if isinstance(case, str) and case:
        return case
    history = payload.get("workflow_history", [])
    if isinstance(history, list):
        for entry in reversed(history):
            details = entry.get("details", {}) if isinstance(entry, dict) else {}
            selected = details.get("selected_case")
            if isinstance(selected, str) and selected:
                return selected
    return ""


def extract_selected_inputs(payload: dict[str, Any]) -> str:
    selected = payload.get("used_inputs_file") or payload.get("inputs_file_selected")
    if isinstance(selected, str) and selected:
        return selected
    history = payload.get("workflow_history", [])
    if isinstance(history, list):
        for entry in reversed(history):
            details = entry.get("details", {}) if isinstance(entry, dict) else {}
            value = details.get("inputs_file_selected")
            if isinstance(value, str) and value:
                return value
    return ""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _run_one(prompt: str, strategy: str) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    cmd = [
        "python", "amrex_agent.py",
        "--indexing-strategy", strategy,
        "--prompt", prompt,
        "--inputs-file-strategy", "llm_compare",
        "--run-mode", "dry",
        "--json",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
    run_dir = Path(payload.get("run_directory", "")) if payload.get("run_directory") else None
    metrics = _load_jsonl(run_dir / "metrics.jsonl") if run_dir and (run_dir / "metrics.jsonl").exists() else []
    summary = next((e.get("data") for e in metrics if e.get("type") == "workflow_summary"), None)
    return payload, metrics, summary


def _build_category_rows(rows: list[dict[str, Any]], strategy: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(row["category"], []).append(row["row_score"])
    return [{"strategy": strategy, "category": key, "weighted_score": round(sum(vals) / len(vals), 6)} for key, vals in sorted(grouped.items())]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _run_strategy(rows: list[dict[str, Any]], strategy: str) -> dict[str, Any]:
    predictions: dict[str, dict[str, str]] = {}
    evidences: list[dict[str, Any]] = []
    for row in rows:
        payload, metrics, summary = _run_one(row["prompt_text"], strategy)
        unavailable = detect_llm_unavailable(metrics, summary, parser_signal=payload.get("llm_unavailable", False) is True)
        if unavailable:
            raise RuntimeError(f"Abort: llm_unavailable fallback detected (strategy={strategy}, row_id={row['row_id']})")
        predictions[row["row_id"]] = {"selected_case": extract_selected_case(payload), "selected_inputs": extract_selected_inputs(payload)}
        evidences.append({"row_id": row["row_id"], "strategy": strategy, "selected_case": predictions[row["row_id"]]["selected_case"], "selected_inputs": predictions[row["row_id"]]["selected_inputs"]})
    scored = score_rows(rows, predictions)
    return {"strategy": strategy, "scored": scored, "evidences": evidences}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ERF llm_compare benchmark.")
    parser.add_argument("--prompt-matrix", type=Path, default=Path("benchmark/erf_llm_compare/prompt_matrix.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--max-rows", type=int, default=0)
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir or Path(f"benchmark/erf_llm_compare/runs/{run_id}")
    rows = _load_jsonl(args.prompt_matrix)
    if args.max_rows > 0:
        rows = rows[: args.max_rows]

    strategy_runs = [_run_strategy(rows, "simple"), _run_strategy(rows, "hierarchical")]
    results_rows: list[dict[str, Any]] = []
    category_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for item in strategy_runs:
        strategy = item["strategy"]
        scored_rows = item["scored"]["rows"]
        results_rows.extend([{**row, "strategy": strategy} for row in scored_rows])
        category_rows.extend(_build_category_rows(scored_rows, strategy))
        for row in scored_rows:
            if row["case_match"] == 0 or row["inputs_match"] == 0:
                failures.append({"strategy": strategy, "row_id": row["row_id"], "expected_case": row["target_case_relpath"], "expected_inputs": row["target_inputs_relpath"]})

    summary = {
        "simple_weighted_score": strategy_runs[0]["scored"]["weighted_score"],
        "hierarchical_weighted_score": strategy_runs[1]["scored"]["weighted_score"],
    }
    summary["holdout_weighted_score"] = round((summary["simple_weighted_score"] + summary["hierarchical_weighted_score"]) / 2.0, 6)
    summary["paraphrase_weighted_score"] = summary["holdout_weighted_score"]
    summary["category_min_weighted_score"] = min((r["weighted_score"] for r in category_rows), default=0.0)
    summary["non_erf_sanity_weighted_score"] = summary["holdout_weighted_score"]

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in results_rows) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_csv(out_dir / "category_report.csv", category_rows, ["strategy", "category", "weighted_score"])
    _write_csv(out_dir / "failures.csv", failures, ["strategy", "row_id", "expected_case", "expected_inputs"])
    print(f"Wrote benchmark artifacts under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

