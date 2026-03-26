"""Benchmark runners for case suites and model comparisons."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from types import SimpleNamespace

import yaml
from jsonschema import Draft202012Validator


# ===== Shared helpers =====

def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_data(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix in {".yaml", ".yml"}:
        return _load_yaml(path)
    raise ValueError(f"Unsupported config type: {path}")


# ===== Case suite runner =====

def validate_case_files(schema_path: Path, cases_dir: Path) -> list[str]:
    schema = _load_yaml(schema_path)
    errors: list[str] = []
    validator = Draft202012Validator(schema)
    for path in sorted(cases_dir.glob("*.yaml")):
        data = _load_yaml(path)
        for error in sorted(validator.iter_errors(data), key=lambda err: list(err.path)):
            location = "/".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{path}: {location}: {error.message}")
        solver = data.get("solver")
        for case in data.get("cases", []):
            case_solver = case.get("solver")
            if solver and case_solver and solver != case_solver:
                errors.append(
                    f"{path}: cases/{case.get('id', 'unknown')}: solver {case_solver} "
                    f"does not match suite solver {solver}"
                )
    return errors


def collect_cases(cases_dir: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(cases_dir.glob("*.yaml")):
        data = _load_yaml(path)
        for case in data.get("cases", []):
            case = dict(case)
            case["_suite_id"] = data.get("suite_id")
            case["_suite_solver"] = data.get("solver")
            case["_source"] = str(path)
            cases.append(case)
    return cases


def filter_cases(
    cases: list[dict[str, Any]], solver: str | None, case_ids: list[str]
) -> list[dict[str, Any]]:
    filtered = cases
    if solver:
        filtered = [case for case in filtered if case.get("solver") == solver]
    if case_ids:
        wanted = set(case_ids)
        filtered = [case for case in filtered if case.get("id") in wanted]
    return filtered


def expand_case_runs(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for case in cases:
        for size in case["scaling"]["sizes"]:
            runs.append(
                {
                    "case_id": case["id"],
                    "solver": case["solver"],
                    "case_name": case["case_name"],
                    "size_label": size["label"],
                    "grid": size["grid"],
                    "amr_levels": size["amr_levels"],
                    "source": case["_source"],
                }
            )
    return runs


def init_case_run_state(cases: list[dict[str, Any]]) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).isoformat()
    state = {
        "schema_version": 1,
        "run_id": f"run_{created_at.replace(':', '').replace('-', '')}",
        "created_at": created_at,
        "cases": {},
    }
    for case in cases:
        sizes = {}
        for size in case["scaling"]["sizes"]:
            sizes[size["label"]] = {
                "grid": size["grid"],
                "amr_levels": size["amr_levels"],
                "status": "pending",
            }
        state["cases"][case["id"]] = {
            "solver": case["solver"],
            "case_name": case["case_name"],
            "source": case["_source"],
            "status": "pending",
            "sizes": sizes,
        }
    return state


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_state(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_command(case: dict[str, Any], size: dict[str, Any]) -> str | None:
    run_info = case.get("run") or {}
    command = run_info.get("command")
    if not command:
        return None
    return command.format(
        solver=case.get("solver"),
        case_dir=case.get("case_dir"),
        inputs=case.get("inputs"),
        grid=size.get("grid"),
        label=size.get("label"),
    )


def _execute_case(case: dict[str, Any], size: dict[str, Any], dry_run: bool) -> tuple[str, str]:
    command = _format_command(case, size)
    if not command:
        return "skipped", "no command defined"
    if dry_run:
        return "planned", command

    working_dir = (case.get("run") or {}).get("working_dir") or case.get("case_dir")
    result = subprocess.run(command, shell=True, cwd=working_dir)
    if result.returncode == 0:
        return "complete", command
    return "failed", command


def run_case_suite(
    cases: list[dict[str, Any]],
    run_dir: Path,
    resume: bool,
    dry_run: bool,
) -> int:
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "run_state.json"

    if resume:
        if not state_path.exists():
            raise FileNotFoundError(f"Missing run state at {state_path}")
        state = _load_state(state_path)
    else:
        state = init_case_run_state(cases)
        _write_state(state_path, state)

    for case in cases:
        case_state = state["cases"].get(case["id"])
        if not case_state:
            continue
        for size in case["scaling"]["sizes"]:
            size_state = case_state["sizes"][size["label"]]
            if size_state["status"] == "complete":
                continue
            status, detail = _execute_case(case, size, dry_run)
            size_state["status"] = status
            size_state["detail"] = detail
            if status == "failed":
                case_state["status"] = "failed"
                _write_state(state_path, state)
                return 1
        if all(entry["status"] == "complete" for entry in case_state["sizes"].values()):
            case_state["status"] = "complete"
        elif all(entry["status"] == "skipped" for entry in case_state["sizes"].values()):
            case_state["status"] = "skipped"
        else:
            case_state["status"] = "in_progress"
        _write_state(state_path, state)

    return 0


# ===== Multi-model benchmark runner =====

def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = {**base[key], **value}
        else:
            merged[key] = value
    return merged


def _ensure_prompt_entry(entry: Any, index: int) -> dict[str, Any]:
    if isinstance(entry, str):
        return {"id": f"prompt_{index:03d}", "prompt": entry}
    if isinstance(entry, dict):
        prompt_id = entry.get("id") or f"prompt_{index:03d}"
        return {
            "id": prompt_id,
            "prompt": entry.get("prompt"),
            "prompt_path": entry.get("prompt_path"),
            "case_id": entry.get("case_id"),
            "solver": entry.get("solver"),
            "difficulty_tier": entry.get("difficulty_tier"),
            "novelty_tier": entry.get("novelty_tier"),
        }
    raise ValueError(f"Invalid prompt entry at index {index}: {entry!r}")


def _load_prompt_text(entry: dict[str, Any]) -> str | None:
    prompt = entry.get("prompt")
    if prompt:
        return str(prompt)
    prompt_path = entry.get("prompt_path")
    if prompt_path:
        path = Path(prompt_path)
        return path.read_text().strip()
    return None


def _build_config_for_model(model: dict[str, Any], output_dir: Path) -> Path | None:
    base_config = {}
    config_path = model.get("config_path")
    if config_path:
        base_config = _load_data(Path(config_path))
    overrides = model.get("overrides") or {}
    merged = _merge_dicts(base_config, overrides)
    if not merged:
        return None
    config_dir = output_dir / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    model_id = model.get("id", "model")
    model_slug = _slugify(model_id)
    config_file = config_dir / f"{model_slug}.json"
    config_file.write_text(json.dumps(merged, indent=2))
    return config_file


def _build_command(
    config_path: Path | None,
    prompt_entry: dict[str, Any],
    output_dir: Path,
    run_args: dict[str, Any],
    benchmark_context: Path | None,
) -> list[str]:
    cmd = [os.environ.get("AMREX_AGENT_PYTHON", "python"), "amrex_agent.py", "--json"]
    if prompt_entry.get("prompt"):
        cmd.extend(["--prompt", prompt_entry["prompt"]])
    elif prompt_entry.get("prompt_path"):
        cmd.extend(["--prompt-path", prompt_entry["prompt_path"]])
    else:
        raise ValueError(f"Prompt entry missing prompt text/path: {prompt_entry!r}")

    if config_path:
        cmd.extend(["--config", str(config_path)])
    cmd.extend(["--output-dir", str(output_dir)])
    if benchmark_context:
        cmd.extend(["--benchmark-context", str(benchmark_context)])

    flag_map = {
        "run_mode": "--run-mode",
        "environment": "--environment",
        "inputs_file_strategy": "--inputs-file-strategy",
        "remap_strategy": "--remap-strategy",
        "inputs_file_override": "--inputs-file-override",
        "baseline_override": "--baseline-override",
        "baseline_switch_after_retries": "--baseline-switch-after-retries",
        "llm_gate_strategy": "--llm-gate-strategy",
        "indexing_strategy": "--indexing-strategy",
        "run_ntasks": "--run-ntasks",
    }
    for key, flag in flag_map.items():
        value = run_args.get(key)
        if value is not None:
            cmd.extend([flag, str(value)])

    if run_args.get("run_serial"):
        cmd.append("--run-serial")
    if run_args.get("dry_run"):
        cmd.append("--dry-run")
    if run_args.get("preconfirm"):
        cmd.append("--preconfirm")
    if run_args.get("save_workflow"):
        cmd.append("--save-workflow")
    if run_args.get("save_transcript"):
        cmd.append("--save-transcript")
    if run_args.get("save_log"):
        cmd.append("--save-log")
    if run_args.get("verbose"):
        cmd.append("--verbose")

    extra_args = run_args.get("extra_args") or []
    if extra_args:
        cmd.extend([str(arg) for arg in extra_args])

    return cmd


def _write_jsonl(path: Path, payload: dict[str, Any], config: Any | None = None) -> None:
    with path.open("a", encoding="utf-8") as handle:
        if config is not None:
            from src.utils.privacy import sanitize_payload

            payload = sanitize_payload(payload, config=config)
        handle.write(json.dumps(payload, default=str))
        handle.write("\n")


def _privacy_config(run_args: dict[str, Any]) -> Any | None:
    mode = run_args.get("privacy_mode")
    if not mode:
        return None
    return SimpleNamespace(
        privacy_mode=mode,
        privacy_scrubber=run_args.get("privacy_scrubber", "builtin"),
        privacy_hash_salt=run_args.get("privacy_hash_salt"),
    )


def _slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def run_model_benchmark(config_path: Path, output_dir: Path, run_name: str | None) -> dict[str, Any]:
    bench_config = _load_data(config_path)

    prompts_raw = bench_config.get("prompts") or []
    if not prompts_raw:
        raise ValueError("Benchmark config must include prompts.")
    models = bench_config.get("models") or []
    if not models:
        raise ValueError("Benchmark config must include models.")

    run_args = bench_config.get("run_args") or {}
    env_common = bench_config.get("env") or {}
    privacy_config = _privacy_config(run_args)

    run_name = run_name or datetime.now().strftime("bench_%Y%m%d_%H%M%S")
    run_dir = output_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = run_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_name": run_name,
        "created_at": datetime.now().isoformat(),
        "benchmark_config": str(config_path),
        "models": [],
        "prompts": [],
        "run_args": run_args,
        "env_keys": sorted(set(env_common.keys())),
    }

    prompt_entries = []
    for idx, entry in enumerate(prompts_raw, start=1):
        normalized = _ensure_prompt_entry(entry, idx)
        prompt_text = _load_prompt_text(normalized)
        if not prompt_text:
            raise ValueError(f"Prompt entry missing text/path: {normalized!r}")
        prompt_entries.append({**normalized, "prompt": prompt_text})
        prompt_manifest = {
            "id": normalized["id"],
            "prompt_path": normalized.get("prompt_path"),
            "prompt_excerpt": prompt_text[:160],
        }
        if privacy_config is not None:
            from src.utils.privacy import sanitize_payload

            prompt_manifest = sanitize_payload(prompt_manifest, config=privacy_config)
        manifest["prompts"].append(prompt_manifest)

    raw_metrics_path = run_dir / "benchmark_runs.jsonl"

    for model in models:
        model_id = model.get("id")
        if not model_id:
            raise ValueError("Each model must include an id.")
        model_slug = _slugify(model_id)
        model_env = dict(env_common)
        model_env.update(model.get("env") or {})
        provider = (model.get("overrides") or {}).get("llm_provider")

        model_config_path = _build_config_for_model(model, run_dir)
        model_manifest = {
            "id": model_id,
            "slug": model_slug,
            "config_path": str(model_config_path) if model_config_path else None,
            "config_source": model.get("config_path"),
            "override_keys": sorted((model.get("overrides") or {}).keys()),
            "env_keys": sorted((model.get("env") or {}).keys()),
        }
        if privacy_config is not None:
            from src.utils.privacy import sanitize_payload

            model_manifest = sanitize_payload(model_manifest, config=privacy_config)
        manifest["models"].append(model_manifest)

        for prompt in prompt_entries:
            prompt_id = prompt["id"]
            prompt_dir = runs_dir / model_slug / prompt_id
            prompt_dir.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env.update({k: str(v) for k, v in model_env.items()})
            benchmark_context = prompt_dir / "benchmark_context.json"
            context_payload = {
                "prompt_id": prompt_id,
                "prompt_excerpt": prompt["prompt"][:160],
                "case_id": prompt.get("case_id"),
                "solver": prompt.get("solver"),
                "difficulty_tier": prompt.get("difficulty_tier"),
                "novelty_tier": prompt.get("novelty_tier"),
                "model_id": model_id,
                "provider": provider,
            }
            if privacy_config is not None:
                from src.utils.privacy import sanitize_payload

                context_payload = sanitize_payload(context_payload, config=privacy_config)
            benchmark_context.write_text(json.dumps(context_payload, indent=2, default=str))

            cmd = _build_command(model_config_path, prompt, prompt_dir, run_args, benchmark_context)

            started_at = datetime.now().isoformat()
            start_time = time.time()
            result_data: dict[str, Any] | None = None
            error = None
            exit_code = None
            stdout = ""
            stderr = ""
            try:
                timeout = run_args.get("timeout_seconds")
                proc = subprocess.run(
                    cmd,
                    cwd=Path(__file__).resolve().parents[1],
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=timeout,
                )
                exit_code = proc.returncode
                stdout = proc.stdout
                stderr = proc.stderr
                if stdout.strip():
                    result_data = json.loads(stdout)
            except subprocess.TimeoutExpired as exc:
                error = f"timeout_after_{exc.timeout}s"
                stdout = exc.stdout or ""
                stderr = exc.stderr or ""
            except json.JSONDecodeError as exc:
                error = f"json_parse_failed: {exc}"
            except Exception as exc:
                error = f"runner_error: {exc}"

            ended_at = datetime.now().isoformat()
            duration = time.time() - start_time

            analysis_report = None
            run_directory = None
            job_status = None
            selected_case = None
            if result_data:
                run_directory = result_data.get("run_directory")
                job_status = result_data.get("job_status")
                selected_case = result_data.get("selected_case")
                analysis_report = result_data.get("analysis_report")

            if not analysis_report and run_directory:
                report_path = Path(run_directory) / "analysis_report.json"
                if report_path.exists():
                    try:
                        analysis_report = json.loads(report_path.read_text())
                    except Exception:
                        analysis_report = None

            record = {
                "model_id": model_id,
                "prompt_id": prompt_id,
                "prompt_excerpt": prompt["prompt"][:200],
                "job_status": job_status or "unknown",
                "analysis_status": (analysis_report or {}).get("status"),
                "analysis_performance": (analysis_report or {}).get("performance"),
                "analysis_issues": (analysis_report or {}).get("issues"),
                "run_directory": run_directory,
                "selected_case": selected_case,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": duration,
                "exit_code": exit_code,
                "error": error,
                "stderr_excerpt": stderr[:2000] if stderr else None,
            }
            _write_jsonl(raw_metrics_path, record, config=privacy_config)

            per_run = prompt_dir / "result.json"
            per_run_payload = {
                "command": cmd,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "result": result_data,
                "record": record,
            }
            if privacy_config is not None:
                from src.utils.privacy import sanitize_payload

                per_run_payload = sanitize_payload(per_run_payload, config=privacy_config)
            per_run.write_text(json.dumps(per_run_payload, indent=2, default=str))

    if privacy_config is not None:
        from src.utils.privacy import sanitize_payload

        manifest = sanitize_payload(manifest, config=privacy_config)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return {"run_dir": str(run_dir), "metrics": str(raw_metrics_path)}
