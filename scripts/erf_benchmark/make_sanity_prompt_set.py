#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _row(prompt_family: str, prompt_text: str, variant: str, expected_case_prefix: str) -> dict[str, object]:
    row_id = hashlib.sha1(f"{prompt_family}|{variant}|{prompt_text}".encode("utf-8")).hexdigest()[:16]
    return {
        "row_id": row_id,
        "prompt_family": prompt_family,
        "category": "sanity",
        "wave_id": variant,
        "prompt_text": prompt_text,
        "expected_solver": "ERF",
        "expected_case_prefix": expected_case_prefix,
        "expected_inputs_prefix": f"{expected_case_prefix}/inputs",
        "strategy_targets": ["simple", "hierarchical"],
    }


def build_rows() -> list[dict[str, object]]:
    rows = [
        _row("abl", "Run an atmospheric boundary layer simulation for 10 steps", "base", "Exec/ABL"),
        _row("abl", "Set up an ABL run and stop after 10 timesteps", "p1", "Exec/ABL"),
        _row("abl", "Use ERF for a boundary-layer case with max_step=10", "p2", "Exec/ABL"),
        _row("squall_2d", "Run a 2D squall line simulation", "base", "Exec/CanonicalFlows/SquallLine_2D"),
        _row("squall_2d", "Set up ERF for a two-dimensional squall-line case", "p1", "Exec/CanonicalFlows/SquallLine_2D"),
        _row("squall_2d", "Use ERF canonical flows for a 2D squall line setup", "p2", "Exec/CanonicalFlows/SquallLine_2D"),
    ]
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate fixed sanity prompt set for ERF tuning.")
    parser.add_argument("--out", type=Path, default=Path("benchmark/erf_llm_compare/sanity_prompt_set.jsonl"))
    args = parser.parse_args()
    rows = build_rows()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

