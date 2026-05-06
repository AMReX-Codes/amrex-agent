#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass
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

NOT_FOUND = "NOT_FOUND"
RUN_ID_RE = re.compile(r"(20\d{6}T\d{6}Z)")


@dataclass(frozen=True)
class RowProvenance:
    run_id: str
    git_sha: str
    faiss_index_path: str
    faiss_index_size_kb: float | None
    faiss_index_modified: str | None
    faiss_index_hash_or_mtime: str | None
    frozen_input_file: str


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


def extract_iteration1_case(payload: dict[str, Any]) -> str:
    value = payload.get("iteration1_case")
    if isinstance(value, str) and value.strip():
        return _extract_exec_relpath(value, kind="case")
    history = payload.get("workflow_history", [])
    if not isinstance(history, list):
        return ""
    for entry in history:
        if not isinstance(entry, dict) or entry.get("node") != "architect":
            continue
        details = entry.get("details", {})
        if not isinstance(details, dict):
            continue
        selected = details.get("selected_case")
        if isinstance(selected, str) and selected.strip():
            return _extract_exec_relpath(selected, kind="case")
    return ""


def extract_case_reselection_fallback(payload: dict[str, Any]) -> bool:
    value = payload.get("case_reselection_fallback")
    if isinstance(value, bool):
        return value
    history = payload.get("workflow_history", [])
    if not isinstance(history, list):
        return False
    for entry in reversed(history):
        if not isinstance(entry, dict):
            continue
        details = entry.get("details", {})
        if not isinstance(details, dict):
            continue
        marker = details.get("case_reselection_fallback")
        if isinstance(marker, bool):
            return marker
    return False


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
    candidates: list[tuple[int, dict[str, Any]]] = []
    for idx, ch in enumerate(content):
        if ch != "{":
            continue
        try:
            obj, end = decoder.raw_decode(content[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            candidates.append((end, obj))
    if not candidates:
        raise json.JSONDecodeError("No JSON object found in stdout", content, 0)

    def _score(candidate: dict[str, Any], parsed_len: int) -> tuple[int, int]:
        key_bonus = 0
        for key, weight in (
            ("workflow_history", 8),
            ("run_directory", 6),
            ("run_dir", 6),
            ("selected_case", 4),
            ("modifications", 3),
            ("metrics", 2),
            ("history", 1),
        ):
            if key in candidate:
                key_bonus += weight
        return key_bonus, parsed_len

    best = max(candidates, key=lambda item: _score(item[1], item[0]))
    return best[1]


def _infer_run_directory(payload: dict[str, Any], stdout: str, stderr: str) -> str:
    for key in ("run_directory", "run_dir", "output_dir"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    output_text = "\n".join([stdout or "", stderr or ""])
    patterns = [
        r"Workflow history saved to\s+(\S+/workflow_history(?:_[0-9_]+)?\.json)",
        r"Files written to:\s*(\S+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, output_text)
        if not match:
            continue
        path = match.group(1)
        if path.endswith(".json"):
            return str(Path(path).parent)
        return path
    return ""


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


def _is_rate_limited_response(stdout: str, stderr: str) -> bool:
    text = f"{stdout}\n{stderr}".lower()
    return "429" in text or "too many requests" in text or "rate limit" in text


def _run_one(
    prompt: str,
    strategy: str,
    *,
    output_root: Path | None = None,
    agent_config: Path | None = None,
    inputs_file_strategy: str = "llm_compare",
    verbose_cli: bool = False,
    save_workflow: bool = False,
    save_transcript: bool = False,
    save_log: bool = False,
    max_rate_limit_retries: int = 1,
    flush_prints: bool = True,
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
    if output_root:
        cmd.extend(["--output-dir", str(output_root)])
    if verbose_cli:
        cmd.extend(["--verbose"])
    if save_workflow:
        cmd.extend(["--save-workflow"])
    if save_transcript:
        cmd.extend(["--save-transcript"])
    if save_log:
        cmd.extend(["--save-log"])
    completed: subprocess.CompletedProcess[str] | None = None
    retry_delay = 2.0
    rate_limit_retries = 0
    while True:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if rate_limit_retries >= max_rate_limit_retries:
            break
        if not _is_rate_limited_response(completed.stdout, completed.stderr):
            break
        rate_limit_retries += 1
        print(
            f"[{strategy}] retrying after 429/rate-limit response; retry={rate_limit_retries} wait={retry_delay:.2f}s",
            flush=flush_prints,
        )
        time.sleep(retry_delay)
        retry_delay = min(60.0, (retry_delay * 2.0) + random.uniform(0.0, 1.0))

    assert completed is not None
    payload: dict[str, Any] = {}
    parse_error = ""
    try:
        payload = _extract_json_payload(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        parse_error = str(exc)
    run_dir_text = _infer_run_directory(payload, completed.stdout, completed.stderr)
    run_dir = Path(run_dir_text) if run_dir_text else None
    metrics = _load_jsonl(run_dir / "metrics.jsonl") if run_dir and (run_dir / "metrics.jsonl").exists() else []
    summary = next((e.get("data") for e in metrics if e.get("type") == "workflow_summary"), None)
    console = {
        "returncode": completed.returncode,
        "stdout_tail": _tail_lines(completed.stdout),
        "stderr_tail": _tail_lines(completed.stderr),
        "parse_error": parse_error,
        "run_directory": str(run_dir) if run_dir else "",
        "rate_limit_retries": rate_limit_retries,
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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_yaml_or_json(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None

    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        payload = yaml.safe_load(text)
        if isinstance(payload, dict):
            return payload
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {}


def _resolve_faiss_path(config_path: Path | None) -> Path | None:
    if config_path is None or not config_path.exists():
        return None

    payload = _load_yaml_or_json(config_path)
    if not payload:
        return None

    raw_path = payload.get("faiss_db_path")
    if raw_path:
        path = Path(str(raw_path)).expanduser()
        if not path.is_absolute():
            path = (config_path.parent / path).resolve()
        return path

    # Use config defaults when faiss_db_path is omitted.
    provider = str(payload.get("embedding_provider") or payload.get("llm_provider") or "cborg")
    try:
        from src.config import resolve_database_path, resolve_faiss_db_path_for_provider

        faiss_root = resolve_database_path("faiss")
        return resolve_faiss_db_path_for_provider(faiss_root, provider).resolve()
    except Exception:
        return None


def _faiss_provenance(config_path: Path | None) -> dict[str, Any]:
    resolved = _resolve_faiss_path(config_path)
    if resolved is None:
        return {
            "path": None,
            "size_kb": None,
            "modified": None,
            "hash_or_mtime": None,
        }

    path = resolved.resolve()
    if not path.exists():
        return {
            "path": str(path),
            "size_kb": None,
            "modified": None,
            "hash_or_mtime": None,
        }

    if path.is_file():
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        return {
            "path": str(path),
            "size_kb": round(stat.st_size / 1024.0, 3),
            "modified": modified,
            "hash_or_mtime": f"sha256:{_sha256_file(path)}",
        }

    files = sorted(p for p in path.rglob("*") if p.is_file())
    if not files:
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        return {
            "path": str(path),
            "size_kb": 0.0,
            "modified": modified,
            "hash_or_mtime": f"mtime:{modified}",
        }

    digest = hashlib.sha256()
    total_bytes = 0
    max_mtime = 0.0
    for file_path in files:
        stat = file_path.stat()
        rel = str(file_path.relative_to(path))
        total_bytes += stat.st_size
        if stat.st_mtime > max_mtime:
            max_mtime = stat.st_mtime
        digest.update(rel.encode("utf-8"))
        digest.update(str(stat.st_size).encode("utf-8"))
        digest.update(str(int(stat.st_mtime)).encode("utf-8"))
    modified = datetime.fromtimestamp(max_mtime, tz=timezone.utc).isoformat()
    return {
        "path": str(path),
        "size_kb": round(total_bytes / 1024.0, 3),
        "modified": modified,
        "hash_or_mtime": f"tree-sha256:{digest.hexdigest()}",
    }


def _git_provenance(repo_root: Path) -> dict[str, Any]:
    sha = None
    dirty = None
    dirty_files: list[str] | None = None
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            text=True,
        ).strip()
    except Exception:
        sha = None
    try:
        status = subprocess.check_output(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            text=True,
        )
        dirty = bool(status.strip())
        dirty_files = []
        for line in status.splitlines():
            if not line.strip():
                continue
            # porcelain format: XY <path>
            dirty_files.append(line[3:] if len(line) > 3 else line)
    except Exception:
        dirty = None
    return {"sha": sha, "dirty": dirty, "dirty_files": dirty_files or []}


def _confirm_dirty_run(git_info: dict[str, Any], *, allow_dirty: bool) -> None:
    dirty = bool(git_info.get("dirty"))
    if not dirty:
        return

    dirty_files = git_info.get("dirty_files") or []
    print("WARNING: git working tree is dirty.", flush=True)
    if dirty_files:
        print("Dirty files:", flush=True)
        for file_path in dirty_files:
            print(f"  - {file_path}", flush=True)

    if allow_dirty:
        print("Proceeding because --allow-dirty is set.", flush=True)
        return

    print("Run paused: confirm dirty-run continuation.", flush=True)
    if not sys.stdin.isatty():
        raise RuntimeError(
            "Dirty working tree detected in non-interactive mode. Re-run with --allow-dirty to override."
        )
    answer = input("Proceed with dirty working tree? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        raise RuntimeError("Aborted by user due to dirty working tree.")


def _short_git_sha(git_info: dict[str, Any]) -> str:
    sha = str(git_info.get("sha") or "")
    short = sha[:7] if sha else "unknown"
    if git_info.get("dirty"):
        short += "+dirty"
    return short


def _infer_run_id(out_dir: Path) -> str:
    found = RUN_ID_RE.findall(str(out_dir))
    if found:
        return found[-1]
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _extract_hierarchical_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = payload.get("case_candidates")
    if isinstance(candidates, list) and candidates:
        return [item for item in candidates if isinstance(item, dict)]
    history = payload.get("workflow_history", [])
    if not isinstance(history, list):
        return []
    for entry in reversed(history):
        if not isinstance(entry, dict) or entry.get("node") != "architect":
            continue
        details = entry.get("details", {})
        if not isinstance(details, dict):
            continue
        raw = details.get("case_candidates")
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    return []


def _run_strategy(
    rows: list[dict[str, Any]],
    strategy: str,
    *,
    row_provenance: RowProvenance,
    strategy_output_root: Path | None = None,
    agent_config: Path | None = None,
    inputs_file_strategy: str = "llm_compare",
    verbose_cli: bool = False,
    save_workflow: bool = False,
    save_transcript: bool = False,
    save_log: bool = False,
    max_rate_limit_retries: int = 1,
    max_unavailable_attempts: int = 1,
    checkpoint_root: Path | None = None,
    checkpoint_prefix: str = "partial",
    checkpoint_every_row: bool = True,
    flush_prints: bool = True,
    continue_on_catastrophic: bool = False,
) -> dict[str, Any]:
    predictions: dict[str, dict[str, str]] = {}
    evidences: list[dict[str, Any]] = []
    console_rows: list[dict[str, Any]] = []
    events: list[dict[str, str]] = []
    explainability_rows: list[dict[str, Any]] = []
    hierarchical_candidates: list[dict[str, Any]] = []
    failed_rows = 0
    failed_sentinel = "__FAILED_ROW__"
    strategy_start = time.time()

    def _checkpoint() -> None:
        if checkpoint_root is None:
            return
        completed_rows = [row for row in rows if row["row_id"] in predictions]
        partial_scored = (
            score_rows(completed_rows, predictions)
            if completed_rows
            else {"rows": [], "weighted_score": 0.0}
        )
        prefix = f"{checkpoint_prefix}_{strategy}"
        _write_jsonl(checkpoint_root / f"{prefix}_results.jsonl", partial_scored["rows"])
        _write_jsonl(checkpoint_root / f"{prefix}_console_logs.jsonl", console_rows)
        _write_jsonl(checkpoint_root / f"{prefix}_catastrophic_events.jsonl", events)
        _write_jsonl(checkpoint_root / f"{prefix}_explainability_calls.jsonl", explainability_rows)
        _write_json_atomic(
            checkpoint_root / f"{prefix}_summary.json",
            {
                "strategy": strategy,
                "rows_completed": len(completed_rows),
                "rows_total": len(rows),
                "weighted_score": partial_scored["weighted_score"],
                "failed_rows": failed_rows,
                "elapsed_seconds": round(time.time() - strategy_start, 3),
                "max_rate_limit_retries": max_rate_limit_retries,
                "max_unavailable_attempts": max_unavailable_attempts,
            },
        )

    for row_idx, row in enumerate(rows):
        attempt = 0
        while True:
            attempt += 1
            payload, metrics, summary, console = _run_one(
                row["prompt_text"],
                strategy,
                output_root=strategy_output_root,
                agent_config=agent_config,
                inputs_file_strategy=inputs_file_strategy,
                verbose_cli=verbose_cli,
                save_workflow=save_workflow,
                save_transcript=save_transcript,
                save_log=save_log,
                max_rate_limit_retries=max_rate_limit_retries,
                flush_prints=flush_prints,
            )
            console_rows.append({"row_id": row["row_id"], "strategy": strategy, "row_index": row_idx, "attempt": attempt, **console})
            if strategy == "hierarchical":
                candidates = _extract_hierarchical_candidates(payload)
                hierarchical_candidates.append(
                    {
                        "row_id": row["row_id"],
                        "row_index": row_idx,
                        "attempt": attempt,
                        "selected_case": extract_selected_case(payload),
                        "candidates_top_n": candidates[:10],
                    }
                )
            row_events = _scan_console_events(console["stdout_tail"], console["stderr_tail"], row_id=row["row_id"], strategy=strategy)
            events.extend(row_events)
            if console["returncode"] != 0 or console["parse_error"]:
                events.append({"row_id": row["row_id"], "strategy": strategy, "severity": "catastrophic", "reason": "cli_execution_failure"})
                if not continue_on_catastrophic:
                    raise RuntimeError(f"Abort: catastrophic execution failure (strategy={strategy}, row_id={row['row_id']})")
                failed_rows += 1
                predictions[row["row_id"]] = {"selected_case": failed_sentinel, "selected_inputs": failed_sentinel}
                evidences.append(
                    {
                        "row_id": row["row_id"],
                        "strategy": strategy,
                        "warning": "catastrophic_execution_failure",
                        "attempt": attempt,
                        "run_directory": console.get("run_directory"),
                        "iteration1_case": extract_iteration1_case(payload) or NOT_FOUND,
                        "case_reselection_fallback": extract_case_reselection_fallback(payload),
                    }
                )
                print(
                    f"[{strategy}] catastrophic row={row['row_id']} -> marking failed sentinel and continuing",
                    flush=flush_prints,
                )
                break
            unavailable = detect_llm_unavailable(
                metrics,
                summary,
                workflow_payload=payload,
                parser_signal=payload.get("llm_unavailable", False) is True,
            )
            if unavailable:
                prompt_id = str(row.get("prompt_id") or row["row_id"])
                events.append(
                    {
                        "row_id": row["row_id"],
                        "strategy": strategy,
                        "severity": "error",
                        "reason": "llm_unavailable",
                        "row_index": str(row_idx),
                        "prompt_id": prompt_id,
                        "attempt": str(attempt),
                    }
                )
                print(
                    f"[{strategy}] llm_unavailable row_index={row_idx} prompt_id={prompt_id} "
                    f"attempt={attempt}/{max_unavailable_attempts}",
                    flush=flush_prints,
                )
                if attempt < max_unavailable_attempts:
                    continue
                failed_rows += 1
                predictions[row["row_id"]] = {"selected_case": failed_sentinel, "selected_inputs": failed_sentinel}
                evidences.append(
                    {
                        "row_id": row["row_id"],
                        "strategy": strategy,
                        "selected_case": failed_sentinel,
                        "selected_inputs": failed_sentinel,
                        "iteration1_case": extract_iteration1_case(payload) or NOT_FOUND,
                        "case_reselection_fallback": extract_case_reselection_fallback(payload),
                    }
                )
                llm_usage = [event for event in metrics if event.get("type") == "llm_usage"]
                explainability_rows.extend(
                    build_call_records(
                        row=row,
                        strategy=strategy,
                        payload=payload,
                        llm_usage_events=llm_usage,
                        selected_case=failed_sentinel,
                        selected_inputs=failed_sentinel,
                        row_events=row_events,
                        unavailable=True,
                    )
                )
                break
            selected_case = extract_selected_case(payload)
            selected_inputs = extract_selected_inputs(payload) or NOT_FOUND
            predictions[row["row_id"]] = {"selected_case": selected_case, "selected_inputs": selected_inputs}
            evidences.append(
                {
                    "row_id": row["row_id"],
                    "strategy": strategy,
                    "selected_case": predictions[row["row_id"]]["selected_case"],
                    "selected_inputs": predictions[row["row_id"]]["selected_inputs"],
                    "iteration1_case": extract_iteration1_case(payload) or NOT_FOUND,
                    "case_reselection_fallback": extract_case_reselection_fallback(payload),
                }
            )
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
                    unavailable=False,
                )
            )
            break
        print(
            f"[{strategy}] row={row['row_id']} warnings={sum(1 for e in events if e['severity']=='warning')} "
            f"errors={sum(1 for e in events if e['severity']!='warning')}",
            flush=flush_prints,
        )
        if checkpoint_every_row:
            _checkpoint()
    scored = score_rows(rows, predictions)
    if checkpoint_every_row:
        _checkpoint()
    return {
        "strategy": strategy,
        "scored": scored,
        "evidences": evidences,
        "console_rows": console_rows,
        "events": events,
        "explainability_rows": explainability_rows,
        "failed_rows": failed_rows,
        "hierarchical_candidates": hierarchical_candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ERF llm_compare benchmark.")
    parser.add_argument("--prompt-matrix", type=Path, default=Path("benchmark/erf_llm_compare/prompt_matrix.jsonl"))
    parser.add_argument(
        "--frozen-inputs",
        type=Path,
        default=None,
        help="Optional frozen benchmark inputs JSONL. If provided, it is used instead of --prompt-matrix.",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--strategy", choices=["simple", "hierarchical"], default=None)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--row-offset", type=int, default=0, help="Skip first N rows before evaluation.")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow execution when git working tree is dirty without interactive confirmation.",
    )
    parser.add_argument("--verbose-cli", action="store_true")
    parser.add_argument("--explainability-threshold", type=float, default=0.9)
    parser.add_argument("--agent-config", type=Path, default=None)
    parser.add_argument("--inputs-file-strategy", type=str, default="llm_compare")
    parser.add_argument("--save-workflow", action="store_true", help="Forward --save-workflow to amrex_agent runs.")
    parser.add_argument("--save-transcript", action="store_true", help="Forward --save-transcript to amrex_agent runs.")
    parser.add_argument("--save-log", action="store_true", help="Forward --save-log to amrex_agent runs.")
    parser.add_argument("--max-rate-limit-retries", type=int, default=1, help="Max retries for 429/rate-limit responses.")
    parser.add_argument("--max-unavailable-attempts", type=int, default=1, help="Max attempts when llm_unavailable is detected.")
    parser.add_argument("--checkpoint-prefix", type=str, default="partial", help="Prefix for incremental checkpoint files.")
    parser.add_argument("--no-checkpoint-every-row", action="store_true", help="Disable per-row checkpoint writes.")
    parser.add_argument("--flush-prints", action="store_true", help="Force flush progress prints.")
    parser.add_argument("--no-flush-prints", action="store_true", help="Disable force flush progress prints.")
    parser.add_argument(
        "--continue-on-catastrophic",
        action="store_true",
        help="Do not abort on catastrophic row failures; mark sentinel failure and continue.",
    )
    args = parser.parse_args()
    started_at = datetime.now(timezone.utc).isoformat()
    checkpoint_every_row = not args.no_checkpoint_every_row
    flush_prints = not args.no_flush_prints
    if args.flush_prints:
        flush_prints = True

    repo_root = Path(__file__).resolve().parents[2]
    git_info = _git_provenance(repo_root)
    _confirm_dirty_run(git_info, allow_dirty=bool(args.allow_dirty))

    default_run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir or Path(f"benchmark/erf_llm_compare/runs/{default_run_stamp}_benchmark")
    run_id = _infer_run_id(out_dir)
    strategy_roots: dict[str, Path]
    if args.out_dir:
        strategy_roots = {
            "simple": args.out_dir / "simple",
            "hierarchical": args.out_dir / "hierarchical",
        }
    else:
        base = Path("benchmark/erf_llm_compare/runs")
        strategy_roots = {
            "simple": base / f"{run_id}_simple",
            "hierarchical": base / f"{run_id}_hierarchical",
        }

    input_rows_path = args.frozen_inputs if args.frozen_inputs else args.prompt_matrix
    rows = _load_jsonl(input_rows_path)
    rows_have_strategy = any("strategy" in row for row in rows)

    faiss_info = _faiss_provenance(args.agent_config)
    row_provenance = RowProvenance(
        run_id=run_id,
        git_sha=_short_git_sha(git_info),
        faiss_index_path=str(faiss_info.get("path") or NOT_FOUND),
        faiss_index_size_kb=faiss_info.get("size_kb"),
        faiss_index_modified=faiss_info.get("modified"),
        faiss_index_hash_or_mtime=faiss_info.get("hash_or_mtime"),
        frozen_input_file=str(args.frozen_inputs.resolve()) if args.frozen_inputs else "LIVE_GENERATED",
    )

    selected_strategies = [args.strategy] if args.strategy else ["simple", "hierarchical"]
    strategy_runs = []
    for strategy in selected_strategies:
        strategy_rows = rows
        if rows_have_strategy:
            strategy_rows = [row for row in rows if str(row.get("strategy", "")).lower() == strategy]
        if args.row_offset > 0:
            strategy_rows = strategy_rows[args.row_offset :]
        if args.max_rows > 0:
            strategy_rows = strategy_rows[: args.max_rows]
        if not strategy_rows:
            raise RuntimeError(
                f"No rows to evaluate for strategy={strategy} from input file {input_rows_path}."
            )

        strategy_runs.append(
            _run_strategy(
                strategy_rows,
                strategy,
                row_provenance=row_provenance,
                strategy_output_root=strategy_roots[strategy],
                agent_config=args.agent_config,
                inputs_file_strategy=args.inputs_file_strategy,
                verbose_cli=args.verbose_cli,
                save_workflow=args.save_workflow,
                save_transcript=args.save_transcript,
                save_log=args.save_log,
                max_rate_limit_retries=max(0, args.max_rate_limit_retries),
                max_unavailable_attempts=max(1, args.max_unavailable_attempts),
                checkpoint_root=out_dir,
                checkpoint_prefix=args.checkpoint_prefix,
                checkpoint_every_row=checkpoint_every_row,
                flush_prints=flush_prints,
                continue_on_catastrophic=args.continue_on_catastrophic,
            )
        )
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

    runs_by_strategy = {item["strategy"]: item for item in strategy_runs}
    simple_scored = runs_by_strategy["simple"]["scored"]["weighted_score"] if "simple" in runs_by_strategy else 0.0
    hier_scored = runs_by_strategy["hierarchical"]["scored"]["weighted_score"] if "hierarchical" in runs_by_strategy else 0.0
    simple_failed = runs_by_strategy["simple"]["failed_rows"] if "simple" in runs_by_strategy else 0
    hier_failed = runs_by_strategy["hierarchical"]["failed_rows"] if "hierarchical" in runs_by_strategy else 0
    score_count = len(runs_by_strategy) if runs_by_strategy else 1

    summary = {
        "simple_weighted_score": simple_scored,
        "hierarchical_weighted_score": hier_scored,
        "simple_failed_rows": simple_failed,
        "hierarchical_failed_rows": hier_failed,
    }
    summary["total_failed_rows"] = summary["simple_failed_rows"] + summary["hierarchical_failed_rows"]
    summary["holdout_weighted_score"] = round((summary["simple_weighted_score"] + summary["hierarchical_weighted_score"]) / score_count, 6)
    summary["paraphrase_weighted_score"] = summary["holdout_weighted_score"]
    summary["category_min_weighted_score"] = min((r["weighted_score"] for r in category_rows), default=0.0)
    # NOTE: non_erf_sanity_weighted_score uses holdout score as placeholder.
    # Dedicated non-ERF split execution is deferred to follow-on benchmarking.
    # The 20-row non_erf_sanity.jsonl file exists and is reserved for that pass.
    summary["non_erf_sanity_weighted_score"] = summary["holdout_weighted_score"]
    summary.update(summarize_explainability(explainability_rows, threshold=args.explainability_threshold))
    summary["max_rate_limit_retries"] = max(0, args.max_rate_limit_retries)
    summary["max_unavailable_attempts"] = max(1, args.max_unavailable_attempts)
    summary["checkpoint_every_row"] = checkpoint_every_row
    summary["checkpoint_prefix"] = args.checkpoint_prefix
    summary["continue_on_catastrophic"] = bool(args.continue_on_catastrophic)

    hierarchical_candidates_rows: list[dict[str, Any]] = []
    if "hierarchical" in runs_by_strategy:
        hierarchical_candidates_rows = runs_by_strategy["hierarchical"].get("hierarchical_candidates", [])
    hierarchical_candidates_by_row = {entry.get("row_id"): entry for entry in hierarchical_candidates_rows}
    evidence_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for item in strategy_runs:
        strategy_name = str(item.get("strategy") or "")
        for evidence in item.get("evidences", []) or []:
            if not isinstance(evidence, dict):
                continue
            row_id = evidence.get("row_id")
            if not isinstance(row_id, str) or not row_id:
                continue
            evidence_by_key[(strategy_name, row_id)] = evidence

    enriched_results_rows: list[dict[str, Any]] = []
    for row in results_rows:
        strategy_name = str(row.get("strategy") or "")
        row_id = str(row.get("row_id") or "")
        evidence = evidence_by_key.get((strategy_name, row_id), {})
        selected_inputs = str(evidence.get("selected_inputs") or NOT_FOUND)
        enriched_row = {
            **row,
            "selected_case": evidence.get("selected_case", ""),
            "selected_inputs": selected_inputs,
            "iteration1_case": str(evidence.get("iteration1_case") or NOT_FOUND),
            "case_reselection_fallback": bool(evidence.get("case_reselection_fallback", False)),
            "run_id": row_provenance.run_id,
            "git_sha": row_provenance.git_sha,
            "faiss_index_path": row_provenance.faiss_index_path,
            "faiss_index_size_kb": row_provenance.faiss_index_size_kb,
            "faiss_index_modified": row_provenance.faiss_index_modified,
            "faiss_index_hash_or_mtime": row_provenance.faiss_index_hash_or_mtime,
            "frozen_input_file": row_provenance.frozen_input_file,
        }
        if strategy_name == "hierarchical":
            candidate_row = hierarchical_candidates_by_row.get(row_id, {})
            enriched_row.update(
                {
                    "hierarchical_selected_case": candidate_row.get("selected_case", ""),
                    "hierarchical_candidates_top_n": candidate_row.get("candidates_top_n", []),
                }
            )
        enriched_results_rows.append(enriched_row)

    input_checksum = _sha256_file(input_rows_path) if input_rows_path.exists() else None
    config_checksum = _sha256_file(args.agent_config) if args.agent_config and args.agent_config.exists() else None
    summary["audit"] = {
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "cli": {
            "argv": sys.argv,
            "cwd": os.getcwd(),
        },
        "inputs": {
            "row_source_file": str(input_rows_path),
            "row_source_sha256": input_checksum,
            "prompt_matrix": str(args.prompt_matrix),
            "frozen_inputs": str(args.frozen_inputs) if args.frozen_inputs else None,
            "agent_config": str(args.agent_config) if args.agent_config else None,
            "agent_config_sha256": config_checksum,
        },
        "git": git_info,
        "faiss_provenance": faiss_info,
        "input_provenance": {
            "frozen_file": row_provenance.frozen_input_file,
        },
        "artifacts": {
            "summary": "summary.json",
            "results": "results.jsonl",
            "category_report": "category_report.csv",
            "failures": "failures.csv",
            "console_logs": "console_logs.jsonl",
            "catastrophic_events": "catastrophic_events.jsonl",
            "explainability_calls": "explainability_calls.jsonl",
            "explainability_failures": "explainability_failures.csv",
        },
        "hierarchical_candidates": {
            "embedded_in": "results.jsonl",
            "rows_with_candidates": len(hierarchical_candidates_rows),
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in enriched_results_rows) + "\n", encoding="utf-8")
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
