#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def discover_erf_inputs(erf_root: Path) -> list[Path]:
    return sorted(p.relative_to(erf_root) for p in (erf_root / "Exec").rglob("inputs*") if p.is_file())


def _wave_prompt(case_rel: str, input_name: str, wave_id: str) -> str:
    base = f"Use ERF case {case_rel} with {input_name}"
    if wave_id == "wave1":
        return f"Select the ERF setup matching {case_rel}; prefer inputs file {input_name}."
    if wave_id == "wave2":
        return f"Configure ERF for the {case_rel} scenario and choose {input_name} as baseline inputs."
    return base


def _category_from_relpath(relpath: Path) -> str:
    parts = relpath.parts
    return parts[1] if len(parts) > 2 else "Uncategorized"


def build_prompt_matrix_rows(inputs_relpaths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for relpath in sorted(inputs_relpaths):
        case_rel = relpath.parent.as_posix()
        input_name = relpath.name
        input_rel = relpath.as_posix()
        for wave_id in ("wave0", "wave1", "wave2"):
            row_id = hashlib.sha1(f"{case_rel}|{input_name}|{wave_id}".encode("utf-8")).hexdigest()[:16]
            rows.append(
                {
                    "row_id": row_id,
                    "target_case_relpath": case_rel,
                    "target_inputs_relpath": input_rel,
                    "target_inputs_filename": input_name,
                    "category": _category_from_relpath(relpath),
                    "wave_id": wave_id,
                    "prompt_text": _wave_prompt(case_rel, input_name, wave_id),
                    "strategy_targets": ["simple", "hierarchical"],
                }
            )
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _build_manifest(rows: list[dict], erf_root: Path) -> dict:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "erf_root": str(erf_root),
        "row_count": len(rows),
        "unique_inputs": len({row["target_inputs_relpath"] for row in rows}),
        "waves": ["wave0", "wave1", "wave2"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ERF llm_compare prompt matrix.")
    parser.add_argument("--erf-root", type=Path, default=Path("../ERF"))
    parser.add_argument("--out-dir", type=Path, default=Path("benchmark/erf_llm_compare"))
    args = parser.parse_args()

    inputs_rel = discover_erf_inputs(args.erf_root)
    rows = build_prompt_matrix_rows(inputs_rel)
    _write_jsonl(args.out_dir / "prompt_matrix.jsonl", rows)
    (args.out_dir / "manifest.json").write_text(
        json.dumps(_build_manifest(rows, args.erf_root), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} rows to {args.out_dir / 'prompt_matrix.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

