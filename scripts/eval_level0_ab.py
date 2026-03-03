#!/usr/bin/env python3
"""
Deterministic A/B evaluation for Level-0 solver routing.

Arm A: legacy hardcoded Level0Builder behavior.
Arm B: current config-driven Level0Builder behavior.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import faiss
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from database.configs import discover_code_configs
from database.indexing.level0_builder import Level0Builder
from database.indexing.level0_searcher import Level0Searcher


class DeterministicEmbedder:
    """Deterministic hash embedder used for stable offline comparisons."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def expand_documents(self, documents, metadata):
        return documents, metadata

    def _embed(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in text.lower().split():
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest[:8], 16) % self.dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()

    def embed_texts(self, texts):
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str):
        return self._embed(text)


class LegacyLevel0Builder:
    """Minimal legacy Level-0 builder implementation for A/B baseline."""

    def __init__(self, embedder):
        self.embedder = embedder
        self.configs = discover_code_configs()

    def build(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        self._build_physics_regimes(output_dir)
        self._build_solver_capabilities(output_dir)
        self._build_code_lineage(output_dir)
        self._build_cross_cutting_guidance(output_dir)

    def _save_index(self, documents: list[str], metadata: list[dict[str, Any]], output_path: Path):
        embeddings = self.embedder.embed_texts(documents)
        arr = np.array(embeddings).astype("float32")
        index = faiss.IndexFlatL2(arr.shape[1])
        index.add(arr)
        faiss.write_index(index, str(output_path) + ".faiss")
        (output_path.parent / f"{output_path.name}_metadata.json").write_text(json.dumps(metadata, indent=2))

    def _build_physics_regimes(self, output_dir: Path):
        physics_families = {
            "Combustion": {
                "codes": ["PeleC", "PeleLMeX"],
                "description": "Reacting flows, flames, detonations, chemical kinetics",
            },
            "Compressible Flow": {
                "codes": ["PeleC", "Castro"],
                "description": "Supersonic flows, shocks, high Mach number, compressibility effects",
            },
            "Low Mach Flow": {
                "codes": ["PeleLMeX", "incflo"],
                "description": "Low speed flows, incompressible limit, detailed chemistry",
            },
            "Plasma Physics": {
                "codes": ["WarpX"],
                "description": "Particle beams, electromagnetic fields, accelerators",
            },
            "Atmospheric Modeling": {
                "codes": ["ERF"],
                "description": "Weather, climate, mesoscale dynamics",
            },
        }
        available = {cfg.code_name for cfg in self.configs}
        docs, meta = [], []
        for family, info in physics_families.items():
            for code in info["codes"]:
                if code in available:
                    docs.append(f"{code} - {family}: {info['description']}")
                    meta.append({"code_name": code, "physics_family": family, "description": info["description"]})
        self._save_index(docs, meta, output_dir / "physics_regimes")

    def _build_solver_capabilities(self, output_dir: Path):
        capability_map = {
            "PeleC": ["handles strong shocks", "compressible reacting flow", "supersonic combustion", "detonation physics"],
            "PeleLMeX": ["low Mach number formulation", "detailed chemical kinetics", "flame dynamics", "diffusion-dominated physics"],
            "WarpX": ["particle-in-cell method", "electromagnetic field solver", "plasma accelerators", "beam dynamics"],
            "ERF": ["atmospheric dynamics", "mesoscale modeling", "terrain-following coordinates", "buoyancy-driven flows"],
        }
        docs, meta = [], []
        for cfg in self.configs:
            if getattr(cfg, "description", ""):
                docs.append(f"{cfg.code_name}: {cfg.description}")
                meta.append({"code_name": cfg.code_name, "capability_type": "description"})
            for cap in capability_map.get(cfg.code_name, []):
                docs.append(f"{cfg.code_name}: {cap}")
                meta.append({"code_name": cfg.code_name, "capability": cap, "capability_type": "specific"})
        self._save_index(docs, meta, output_dir / "solver_capabilities")

    def _build_code_lineage(self, output_dir: Path):
        lineage = {
            "PeleLMeX": {"evolved_from": "PeleLM", "description": "PeleLMeX is the modernized version of PeleLM with improved numerics"},
            "PeleC": {"related": ["CNS", "Combustion"], "description": "PeleC evolved from CNS (Compressible Navier-Stokes)"},
        }
        available = {cfg.code_name for cfg in self.configs}
        docs, meta = [], []
        for code, info in lineage.items():
            if code in available:
                docs.append(f"{code} lineage: {info['description']}")
                meta.append({"code_name": code, "lineage_info": info})
        self._save_index(docs, meta, output_dir / "code_lineage")

    def _build_cross_cutting_guidance(self, output_dir: Path):
        docs = ["Default guidance: Use PeleC for compressible flows, PeleLMeX for low Mach"]
        meta = [{"guidance_type": "default"}]
        self._save_index(docs, meta, output_dir / "cross_cutting_guidance")


@dataclass
class EvalRow:
    prompt_id: str
    expected: str
    predicted: str
    confidence: float
    ok: bool


def softmax(values: list[float]) -> list[float]:
    if not values:
        return []
    vmax = max(values)
    exps = [math.exp(v - vmax) for v in values]
    total = sum(exps)
    return [v / total for v in exps] if total > 0 else [0.0 for _ in values]


def evaluate(searcher: Level0Searcher, prompts: list[dict[str, Any]], all_codes: list[str]) -> dict[str, Any]:
    rows: list[EvalRow] = []
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    nll_sum = 0.0
    brier_sum = 0.0
    ece_bins: list[list[float]] = [[] for _ in range(10)]

    for item in prompts:
        ranked = searcher.search(item["prompt"], top_k=len(all_codes))
        if not ranked:
            rows.append(EvalRow(item["id"], item["expected_solver"], "NONE", 0.0, False))
            confusion[item["expected_solver"]]["NONE"] += 1
            continue

        scores = [r["score"] for r in ranked]
        probs = softmax(scores)
        best = ranked[0]["code"]
        conf = probs[0]
        ok = best == item["expected_solver"]
        rows.append(EvalRow(item["id"], item["expected_solver"], best, conf, ok))
        confusion[item["expected_solver"]][best] += 1

        label_vec = [1.0 if r["code"] == item["expected_solver"] else 0.0 for r in ranked]
        nll_sum += -math.log(max(1e-12, next((p for p, r in zip(probs, ranked) if r["code"] == item["expected_solver"]), 1e-12)))
        brier_sum += sum((p - y) ** 2 for p, y in zip(probs, label_vec))
        bin_idx = min(9, int(conf * 10))
        ece_bins[bin_idx].append(1.0 if ok else 0.0)

    total = max(1, len(rows))
    accuracy = sum(1 for r in rows if r.ok) / total
    brier = brier_sum / total
    nll = nll_sum / total

    ece = 0.0
    for i, bucket in enumerate(ece_bins):
        if not bucket:
            continue
        conf_center = (i + 0.5) / 10.0
        acc = sum(bucket) / len(bucket)
        ece += (len(bucket) / total) * abs(acc - conf_center)

    return {
        "accuracy": accuracy,
        "brier": brier,
        "nll": nll,
        "ece": ece,
        "rows": [r.__dict__ for r in rows],
        "confusion": {k: dict(v) for k, v in confusion.items()},
    }


def main():
    parser = argparse.ArgumentParser(description="Run deterministic Level-0 A/B evaluation.")
    parser.add_argument(
        "--prompts",
        default="tests/data/level0_ab_prompts.json",
        help="JSON file with prompt entries",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default benchmark_results/level0_ab/<timestamp>)",
    )
    args = parser.parse_args()

    prompts = json.loads(Path(args.prompts).read_text())
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_root = Path(args.output_dir) if args.output_dir else Path("benchmark_results") / "level0_ab" / timestamp
    out_root.mkdir(parents=True, exist_ok=True)

    embedder = DeterministicEmbedder()
    codes = sorted({cfg.code_name for cfg in discover_code_configs()})

    a_dir = out_root / "arm_a_legacy"
    b_dir = out_root / "arm_b_refactor"
    LegacyLevel0Builder(embedder).build(a_dir)
    Level0Builder(embedder=embedder).build(b_dir)

    a_metrics = evaluate(Level0Searcher(index_dir=a_dir, embedder=embedder), prompts, codes)
    b_metrics = evaluate(Level0Searcher(index_dir=b_dir, embedder=embedder), prompts, codes)

    summary = {
        "arm_a_legacy": {k: a_metrics[k] for k in ("accuracy", "ece", "brier", "nll")},
        "arm_b_refactor": {k: b_metrics[k] for k in ("accuracy", "ece", "brier", "nll")},
        "delta_b_minus_a": {
            "accuracy": b_metrics["accuracy"] - a_metrics["accuracy"],
            "ece": b_metrics["ece"] - a_metrics["ece"],
            "brier": b_metrics["brier"] - a_metrics["brier"],
            "nll": b_metrics["nll"] - a_metrics["nll"],
        },
    }

    (out_root / "summary.json").write_text(json.dumps(summary, indent=2))
    (out_root / "details_arm_a.json").write_text(json.dumps(a_metrics, indent=2))
    (out_root / "details_arm_b.json").write_text(json.dumps(b_metrics, indent=2))

    with (out_root / "summary.md").open("w") as fh:
        fh.write("# Level-0 A/B Summary\n\n")
        fh.write("## Metrics\n")
        fh.write(f"- Arm A accuracy: {a_metrics['accuracy']:.3f}\n")
        fh.write(f"- Arm B accuracy: {b_metrics['accuracy']:.3f}\n")
        fh.write(f"- Arm A ECE: {a_metrics['ece']:.3f}\n")
        fh.write(f"- Arm B ECE: {b_metrics['ece']:.3f}\n")
        fh.write(f"- Arm A Brier: {a_metrics['brier']:.3f}\n")
        fh.write(f"- Arm B Brier: {b_metrics['brier']:.3f}\n")

    with (out_root / "confusion_arm_b.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["expected", "predicted", "count"])
        for expected, row in b_metrics["confusion"].items():
            for predicted, count in row.items():
                writer.writerow([expected, predicted, count])

    print(f"Wrote A/B report to: {out_root}")


if __name__ == "__main__":
    main()
