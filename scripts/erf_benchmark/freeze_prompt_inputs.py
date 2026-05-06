#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _expand_prompt_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frozen_at = datetime.now(timezone.utc).isoformat()
    expanded: list[dict[str, Any]] = []
    for row in rows:
        explicit_strategy = row.get("strategy")
        if isinstance(explicit_strategy, str) and explicit_strategy:
            strategies = [explicit_strategy]
        else:
            targets = row.get("strategy_targets")
            if isinstance(targets, list) and targets:
                strategies = [str(token) for token in targets if str(token).strip()]
            else:
                strategies = ["simple", "hierarchical"]

        for strategy in strategies:
            frozen_row = dict(row)
            frozen_row["strategy"] = strategy
            frozen_row["frozen_at"] = frozen_at
            expanded.append(frozen_row)

    expanded.sort(
        key=lambda row: (
            str(row.get("strategy", "")),
            str(row.get("target_case_relpath", "")),
            str(row.get("target_inputs_relpath", "")),
            str(row.get("row_id", "")),
        )
    )
    return expanded


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze prompt matrix rows into explicit per-strategy JSONL rows.")
    parser.add_argument("--prompt-matrix", type=Path, required=True, help="Source prompt matrix JSONL.")
    parser.add_argument("--out", type=Path, required=True, help="Output frozen JSONL path.")
    parser.add_argument("--code", type=str, default="", help="Optional label for status output.")
    args = parser.parse_args()

    rows = _load_jsonl(args.prompt_matrix)
    frozen_rows = _expand_prompt_rows(rows)
    _write_jsonl(args.out, frozen_rows)

    strategy_counts = Counter(str(row.get("strategy", "")) for row in frozen_rows)
    label = f"[{args.code}] " if args.code else ""
    print(f"{label}wrote {len(frozen_rows)} frozen rows to {args.out}")
    for strategy, count in sorted(strategy_counts.items()):
        print(f"{label}  {strategy}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
