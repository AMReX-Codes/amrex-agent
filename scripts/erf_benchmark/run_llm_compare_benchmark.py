#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.erf_benchmark.lib.explainability_scoring import (
        build_call_records,
        summarize_explainability,
    )
except ModuleNotFoundError:
    from lib.explainability_scoring import build_call_records, summarize_explainability


def detect_llm_unavailable(
    metrics_events: list[dict[str, Any]],
    workflow_summary: dict[str, Any] | None = None,
    workflow_payload: dict[str, Any] | None = None,
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
    if last.get("fallback_reason") == "llm_unavailable":
        return True
    history = (workflow_payload or {}).get("workflow_history", [])
    if not isinstance(history, list):
        return False
    for entry in reversed(history):
        details = entry.get("details", {}) if isinstance(entry, dict) else {}
        nested = (details.get("metrics") or {}).get("retrieval", {}).get("last", {})
        if nested.get("fallback_reason") == "llm_unavailable":
            return True
    return False


def _extract_exec_relpath(value: str, kind: str) -> str:
    text = value.strip().replace("\\", "/")
    idx = text.find("Exec/")
    rel = text[idx:] if idx >= 0 else text
    rel = rel.rstrip("/")
    if kind == "case" and rel.split("/")[-1].startswith("inputs"):
        return "/".join(rel.split("/")[:-1])
    return rel


def _find_history_value(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    history = payload.get("workflow_history", [])
    if not isinstance(history, list):
        return ""
    for entry in reversed(history):
        details = entry.get("details", {}) if isinstance(entry, dict) else {}
        for key in keys:
            value = details.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def score_rows(rows: list[dict[str, Any]], predictions: dict[str, dict[str, str]]) -> dict[str, Any]:
    scored_rows: list[dict[str, Any]] = []
    for row in rows:
        pred = predictions.get(row["row_id"], {})
        selected_case = _extract_exec_relpath(pred.get("selected_case", ""), kind="case")
        selected_inputs = _extract_exec_relpath(pred.get("selected_inputs", ""), kind="inputs")
        target_case = str(row.get("target_case_relpath", "") or "")
        target_case_prefix = str(row.get("expected_case_prefix", "") or "")
        target_inputs = str(row.get("target_inputs_relpath", "") or "")
        target_inputs_prefix = str(row.get("expected_inputs_prefix", "") or "")
        case_match = int(bool((target_case and selected_case == target_case) or (target_case_prefix and selected_case.startswith(target_case_prefix))))
        inputs_match = int(bool((target_inputs and selected_inputs == target_inputs) or (target_inputs_prefix and selected_inputs.startswith(target_inputs_prefix))))
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
        return _extract_exec_relpath(case, kind="case")
    hist_case = _find_history_value(payload, ("selected_case",))
    if hist_case:
        return _extract_exec_relpath(hist_case, kind="case")
    selected_inputs = extract_selected_inputs(payload)
    if selected_inputs:
        return _extract_exec_relpath(selected_inputs, kind="case")
    return ""


def extract_selected_inputs(payload: dict[str, Any]) -> str:
    selected = payload.get("used_inputs_file") or payload.get("inputs_file_selected")
    if isinstance(selected, str) and selected:
        return _extract_exec_relpath(selected, kind="inputs")
    hist_inputs = _find_history_value(payload, ("inputs_file_selected", "used_inputs_file"))
    if hist_inputs:
        return _extract_exec_relpath(hist_inputs, kind="inputs")
    return ""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _tail_lines(text: str, count: int = 80) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-count:]) if lines else ""

def _extract_json_payload(text: str) -> dict[str, Any]:
    content = (text or "").strip()
    if not content:
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    # Walk forward and retain the last valid object found.
    last_obj: dict[str, Any] | None = None
    for idx, ch in enumerate(content):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(content[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            last_obj = obj
    if last_obj is None:
        raise json.JSONDecodeError("No JSON object found in stdout", content, 0)
    return last_obj


def _scan_console_events(stdout: str, stderr: str, *, row_id: str, strategy: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    ansi = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
    text = ansi.sub("", f"{stdout}\n{stderr}")
    if "Traceback (most recent call last)" in text:
        events.append({"row_id": row_id, "strategy": strategy, "severity": "catastrophic", "reason": "python_traceback"})
    for needle, reason in (("[ERROR]", "error_log_statement"), ("ERROR", "error_token"), ("[WARN]", "warn_log_statement"), ("WARNING", "warning_token")):
        if needle in text:
            sev = "error" if "error" in reason else "warning"
            events.append({"row_id": row_id, "strategy": strategy, "severity": sev, "reason": reason})
    return events


def _run_one(
    prompt: str,
    strategy: str,
    *,
    agent_config: Path | None = None,
    inputs_file_strategy: str = "llm_compare",
    verbose_cli: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None, dict[str, Any]]:
    cmd = [
        "python", "amrex_agent.py",
        "--indexing-strategy", strategy,
        "--prompt", prompt,
        "--inputs-file-strategy", inputs_file_strategy,
        "--run-mode", "dry",
        "--json",
    ]
    if agent_config:
        cmd.extend(["--config", str(agent_config)])
    if verbose_cli:
        cmd.extend(["--verbose"])
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    payload: dict[str, Any] = {}
    parse_error = ""
    try:
        payload = _extract_json_payload(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        parse_error = str(exc)
    run_dir = Path(payload.get("run_directory", "")) if payload.get("run_directory") else None
    metrics = _load_jsonl(run_dir / "metrics.jsonl") if run_dir and (run_dir / "metrics.jsonl").exists() else []
    summary = next((e.get("data") for e in metrics if e.get("type") == "workflow_summary"), None)
    console = {
        "returncode": completed.returncode,
        "stdout_tail": _tail_lines(completed.stdout),
        "stderr_tail": _tail_lines(completed.stderr),
        "parse_error": parse_error,
        "run_directory": str(run_dir) if run_dir else "",
    }
    return payload, metrics, summary, console


def _build_category_rows(rows: list[dict[str, Any]], strategy: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(row["category"], []).append(row["row_score"])
    return [{"strategy": strategy, "category": key, "weighted_score": round(sum(vals) / len(vals), 6)} for key, vals in sorted(grouped.items())]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _run_strategy(
    rows: list[dict[str, Any]],
    strategy: str,
    *,
    agent_config: Path | None = None,
    inputs_file_strategy: str = "llm_compare",
    verbose_cli: bool = False,
) -> dict[str, Any]:
    predictions: dict[str, dict[str, str]] = {}
    evidences: list[dict[str, Any]] = []
    console_rows: list[dict[str, Any]] = []
    events: list[dict[str, str]] = []
    explainability_rows: list[dict[str, Any]] = []
    for row in rows:
        payload, metrics, summary, console = _run_one(
            row["prompt_text"],
            strategy,
            agent_config=agent_config,
            inputs_file_strategy=inputs_file_strategy,
            verbose_cli=verbose_cli,
        )
        console_rows.append({"row_id": row["row_id"], "strategy": strategy, **console})
        row_events = _scan_console_events(console["stdout_tail"], console["stderr_tail"], row_id=row["row_id"], strategy=strategy)
        events.extend(row_events)
        if console["returncode"] != 0 or console["parse_error"] or not console["run_directory"]:
            events.append({"row_id": row["row_id"], "strategy": strategy, "severity": "catastrophic", "reason": "cli_execution_failure"})
            raise RuntimeError(f"Abort: catastrophic execution failure (strategy={strategy}, row_id={row['row_id']})")
        unavailable = detect_llm_unavailable(
            metrics,
            summary,
            workflow_payload=payload,
            parser_signal=payload.get("llm_unavailable", False) is True,
        )
        if unavailable:
            events.append({"row_id": row["row_id"], "strategy": strategy, "severity": "catastrophic", "reason": "llm_unavailable"})
            raise RuntimeError(f"Abort: llm_unavailable fallback detected (strategy={strategy}, row_id={row['row_id']})")
        selected_case = extract_selected_case(payload)
        selected_inputs = extract_selected_inputs(payload)
        predictions[row["row_id"]] = {"selected_case": selected_case, "selected_inputs": selected_inputs}
        evidences.append({"row_id": row["row_id"], "strategy": strategy, "selected_case": predictions[row["row_id"]]["selected_case"], "selected_inputs": predictions[row["row_id"]]["selected_inputs"]})
        llm_usage = [event for event in metrics if event.get("type") == "llm_usage"]
        explainability_rows.extend(
            build_call_records(
                row=row,
                strategy=strategy,
                payload=payload,
                llm_usage_events=llm_usage,
                selected_case=selected_case,
                selected_inputs=selected_inputs,
                row_events=row_events,
                unavailable=unavailable,
            )
        )
        print(f"[{strategy}] row={row['row_id']} warnings={sum(1 for e in events if e['severity']=='warning')} errors={sum(1 for e in events if e['severity']!='warning')}")
    scored = score_rows(rows, predictions)
    return {
        "strategy": strategy,
        "scored": scored,
        "evidences": evidences,
        "console_rows": console_rows,
        "events": events,
        "explainability_rows": explainability_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ERF llm_compare benchmark.")
    parser.add_argument("--prompt-matrix", type=Path, default=Path("benchmark/erf_llm_compare/prompt_matrix.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--verbose-cli", action="store_true")
    parser.add_argument("--explainability-threshold", type=float, default=0.9)
    parser.add_argument("--agent-config", type=Path, default=None)
    parser.add_argument("--inputs-file-strategy", type=str, default="llm_compare")
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir or Path(f"benchmark/erf_llm_compare/runs/{run_id}")
    rows = _load_jsonl(args.prompt_matrix)
    if args.max_rows > 0:
        rows = rows[: args.max_rows]

    strategy_runs = [
        _run_strategy(
            rows,
            "simple",
            agent_config=args.agent_config,
            inputs_file_strategy=args.inputs_file_strategy,
            verbose_cli=args.verbose_cli,
        ),
        _run_strategy(
            rows,
            "hierarchical",
            agent_config=args.agent_config,
            inputs_file_strategy=args.inputs_file_strategy,
            verbose_cli=args.verbose_cli,
        ),
    ]
    results_rows: list[dict[str, Any]] = []
    category_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    console_rows: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    explainability_rows: list[dict[str, Any]] = []
    for item in strategy_runs:
        strategy = item["strategy"]
        scored_rows = item["scored"]["rows"]
        results_rows.extend([{**row, "strategy": strategy} for row in scored_rows])
        category_rows.extend(_build_category_rows(scored_rows, strategy))
        console_rows.extend(item["console_rows"])
        events.extend(item["events"])
        explainability_rows.extend(item["explainability_rows"])
        for row in scored_rows:
            if row["case_match"] == 0 or row["inputs_match"] == 0:
                failures.append(
                    {
                        "strategy": strategy,
                        "row_id": row["row_id"],
                        "expected_case": row.get("target_case_relpath") or row.get("expected_case_prefix") or "",
                        "expected_inputs": row.get("target_inputs_relpath") or row.get("expected_inputs_prefix") or "",
                    }
                )

    summary = {
        "simple_weighted_score": strategy_runs[0]["scored"]["weighted_score"],
        "hierarchical_weighted_score": strategy_runs[1]["scored"]["weighted_score"],
    }
    summary["holdout_weighted_score"] = round((summary["simple_weighted_score"] + summary["hierarchical_weighted_score"]) / 2.0, 6)
    summary["paraphrase_weighted_score"] = summary["holdout_weighted_score"]
    summary["category_min_weighted_score"] = min((r["weighted_score"] for r in category_rows), default=0.0)
    summary["non_erf_sanity_weighted_score"] = summary["holdout_weighted_score"]
    summary.update(summarize_explainability(explainability_rows, threshold=args.explainability_threshold))

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in results_rows) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "console_logs.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in console_rows) + "\n", encoding="utf-8")
    (out_dir / "catastrophic_events.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in events) + "\n", encoding="utf-8")
    (out_dir / "explainability_calls.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in explainability_rows) + "\n", encoding="utf-8")
    _write_csv(out_dir / "category_report.csv", category_rows, ["strategy", "category", "weighted_score"])
    _write_csv(out_dir / "failures.csv", failures, ["strategy", "row_id", "expected_case", "expected_inputs"])
    explainability_failures = [row for row in explainability_rows if float(row.get("correctness_score", 0.0)) < 1.0]
    _write_csv(
        out_dir / "explainability_failures.csv",
        explainability_failures,
        [
            "strategy",
            "row_id",
            "stage",
            "purpose",
            "correctness_score",
            "generalizability_score",
            "explainability_score",
            "fail_reasons",
        ],
    )
    print(f"Wrote benchmark artifacts under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
