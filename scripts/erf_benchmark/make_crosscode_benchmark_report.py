#!/usr/bin/env python3
"""Build cross-code benchmark tables and bar charts.

Default behavior:
- REMORA: latest full run under benchmark_remora/results/full_*
- PeleLMeX: latest full run under benchmark_pelelmex/results/full_*
- ERF: all full runs under benchmark_v2/results/full_*

Outputs:
- <out-dir>/benchmark_summary.csv
- <out-dir>/benchmark_summary.md
- <out-dir>/case_match_pct.png
- <out-dir>/inputs_match_pct.png
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd


TIMESTAMP_SUFFIX_RE = re.compile(r"_(\d{8}T\d{6}Z)$")


@dataclass
class RunRef:
    code: str
    run_dir: Path


def _extract_provider(run_name: str) -> str:
    """Extract provider-ish token from a run directory name."""
    if not run_name.startswith("full_"):
        return run_name
    body = run_name[len("full_") :]
    body = TIMESTAMP_SUFFIX_RE.sub("", body)
    return body


def _latest_full_run(results_root: Path) -> Path | None:
    runs = sorted(
        [p for p in results_root.glob("full_*") if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
    )
    if not runs:
        return None
    return runs[-1]


def _collect_runs(repo_root: Path) -> list[RunRef]:
    runs: list[RunRef] = []

    remora_root = repo_root / "benchmark_remora" / "results"
    remora = _latest_full_run(remora_root) if remora_root.exists() else None
    if remora:
        runs.append(RunRef(code="REMORA", run_dir=remora))

    pele_root = repo_root / "benchmark_pelelmex" / "results"
    pele = _latest_full_run(pele_root) if pele_root.exists() else None
    if pele:
        runs.append(RunRef(code="PeleLMeX", run_dir=pele))

    erf_root = repo_root / "benchmark_v2" / "results"
    if erf_root.exists():
        erf_runs = sorted([p for p in erf_root.glob("full_*") if p.is_dir()], key=lambda p: p.name)
        for p in erf_runs:
            runs.append(RunRef(code="ERF", run_dir=p))

    return runs


def _load_results(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _summarize_run(run: RunRef) -> list[dict]:
    results_path = run.run_dir / "results.jsonl"
    if not results_path.exists():
        return []
    rows = _load_results(results_path)
    provider = _extract_provider(run.run_dir.name)
    out: list[dict] = []

    strategies = sorted({str(r.get("strategy", "unknown")) for r in rows})
    for strategy in strategies:
        subset = [r for r in rows if str(r.get("strategy", "unknown")) == strategy]
        n = len(subset)
        if n == 0:
            continue
        case_hits = sum(int(bool(r.get("case_match", 0))) for r in subset)
        inputs_hits = sum(int(bool(r.get("inputs_match", 0))) for r in subset)
        row_score_mean = sum(float(r.get("row_score", 0.0) or 0.0) for r in subset) / n
        out.append(
            {
                "code": run.code,
                "provider": provider,
                "run_dir": run.run_dir.as_posix(),
                "strategy": strategy,
                "rows": n,
                "case_match_hits": case_hits,
                "case_match_pct": 100.0 * case_hits / n,
                "inputs_match_hits": inputs_hits,
                "inputs_match_pct": 100.0 * inputs_hits / n,
                "row_score_mean": row_score_mean,
            }
        )
    return out


def _make_chart(df: pd.DataFrame, metric: str, ylabel: str, out_path: Path) -> None:
    order = (
        df[["code", "provider"]]
        .drop_duplicates()
        .sort_values(["code", "provider"])
        .apply(lambda r: f"{r['code']} ({r['provider']})", axis=1)
        .tolist()
    )
    labels = order
    width = 0.35
    x = list(range(len(labels)))

    vals_simple: list[float] = []
    vals_hier: list[float] = []
    for label in labels:
        code, provider = label.split(" (", 1)
        provider = provider.rstrip(")")
        sel = df[(df["code"] == code) & (df["provider"] == provider)]
        s = sel[sel["strategy"] == "simple"]
        h = sel[sel["strategy"] == "hierarchical"]
        vals_simple.append(float(s.iloc[0][metric]) if not s.empty else 0.0)
        vals_hier.append(float(h.iloc[0][metric]) if not h.empty else 0.0)

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.5), 5))
    ax.bar([i - width / 2 for i in x], vals_simple, width=width, label="simple")
    ax.bar([i + width / 2 for i in x], vals_hier, width=width, label="hierarchical")
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, 100)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_title(ylabel)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _markdown_table(df: pd.DataFrame) -> str:
    columns = list(df.columns)
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines = [header, sep]
    for _, row in df.iterrows():
        vals = [str(row[c]) for c in columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def build_report(repo_root: Path, out_dir: Path) -> tuple[Path, Path, Path, Path]:
    run_refs = _collect_runs(repo_root)
    rows: list[dict] = []
    for run in run_refs:
        rows.extend(_summarize_run(run))

    if not rows:
        raise RuntimeError("No benchmark full run artifacts found.")

    df = pd.DataFrame(rows).sort_values(["code", "provider", "strategy"]).reset_index(drop=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "benchmark_summary.csv"
    md_path = out_dir / "benchmark_summary.md"
    case_png = out_dir / "case_match_pct.png"
    inputs_png = out_dir / "inputs_match_pct.png"

    df.to_csv(csv_path, index=False)

    md_df = df.copy().astype(str)
    for col in ["case_match_pct", "inputs_match_pct", "row_score_mean"]:
        md_df[col] = df[col].map(lambda v: f"{v:.2f}")
    md_path.write_text(_markdown_table(md_df), encoding="utf-8")

    _make_chart(df, "case_match_pct", "Case Match (%)", case_png)
    _make_chart(df, "inputs_match_pct", "Inputs Match (%)", inputs_png)

    return csv_path, md_path, case_png, inputs_png


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create cross-code benchmark tables and charts.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root (default: current directory).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("benchmark_crosscode/latest"),
        help="Output directory for report files.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main() -> int:
    args = _parse_args()
    csv_path, md_path, case_png, inputs_png = build_report(
        repo_root=args.repo_root.resolve(),
        out_dir=args.out_dir.resolve(),
    )
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {md_path}")
    print(f"Wrote: {case_png}")
    print(f"Wrote: {inputs_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
