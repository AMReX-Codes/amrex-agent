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
import faiss
import numpy as np

from database.configs import discover_code_configs


logger = logging.getLogger(__name__)

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
        
    def build(self, output_dir: Path):
        """
        Build all 4 Level 0 sub-indices.
        
        Args:
            output_dir: Directory to save indices
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Building Level 0 indices for {len(self.configs)} codes...")
        
        # Build each sub-index
        self._build_physics_regimes(output_dir)
        self._build_solver_capabilities(output_dir)
        self._build_code_lineage(output_dir)
        self._build_cross_cutting_guidance(output_dir)
        
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
            })
        return {"documents": documents, "metadata": metadata}
    
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
    
    def _get_solver_list(self) -> List[str]:
        """Get list of solvers being indexed."""
        return [cfg.code_name for cfg in self.configs]
    
    def _validate_solver_name(self, name: str) -> bool:
        """Validate solver name against registry."""
        valid_names = {cfg.code_name for cfg in self.configs}
        return name in valid_names
