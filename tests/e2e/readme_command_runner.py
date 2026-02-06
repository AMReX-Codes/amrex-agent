from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Callable

from tests.e2e.readme_command_registry import extract_readme_commands


def collect_commands_by_file(repo_root: Path) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for entry in extract_readme_commands(repo_root):
        grouped.setdefault(entry["path"], []).append(entry)
    for entries in grouped.values():
        entries.sort(key=lambda item: (item.get("start_line", 0), item["index"]))
    return grouped


def run_commands_by_file(
    repo_root: Path,
    file_filter: list[str] | None = None,
    dry_run: bool = False,
    timeout_seconds: int | None = None,
    stop_on_failure: bool = False,
    entry_filter: Callable[[dict], bool] | None = None,
    command_transform: Callable[[str], str] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, list[dict]]:
    grouped = collect_commands_by_file(repo_root)
    results: dict[str, list[dict]] = {}

    for path, entries in grouped.items():
        if file_filter and path not in file_filter:
            continue
        results[path] = []
        for entry in entries:
            if entry_filter and not entry_filter(entry):
                continue
            command = entry["text"]
            if command_transform:
                command = command_transform(command)
            if dry_run:
                results[path].append(
                    {
                        "id": entry["id"],
                        "status": "dry_run",
                        "command": command,
                    }
                )
                continue
            result = _run_shell(entry, command, repo_root, env, timeout_seconds)
            results[path].append(result)
            if stop_on_failure and result["status"] in {"failed", "timeout"}:
                return results

    return results


def _run_shell(
    entry: dict,
    command: str,
    repo_root: Path,
    env: dict[str, str] | None,
    timeout_seconds: int | None,
) -> dict:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        result = subprocess.run(
            ["bash", "-lc", command],
            cwd=repo_root,
            env=merged_env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "id": entry["id"],
            "status": "timeout",
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "command": command,
        }

    return {
        "id": entry["id"],
        "status": "ok" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": command,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run README command blocks grouped by file.")
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="Run commands from a specific README path (relative to repo root).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List commands without executing them.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="Per-command timeout in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    results = run_commands_by_file(
        repo_root,
        file_filter=args.files,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout_seconds,
    )
    failures = 0
    for path, entries in results.items():
        for entry in entries:
            if entry["status"] in {"failed", "timeout"}:
                failures += 1
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
