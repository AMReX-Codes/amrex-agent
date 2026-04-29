#!/usr/bin/env python3
"""Generate benchmark_v2 JSONL datasets by crawling a solver source tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path


def _is_inputs_file(name: str) -> bool:
    if name == "input":
        return True
    if name.startswith("input."):
        return True
    if name.startswith("input_"):
        return True
    if name.startswith("inputs_"):
        return True
    if name.startswith("inputs."):
        return True
    if name.startswith("inputs") and "." not in name:
        return True
    return False


def _category_from_relpath(relpath: Path) -> str:
    parts = relpath.parts
    if "Exec" in parts:
        idx = parts.index("Exec")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return "uncategorized"


def _row_for_inputs(relpath: Path, solver_name: str) -> dict[str, object]:
    target_inputs_relpath = relpath.as_posix()
    target_case_relpath = relpath.parent.as_posix()
    target_inputs_filename = relpath.name
    row_id = hashlib.sha256(target_inputs_relpath.encode("utf-8")).hexdigest()[:16]
    return {
        "row_id": row_id,
        "prompt_text": f"Use {solver_name} case {target_case_relpath} with {target_inputs_filename}",
        "target_case_relpath": target_case_relpath,
        "target_inputs_filename": target_inputs_filename,
        "target_inputs_relpath": target_inputs_relpath,
        "category": _category_from_relpath(relpath),
        "wave_id": "wave0",
        "strategy_targets": ["simple", "hierarchical"],
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def generate(source_root: Path, out_dir: Path, seed: int, solver_name: str | None = None) -> int:
    if not source_root.exists() or not source_root.is_dir():
        raise FileNotFoundError(f"Source root not found or not a directory: {source_root}")

    solver_label = solver_name or source_root.name

    rows: list[dict[str, object]] = []
    skipped: list[tuple[str, str]] = []
    pruned_case_dirs: list[str] = []

    exec_root = source_root / "Exec"
    if not exec_root.exists() or not exec_root.is_dir():
        raise FileNotFoundError(f"Source Exec root not found or not a directory: {exec_root}")

    for dirpath_str, dirnames, filenames in os.walk(exec_root, topdown=True):
        dirpath = Path(dirpath_str)
        rel_dir = dirpath.relative_to(source_root)
        rel_dir_text = rel_dir.as_posix()

        # Always prune .Exec_dev branches.
        kept_dirs: list[str] = []
        for d in dirnames:
            rel_child = f"{rel_dir_text}/{d}" if rel_dir_text != "." else d
            if ".Exec_dev" in rel_child:
                skipped.append((rel_child, "path contains .Exec_dev"))
            else:
                kept_dirs.append(d)
        dirnames[:] = kept_dirs

        inputs_in_dir: list[str] = [name for name in filenames if _is_inputs_file(name)]

        # Leaf-preferred, no-recurse-into-case:
        # if this directory is a case (has inputs files), record these files and stop descending.
        if inputs_in_dir:
            for name in sorted(inputs_in_dir):
                rel_file = (rel_dir / name) if rel_dir_text != "." else Path(name)
                rel_file_text = rel_file.as_posix()
                if ".Exec_dev" in rel_file_text:
                    skipped.append((rel_file_text, "path contains .Exec_dev"))
                    continue
                # Skip files directly under Exec/ (no top-level category directory).
                rel_from_exec = rel_file.relative_to(Path("Exec"))
                if len(rel_from_exec.parts) < 2:
                    skipped.append((rel_file_text, "inputs file directly under Exec (no category directory)"))
                    continue
                rows.append(_row_for_inputs(rel_file, solver_label))

            if dirnames:
                pruned_case_dirs.append(rel_dir_text)
                for child in dirnames:
                    child_path = f"{rel_dir_text}/{child}" if rel_dir_text != "." else child
                    skipped.append((child_path, "pruned: parent directory is a case (contains inputs files)"))
                dirnames[:] = []
            continue

    rows.sort(key=lambda r: str(r["target_inputs_relpath"]))
    by_category: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_category[str(row["category"])].append(row)

    rng = random.Random(seed)
    train_rows: list[dict[str, object]] = []
    holdout_rows: list[dict[str, object]] = []
    for category in sorted(by_category):
        bucket = list(by_category[category])
        rng.shuffle(bucket)
        n = len(bucket)
        holdout_n = int(round(n * 0.2))
        if holdout_n > n:
            holdout_n = n
        holdout = bucket[:holdout_n]
        train = bucket[holdout_n:]
        holdout_rows.extend(holdout)
        train_rows.extend(train)

    train_rows.sort(key=lambda r: str(r["target_inputs_relpath"]))
    holdout_rows.sort(key=lambda r: str(r["target_inputs_relpath"]))

    _write_jsonl(out_dir / "prompt_matrix.jsonl", rows)
    _write_jsonl(out_dir / "train.jsonl", train_rows)
    _write_jsonl(out_dir / "holdout.jsonl", holdout_rows)

    cat_counts = Counter(str(r["category"]) for r in rows)
    print(f"Total rows: {len(rows)}")
    print("Rows per category:")
    for cat in sorted(cat_counts):
        print(f"  {cat}: {cat_counts[cat]}")
    print("Rows per split:")
    print(f"  prompt_matrix: {len(rows)}")
    print(f"  train: {len(train_rows)}")
    print(f"  holdout: {len(holdout_rows)}")
    print("Skipped paths:")
    if skipped:
        for path, reason in sorted(skipped):
            print(f"  {path} :: {reason}")
    else:
        print("  none")

    print("Pruned case directory example:")
    if pruned_case_dirs:
        print(f"  {sorted(pruned_case_dirs)[0]}")
    else:
        print("  none")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate benchmark_v2 JSONL files by crawling a solver tree."
    )
    parser.add_argument(
        "--erf-root",
        "--source",
        dest="source_root",
        type=Path,
        default=Path("/home/jmsexton/codes/worktree_sandbox/ERF"),
        help="Absolute path to solver repository root.",
    )
    parser.add_argument(
        "--out-dir",
        "--output",
        dest="out_dir",
        type=Path,
        default=Path("/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2"),
        help="Output directory for generated JSONL files.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for stratified split shuffling.",
    )
    parser.add_argument(
        "--solver-name",
        type=str,
        default=None,
        help="Optional solver label used in prompt text (default: source root directory name).",
    )
    args = parser.parse_args()
    return generate(
        args.source_root.resolve(),
        args.out_dir.resolve(),
        args.seed,
        solver_name=args.solver_name,
    )


if __name__ == "__main__":
    raise SystemExit(main())
