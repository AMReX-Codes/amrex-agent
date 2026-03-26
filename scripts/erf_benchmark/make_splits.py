#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def build_splits(
    row_ids: list[str],
    seed: int = 1729,
    holdout_ratio: float = 0.2,
    paraphrase_ratio: float = 0.3,
) -> dict[str, list[str]]:
    ids = sorted(row_ids)
    rng = random.Random(seed)
    rng.shuffle(ids)
    holdout_count = max(1, int(round(len(ids) * holdout_ratio))) if ids else 0
    holdout_ids = sorted(ids[:holdout_count])
    train_ids = sorted(ids[holdout_count:])
    paraphrase_count = int(round(len(holdout_ids) * paraphrase_ratio))
    paraphrase_ids = sorted(holdout_ids[:paraphrase_count])
    return {
        "train_ids": train_ids,
        "holdout_ids": holdout_ids,
        "holdout_paraphrase_ids": paraphrase_ids,
    }


def _load_row_ids(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line)["row_id"] for line in handle if line.strip()]


def _write_json(path: Path, payload: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create deterministic ERF benchmark splits.")
    parser.add_argument("--prompt-matrix", type=Path, default=Path("benchmark/erf_llm_compare/prompt_matrix.jsonl"))
    parser.add_argument("--splits-dir", type=Path, default=Path("benchmark/erf_llm_compare/splits"))
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--holdout-ratio", type=float, default=0.2)
    parser.add_argument("--paraphrase-ratio", type=float, default=0.3)
    args = parser.parse_args()

    splits = build_splits(
        _load_row_ids(args.prompt_matrix),
        seed=args.seed,
        holdout_ratio=args.holdout_ratio,
        paraphrase_ratio=args.paraphrase_ratio,
    )
    _write_json(args.splits_dir / "train_ids.json", splits["train_ids"])
    _write_json(args.splits_dir / "holdout_ids.json", splits["holdout_ids"])
    _write_json(args.splits_dir / "holdout_paraphrase_ids.json", splits["holdout_paraphrase_ids"])
    print(f"Wrote splits under {args.splits_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

