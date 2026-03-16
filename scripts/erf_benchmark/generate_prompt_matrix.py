#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

LEGACY_WAVES = ("wave0", "wave1", "wave2")
PHYS_WAVES = ("wave_phys0", "wave_phys1", "wave_phys2", "wave_phys3")
ALL_WAVES = LEGACY_WAVES + PHYS_WAVES


def _default_catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "benchmark" / "cases" / "erf.yaml"

def discover_erf_inputs(erf_root: Path) -> list[Path]:
    exec_root = erf_root / "Exec"
    candidates: set[Path] = set()
    for pattern in ("inputs*", "input_*"):
        for path in exec_root.rglob(pattern):
            if path.is_file():
                candidates.add(path.relative_to(erf_root))
    return sorted(candidates)


def _load_case_catalog(catalog_path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    if not catalog_path.exists():
        return {}

    payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    cases = payload.get("cases") or []
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in cases:
        case_dir = str(entry.get("case_dir", "")).strip().rstrip("/")
        inputs = str(entry.get("inputs", "")).strip()
        if not case_dir or not inputs:
            continue
        index[(case_dir, inputs)] = entry
    return index


def _category_from_relpath(relpath: Path) -> str:
    parts = relpath.parts
    return parts[1] if len(parts) > 2 else "Uncategorized"


def _normalize_case_name(case_rel: str) -> str:
    return case_rel.split("/")[-1].replace("_", " ")


def _metadata_for(
    *,
    case_rel: str,
    input_name: str,
    case_catalog: dict[tuple[str, str], dict[str, Any]] | None,
) -> dict[str, Any] | None:
    if not case_catalog:
        return None

    hit = case_catalog.get((case_rel, input_name))
    if hit:
        return hit

    same_case_entries = [
        entry
        for (catalog_case, _catalog_input), entry in case_catalog.items()
        if catalog_case.rstrip("/") == case_rel.rstrip("/")
    ]
    if len(same_case_entries) == 1:
        return same_case_entries[0]
    return None


def _physics_list(meta: dict[str, Any] | None) -> str:
    if not meta:
        return "core ERF dynamics"
    tags = meta.get("physics") or []
    if not isinstance(tags, list) or not tags:
        return "core ERF dynamics"
    return ", ".join(str(tag) for tag in tags)


def _specialized_phrase(meta: dict[str, Any] | None) -> str:
    if not meta:
        return "Use baseline physics options unless a required coupling is obvious."
    if meta.get("specialized_knowledge"):
        return "Preserve specialized model options from the baseline and avoid simplifying them away."
    return "Keep the setup straightforward and avoid unnecessary specialist model switches."


def _wave_prompt(case_rel: str, input_name: str, wave_id: str, meta: dict[str, Any] | None = None) -> str:
    base = f"Use ERF case {case_rel} with {input_name}"
    if wave_id == "wave1":
        return f"Select the ERF setup matching {case_rel}; prefer inputs file {input_name}."
    if wave_id == "wave2":
        return f"Configure ERF for the {case_rel} scenario and choose {input_name} as baseline inputs."
    if wave_id == "wave_phys0":
        case_name = str((meta or {}).get("case_name") or _normalize_case_name(case_rel))
        desc = str((meta or {}).get("description") or "").strip()
        if desc:
            return f"Run ERF {case_name} from {case_rel} using {input_name}. {desc}"
        return f"Run ERF {case_name} from {case_rel} using {input_name}."
    if wave_id == "wave_phys1":
        case_name = str((meta or {}).get("case_name") or _normalize_case_name(case_rel))
        desc = str((meta or {}).get("description") or "Use the baseline physics behavior.").strip()
        physics = _physics_list(meta)
        return (
            f"Run ERF {case_name} using baseline {input_name}. "
            f"Target scenario: {desc} Emphasize physics: {physics}."
        )
    if wave_id == "wave_phys2":
        case_name = str((meta or {}).get("case_name") or _normalize_case_name(case_rel))
        desc = str((meta or {}).get("description") or "Use baseline flow setup.").strip()
        concept_density = str((meta or {}).get("concept_density") or "medium")
        novelty_tier = str((meta or {}).get("novelty_tier") or "parameter-only")
        difficulty = str((meta or {}).get("difficulty_tier") or "medium")
        return (
            f"Configure ERF for {case_name} with {input_name}. {desc} "
            f"Treat this as {difficulty} difficulty with {concept_density} concept density. "
            f"Limit edits to {novelty_tier}-level changes."
        )
    if wave_id == "wave_phys3":
        case_name = str((meta or {}).get("case_name") or _normalize_case_name(case_rel))
        desc = str((meta or {}).get("description") or "Match the baseline dynamics and outputs.").strip()
        prompt_band = str((meta or {}).get("prompt_length_band") or "medium")
        physics = _physics_list(meta)
        return (
            f"Run an ERF simulation for {case_name} using baseline file {input_name}. "
            f"Scenario intent: {desc} Physics scope: {physics}. "
            f"Prompt complexity target: {prompt_band}. {_specialized_phrase(meta)} "
            "Report selected case, selected inputs, and one diagnostic output to verify behavior."
        )
    return base


def build_prompt_matrix_rows(
    inputs_relpaths: list[Path],
    *,
    wave_ids: tuple[str, ...] = LEGACY_WAVES,
    case_catalog: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for relpath in sorted(inputs_relpaths):
        case_rel = relpath.parent.as_posix()
        input_name = relpath.name
        input_rel = relpath.as_posix()
        meta = _metadata_for(case_rel=case_rel, input_name=input_name, case_catalog=case_catalog)
        for wave_id in wave_ids:
            row_id = hashlib.sha1(f"{case_rel}|{input_name}|{wave_id}".encode("utf-8")).hexdigest()[:16]
            row = {
                "row_id": row_id,
                "target_case_relpath": case_rel,
                "target_inputs_relpath": input_rel,
                "target_inputs_filename": input_name,
                "category": _category_from_relpath(relpath),
                "wave_id": wave_id,
                "prompt_text": _wave_prompt(case_rel, input_name, wave_id, meta),
                "strategy_targets": ["simple", "hierarchical"],
            }
            if meta:
                row.update(
                    {
                        "case_description": str(meta.get("description", "")),
                        "case_physics": meta.get("physics", []),
                        "difficulty_tier": str(meta.get("difficulty_tier", "")),
                        "prompt_length_band": str(meta.get("prompt_length_band", "")),
                        "concept_density": str(meta.get("concept_density", "")),
                        "specialized_knowledge": bool(meta.get("specialized_knowledge", False)),
                        "novelty_tier": str(meta.get("novelty_tier", "")),
                    }
                )
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _build_manifest(rows: list[dict], erf_root: Path, wave_ids: tuple[str, ...]) -> dict:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "erf_root": str(erf_root),
        "row_count": len(rows),
        "unique_inputs": len({row["target_inputs_relpath"] for row in rows}),
        "waves": list(wave_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ERF llm_compare prompt matrix.")
    parser.add_argument("--erf-root", type=Path, default=Path("../ERF"))
    parser.add_argument("--out-dir", type=Path, default=Path("benchmark/erf_llm_compare"))
    parser.add_argument(
        "--waves",
        type=str,
        default="wave0,wave1,wave2",
        help="Comma-separated wave IDs. Supported: wave0,wave1,wave2,wave_phys0,wave_phys1,wave_phys2,wave_phys3",
    )
    parser.add_argument(
        "--case-catalog",
        type=Path,
        default=_default_catalog_path(),
        help="YAML catalog path (e.g., benchmark/cases/erf.yaml) used for physics-forward prompt metadata.",
    )
    args = parser.parse_args()

    wave_ids = tuple(token.strip() for token in args.waves.split(",") if token.strip())
    invalid = [wave for wave in wave_ids if wave not in ALL_WAVES]
    if invalid:
        raise SystemExit(f"Unsupported wave IDs: {invalid}. Supported waves: {ALL_WAVES}")

    inputs_rel = discover_erf_inputs(args.erf_root)
    catalog = _load_case_catalog(args.case_catalog)
    rows = build_prompt_matrix_rows(inputs_rel, wave_ids=wave_ids, case_catalog=catalog)
    _write_jsonl(args.out_dir / "prompt_matrix.jsonl", rows)
    (args.out_dir / "manifest.json").write_text(
        json.dumps(_build_manifest(rows, args.erf_root, wave_ids), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} rows to {args.out_dir / 'prompt_matrix.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
