#!/usr/bin/env python3
"""
Rename newly built schema files to preserve git history.

This script looks for versioned schema files under database/schemas/ and,
when a new version exists alongside a previously tracked version, it uses
git mv to rename the old file to the new name, then replaces the contents
with the newly generated file. This preserves rename history and keeps
diffs small.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SchemaGroup:
    solver: str
    kind: str  # "complete" or "schema"
    files: list[Path]


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def _git_status(path: Path, repo_root: Path) -> str:
    result = _run(["git", "status", "--porcelain", "--", str(path)], repo_root)
    return result.stdout.strip()


def _git_ls_files(glob_pattern: str, repo_root: Path) -> list[Path]:
    result = _run(["git", "ls-files", glob_pattern], repo_root)
    if result.returncode != 0:
        return []
    return [repo_root / line for line in result.stdout.splitlines() if line.strip()]


def _backup_if_modified(path: Path, repo_root: Path) -> None:
    status = _git_status(path, repo_root)
    if not status:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(path.suffix + f".bak.{stamp}")
    shutil.copy2(path, backup_path)
    print(f"[WARN] {path.name} has local changes; backup created: {backup_path.name}")


def _group_schemas(schema_dir: Path) -> list[SchemaGroup]:
    complete_files = [
        p for p in schema_dir.glob("*_complete_*.json")
        if not p.name.endswith("_complete_current.json")
    ]
    schema_files = list(schema_dir.glob("*_schema_*.json"))

    groups: dict[tuple[str, str], list[Path]] = {}
    for path in complete_files:
        solver = path.name.split("_complete_", 1)[0]
        groups.setdefault((solver, "complete"), []).append(path)
    for path in schema_files:
        solver = path.name.split("_schema_", 1)[0]
        groups.setdefault((solver, "schema"), []).append(path)

    return [SchemaGroup(solver=k[0], kind=k[1], files=v) for k, v in groups.items()]


def _select_newest(files: list[Path]) -> Path:
    # Break mtime ties by filename to keep target selection deterministic.
    return max(files, key=lambda p: (p.stat().st_mtime, p.name))


def _complete_schema_candidates(files: list[Path]) -> list[Path]:
    return [p for p in files if not p.name.endswith("_complete_current.json")]


def _sync_complete_current_symlink(schema_dir: Path, group: SchemaGroup) -> None:
    """Ensure <solver>_complete_current.json points at the newest complete schema."""
    if group.kind != "complete" or not group.files:
        return

    candidates = _complete_schema_candidates(group.files)
    if not candidates:
        return

    newest = _select_newest(candidates)
    current_link = schema_dir / f"{group.solver}_complete_current.json"
    desired_target = newest.name

    if current_link.is_symlink() and current_link.readlink().as_posix() == desired_target:
        return

    if current_link.exists() or current_link.is_symlink():
        current_link.unlink()
    current_link.symlink_to(desired_target)
    print(f"[OK] synced {current_link.name} -> {desired_target}")


def _rename_preserving_history(
    repo_root: Path,
    schema_dir: Path,
    group: SchemaGroup,
    allow_rename: bool,
) -> None:
    newest = _select_newest(group.files)
    tracked = _git_ls_files(str(schema_dir / newest.name), repo_root)
    if tracked:
        return

    tracked_group = _git_ls_files(
        str(schema_dir / f"{group.solver}_{group.kind}_*.json"),
        repo_root
    )
    if not tracked_group:
        return

    tracked_group = [
        p for p in tracked_group
        if p.exists()
        and p != newest
        and not p.name.endswith("_complete_current.json")
    ]
    if not tracked_group:
        return

    previous = _select_newest(tracked_group)

    if not allow_rename:
        print(
            f"[WARN] Found new {group.solver} {group.kind} schema '{newest.name}' "
            f"and previous tracked '{previous.name}'. "
            "Re-run with --singleton-rename to perform git mv."
        )
        return

    _backup_if_modified(previous, repo_root)

    temp_copy = newest.with_suffix(newest.suffix + ".new")
    shutil.copy2(newest, temp_copy)
    newest.unlink()

    mv_result = _run(["git", "mv", str(previous), str(newest)], repo_root)
    if mv_result.returncode != 0:
        print(f"[WARN] git mv failed for {previous.name} → {newest.name}: {mv_result.stderr.strip()}")
        temp_copy.rename(newest)
        return

    shutil.move(temp_copy, newest)
    print(f"[OK] git mv {previous.name} → {newest.name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rename new schema files to preserve git history."
    )
    parser.add_argument(
        "--schemas-dir",
        default="database/schemas",
        help="Directory containing schema JSON files",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--singleton-rename",
        action="store_true",
        help="Perform git mv to rename previous schema to the latest one",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    schema_dir = (repo_root / args.schemas_dir).resolve()
    if not schema_dir.exists():
        print(f"[ERROR] Schemas directory not found: {schema_dir}")
        return 1

    groups = _group_schemas(schema_dir)
    for group in groups:
        if len(group.files) >= 2:
            _rename_preserving_history(repo_root, schema_dir, group, args.singleton_rename)
            # Refresh file list after potential rename.
            refreshed_files = [
                p for p in schema_dir.glob(f"{group.solver}_{group.kind}_*.json")
                if p.exists()
            ]
            if group.kind == "complete":
                refreshed_files = _complete_schema_candidates(refreshed_files)
            group.files = refreshed_files
        _sync_complete_current_symlink(schema_dir, group)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
