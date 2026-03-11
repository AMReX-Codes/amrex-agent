"""
Level 0 Index Builder - Multi-Solver Physics Router

Builds 4 weighted sub-indices:
1. physics_regimes (40%) - Domain families (combustion, astrophysics, etc.)
2. solver_capabilities (30%) - Specific capabilities per code
3. code_lineage (20%) - Evolution history and legacy names
4. cross_cutting_guidance (10%) - Decision frameworks from reports


PRD: Section 5.2 (FR-1, FR-2) and Section 10.1

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import json
from pathlib import Path
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import re
import faiss
import numpy as np

from database.configs import discover_code_configs


logger = logging.getLogger(__name__)


_REUSE_LOC_BASELINE_PER_SOLVER_PER_INDEX = 25
_LEVEL0_SUBINDEX_COUNT = 4
_INDEX_LEVELS = ("l0", "l1", "l2")


class Level0Builder:
    """Builds Level 0 multi-solver routing indices."""
    
    def __init__(self, embedder, knowledge_base_path: Optional[Path] = None):
        """
        Initialize Level 0 builder.

        Args:
            embedder: EmbeddingService instance with embeddings attribute
            knowledge_base_path: Path to knowledge base reports (optional)
        """
        self.embedder = embedder
        self.knowledge_base_path = knowledge_base_path or Path("knowledge_base")
        
        # Discover available codes
        self.configs = discover_code_configs()
        
    def build(self, output_dir: Path) -> None:
        """
        Build all 4 Level 0 sub-indices.
        
        Args:
            output_dir: Directory to save indices
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        self._solver_version_links = self._collect_solver_version_links()
        
        logger.info(f"Building Level 0 indices for {len(self.configs)} codes...")
        
        # Build each sub-index
        self._build_physics_regimes(output_dir)
        self._build_solver_capabilities(output_dir)
        self._build_code_lineage(output_dir)
        self._build_cross_cutting_guidance(output_dir)
        self._write_version_manifest(output_dir)
        self._write_loc_savings_report(output_dir)
        
        logger.info(f"[PASS] Level 0 indices built in {output_dir}")
    
    def _build_physics_regimes(self, output_dir: Path):
        """
        Build physics_regimes index (40% weight).

        Sources only config.level0_physics_regimes entries.
        """
        documents = []
        metadata = []

        for config in self.configs:
            entries = getattr(config, "level0_physics_regimes", []) or []
            if not entries:
                logger.warning(
                    "No level0_physics_regimes entries for %s",
                    config.code_name,
                )
                continue

            for entry in entries:
                family = (entry.get("family") or "").strip()
                description = (entry.get("description") or "").strip()
                aliases = [a.strip() for a in entry.get("aliases", []) if str(a).strip()]
                if not family or not description:
                    logger.warning(
                        "Skipping malformed regime entry for %s: %s",
                        config.code_name,
                        entry,
                    )
                    continue

                alias_text = f" Keywords: {', '.join(aliases)}" if aliases else ""
                doc = f"{config.code_name} - {family}: {description}.{alias_text}"
                documents.append(doc)
                metadata.append({
                    'code_name': config.code_name,
                    'physics_family': family,
                    'description': description,
                    'aliases': aliases,
                    **self._version_metadata_for(config.code_name),
                })
        
        # Embed and save
        self._save_index(
            documents, metadata, 
            output_dir / "physics_regimes",
            index_type='physics_regimes'
        )
    
    def _build_solver_capabilities(self, output_dir: Path):
        """
        Build solver_capabilities index (30% weight).

        Sources:
        - config.description (generic description)
        - config.level0_capabilities (explicit capabilities)
        - config.selection_keywords (routing-oriented capability hints)
        """
        documents = []
        metadata = []

        for config in self.configs:
            description = (getattr(config, "description", "") or "").strip()
            if description:
                doc = f"{config.code_name}: {description}"
                documents.append(doc)
                metadata.append({
                    'code_name': config.code_name,
                    'capability': description,
                    'capability_type': 'description',
                    **self._version_metadata_for(config.code_name),
                })

            seen: set[str] = set()
            for capability in getattr(config, "level0_capabilities", []) or []:
                capability = str(capability).strip()
                if not capability:
                    continue
                key = capability.lower()
                if key in seen:
                    continue
                seen.add(key)
                doc = f"{config.code_name}: {capability}"
                documents.append(doc)
                metadata.append({
                    'code_name': config.code_name,
                    'capability': capability,
                    'capability_type': 'specific',
                    **self._version_metadata_for(config.code_name),
                })

            for keyword in getattr(config, "selection_keywords", []) or []:
                keyword = str(keyword).strip()
                if not keyword:
                    continue
                key = keyword.lower()
                if key in seen:
                    continue
                seen.add(key)
                doc = f"{config.code_name}: {keyword}"
                documents.append(doc)
                metadata.append({
                    'code_name': config.code_name,
                    'capability': keyword,
                    'capability_type': 'keyword',
                    **self._version_metadata_for(config.code_name),
                })
        
        self._save_index(
            documents, metadata,
            output_dir / "solver_capabilities",
            index_type='solver_capabilities'
        )
    
    def _build_code_lineage(self, output_dir: Path):
        """
        Build code_lineage index (20% weight).

        Sources only config.level0_lineage entries.
        """
        documents = []
        metadata = []

        for config in self.configs:
            info = getattr(config, "level0_lineage", {}) or {}
            description = (info.get("description") or "").strip()
            if not description:
                logger.warning("No level0_lineage description for %s", config.code_name)
                continue

            text_parts = [f"{config.code_name} lineage: {description}"]
            evolved_from = info.get("evolved_from")
            if evolved_from:
                text_parts.append(f"Evolved from: {evolved_from}")
            related = info.get("related", [])
            if related:
                text_parts.append(f"Related: {', '.join(str(r) for r in related)}")

            documents.append(". ".join(text_parts))
            metadata.append({
                'code_name': config.code_name,
                'lineage_info': info,
                **self._version_metadata_for(config.code_name),
            })
        
        self._save_index(
            documents, metadata,
            output_dir / "code_lineage",
            index_type='code_lineage'
        )
    
    def _build_cross_cutting_guidance(self, output_dir: Path):
        """
        Build cross_cutting_guidance index (10% weight).

        Sources in order:
        1) decision frameworks extracted from KB reports
        2) config.level0_cross_cutting_guidance per solver
        3) synthesized neutral fallback from config metadata
        """
        documents = []
        metadata = []

        # Look for decision framework reports
        if self.knowledge_base_path.exists():
            for report_file in self.knowledge_base_path.glob("report_*_solver*.md"):
                content = report_file.read_text()
                
                # Extract sections (simple chunking)
                sections = content.split('\n## ')
                for section in sections[1:]:  # Skip header
                    lines = section.split('\n')
                    title = lines[0]
                    body = '\n'.join(lines[1:])
                    
                    if 'when to use' in title.lower() or 'selection' in title.lower():
                        documents.append(f"{title}: {body[:500]}")
                        metadata.append({
                            'source': report_file.name,
                            'section': title,
                            'guidance_type': 'decision_framework',
                        })

        # Add per-solver config guidance
        for config in self.configs:
            guidance_lines = getattr(config, "level0_cross_cutting_guidance", []) or []
            for line in guidance_lines:
                line = str(line).strip()
                if not line:
                    continue
                documents.append(line)
                metadata.append({
                    'code_name': config.code_name,
                    'guidance_type': 'solver_guidance',
                    'source': 'config',
                    **self._version_metadata_for(config.code_name),
                })

        # Add neutral fallback guidance only if still empty
        if not documents:
            neutral = self._synthesize_neutral_guidance()
            documents.extend(neutral["documents"])
            metadata.extend(neutral["metadata"])
        
        self._save_index(
            documents, metadata,
            output_dir / "cross_cutting_guidance",
            index_type='cross_cutting_guidance'
        )
    
    def _synthesize_neutral_guidance(self) -> Dict[str, List[Dict[str, Any]] | List[str]]:
        """Generate neutral fallback guidance from config metadata."""
        documents: List[str] = []
        metadata: List[Dict[str, Any]] = []
        for config in self.configs:
            description = (getattr(config, "description", "") or "").strip()
            keywords = getattr(config, "selection_keywords", []) or []
            keyword_text = ", ".join(str(k) for k in keywords if str(k).strip())
            line = f"{config.code_name}: {description}" if description else f"{config.code_name}: domain solver"
            if keyword_text:
                line = f"{line}. Keywords: {keyword_text}"
            documents.append(line)
            metadata.append({
                "code_name": config.code_name,
                "guidance_type": "neutral_synthesized",
                "source": "config",
                **self._version_metadata_for(config.code_name),
            })
        return {"documents": documents, "metadata": metadata}

    def _collect_solver_version_links(self) -> Dict[str, Dict[str, Any]]:
        """Collect commit-linked version metadata for each discovered solver."""
        links: Dict[str, Dict[str, Any]] = {}
        schema_dir = Path(__file__).resolve().parent.parent / "schemas"
        for config in self.configs:
            commit, schema_file = self._extract_solver_commit(config, schema_dir)
            links[config.code_name] = {
                "solver_commit": commit,
                "solver_schema_file": schema_file,
                "level_versions": {
                    level: f"{config.code_name}@{commit}" for level in _INDEX_LEVELS
                },
            }
        return links

    def _extract_solver_commit(self, config: Any, schema_dir: Path) -> tuple[str, str]:
        """Extract solver commit metadata from the latest schema payload."""
        pattern = getattr(config, "schema_pattern", "") or f"{config.code_name.lower()}_schema_*.json"
        matches = sorted(schema_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if not matches:
            return "unknown", "unknown"

        schema_path = matches[0]
        payload: Dict[str, Any] = {}
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}

        commit = str(
            payload.get("repo_commit")
            or (payload.get("metadata") or {}).get("repo_commit")
            or self._parse_commit_from_filename(schema_path.name)
            or "unknown"
        )
        return commit, schema_path.name

    def _parse_commit_from_filename(self, filename: str) -> str:
        """Best-effort commit extraction from schema filename suffixes."""
        match = re.search(r"_([0-9a-f]{7,40})\.json$", filename, re.IGNORECASE)
        return match.group(1) if match else ""

    def _version_metadata_for(self, code_name: str) -> Dict[str, Any]:
        """Return commit-linked version metadata for a solver code name."""
        links = getattr(self, "_solver_version_links", {})
        return dict(links.get(code_name, {}))

    def _write_version_manifest(self, output_dir: Path) -> None:
        """Persist solver commit linkage for L0/L1/L2 index versions."""
        links = getattr(self, "_solver_version_links", {})
        manifest = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "index_levels": list(_INDEX_LEVELS),
            "solvers": [
                {
                    "code_name": code_name,
                    **details,
                }
                for code_name, details in sorted(links.items())
            ],
        }
        (output_dir / "level0_version_manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )
    
    def _save_index(self, documents: List[str], metadata: List[Dict], 
                    output_path: Path, index_type: str):
        """Save FAISS index and metadata."""
        if not documents:
            logger.warning(f"[WARN]  No documents for {index_type}")
            return

        if hasattr(self.embedder, "expand_documents"):
            documents, metadata = self.embedder.expand_documents(documents, metadata)
        
        # Embed documents
        embeddings = self.embedder.embed_texts(documents)
        embeddings_array = np.array(embeddings).astype('float32')
        
        # Create FAISS index
        dimension = embeddings_array.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_array)
        
        # Save index
        faiss.write_index(index, str(output_path) + ".faiss")
        
        # Save metadata
        metadata_file = output_path.parent / f"{output_path.name}_metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))
        
        logger.info(f"  [PASS] {index_type}: {len(documents)} documents indexed")

    def _write_loc_savings_report(self, output_dir: Path) -> None:
        """
        Persist automated LOC-savings metrics for framework reuse tracking.

        This report quantifies estimated manual implementation LOC versus
        the current shared framework LOC for Level 0 index construction.
        """
        report = self._compute_loc_savings_metrics()
        report_path = output_dir / "level0_loc_savings_report.json"
        report_path.write_text(json.dumps(report, indent=2))
        logger.info(
            "  [PASS] loc_savings_report: saved %s (estimated_saved_loc=%s)",
            report_path.name,
            report["estimated_loc_saved"],
        )

    def _compute_loc_savings_metrics(self) -> Dict[str, Any]:
        """Compute reusable framework LOC-savings metrics."""
        solver_count = len(self.configs)
        baseline_manual_loc = (
            solver_count
            * _LEVEL0_SUBINDEX_COUNT
            * _REUSE_LOC_BASELINE_PER_SOLVER_PER_INDEX
        )
        framework_loc = self._count_module_loc()
        estimated_saved = max(0, baseline_manual_loc - framework_loc)
        savings_ratio = (
            (estimated_saved / baseline_manual_loc) if baseline_manual_loc else 0.0
        )
        per_code_cost_accounting = self._compute_per_code_cost_accounting(
            framework_loc=framework_loc
        )
        return {
            "metric_name": "level0_framework_reuse_loc_savings",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "solver_count": solver_count,
            "subindex_count": _LEVEL0_SUBINDEX_COUNT,
            "baseline_manual_loc": baseline_manual_loc,
            "framework_loc": framework_loc,
            "estimated_loc_saved": estimated_saved,
            "savings_ratio": round(savings_ratio, 4),
            "per_code_cost_accounting": per_code_cost_accounting,
            "assumptions": {
                "baseline_loc_per_solver_per_index": _REUSE_LOC_BASELINE_PER_SOLVER_PER_INDEX,
                "baseline_description": (
                    "Estimated LOC for a bespoke per-solver/per-index implementation"
                ),
            },
        }

    def _compute_per_code_cost_accounting(self, framework_loc: int) -> List[Dict[str, Any]]:
        """
        Compute per-code share of reuse cost and saved effort.

        Reuse cost is represented as each solver's apportioned share of the
        framework LOC needed to support all Level 0 sub-indices.
        """
        if not self.configs:
            return []

        baseline_per_code = (
            _LEVEL0_SUBINDEX_COUNT * _REUSE_LOC_BASELINE_PER_SOLVER_PER_INDEX
        )
        allocated_framework_loc = framework_loc / len(self.configs)

        per_code: List[Dict[str, Any]] = []
        for config in self.configs:
            per_code_saved = max(0.0, baseline_per_code - allocated_framework_loc)
            per_code_ratio = (
                (per_code_saved / baseline_per_code) if baseline_per_code else 0.0
            )
            per_code.append({
                "code_name": config.code_name,
                "baseline_manual_loc": baseline_per_code,
                "allocated_framework_loc": round(allocated_framework_loc, 2),
                "estimated_loc_saved": round(per_code_saved, 2),
                "savings_ratio": round(per_code_ratio, 4),
            })
        return per_code

    def _count_module_loc(self) -> int:
        """
        Count non-empty, non-comment lines in this module.

        This keeps framework LOC accounting deterministic and automated.
        """
        module_path = Path(__file__).resolve()
        loc = 0
        for line in module_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            loc += 1
        return loc
    
    def _get_solver_list(self) -> List[str]:
        """Get list of solvers being indexed."""
        return [cfg.code_name for cfg in self.configs]
    
    def _validate_solver_name(self, name: str) -> bool:
        """Validate solver name against registry."""
        valid_names = {cfg.code_name for cfg in self.configs}
        return name in valid_names
