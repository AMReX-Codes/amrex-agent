"""
Level 0 Searcher - Weighted Multi-Index Search

Searches 4 sub-indices with weighted scoring:
- physics_regimes: 40%
- solver_capabilities: 30%
- code_lineage: 20%
- cross_cutting_guidance: 10%

PRD: Section 10.1
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import faiss
import numpy as np
import logging

logger = logging.getLogger(__name__)

class Level0Searcher:
    """Multi-index searcher with weighted scoring."""
    
    # PRD Section 10.1: Exact weights
    WEIGHTS = {
        'physics_regimes': 0.4,
        'solver_capabilities': 0.3,
        'code_lineage': 0.2,
        'cross_cutting_guidance': 0.1,
    }
    INDEX_GROWTH_MIN_INDICES = 100
    MAX_ACCURACY_DRIFT = 0.02
    
    def __init__(self, index_dir: Path, embedder=None):
        """
        Initialize searcher.
        
        Args:
            index_dir: Directory containing Level 0 indices
            embedder: Embedding service (for query embedding)
        """
        self.index_dir = index_dir
        self.embedder = embedder
        
        # Lazy-loaded indices
        self.indices = {}
        self.metadata = {}
    
    def _load_index(self, index_name: str):
        """Lazy load FAISS index and metadata."""
        if index_name in self.indices:
            return  # Already loaded
        
        index_path = self.index_dir / f"{index_name}.faiss"
        meta_path = self.index_dir / f"{index_name}_metadata.json"
        
        if not index_path.exists():
            logger.warning(f"Index not found: {index_path}")
            self.indices[index_name] = None
            self.metadata[index_name] = []
            return
        
        try:
            # Load FAISS index
            self.indices[index_name] = faiss.read_index(str(index_path))
            
            # Load metadata
            with open(meta_path) as f:
                self.metadata[index_name] = json.load(f)
            
            logger.debug(f"Loaded {index_name}: {self.indices[index_name].ntotal} vectors")
        except Exception as e:
            logger.error(f"Failed to load {index_name}: {e}")
            self.indices[index_name] = None
            self.metadata[index_name] = []
    
    def _search_index(self, index_name: str, query: str, top_k: int = 10) -> List[Dict]:
        """Generic search method for any index."""
        # Lazy load
        self._load_index(index_name)
        
        if not self.indices.get(index_name):
            logger.debug(f"Index {index_name} not available")
            return []
        
        # Embed query
        if not self.embedder:
            logger.error("No embedder provided")
            return []
        
        # Get embedding (handle both EmbeddingService and raw embedder)
        if hasattr(self.embedder, 'embeddings'):
            # This is EmbeddingService wrapper
            query_vector = self.embedder.embeddings.embed_query(query)
        elif hasattr(self.embedder, 'embed_query'):
            query_vector = self.embedder.embed_query(query)
        else:
            logger.error(f"Embedder has no embed_query method: {type(self.embedder)}")
            return []
        
        query_vector = np.array([query_vector], dtype=np.float32)
        
        # Search FAISS
        index = self.indices[index_name]
        distances, indices = index.search(query_vector, top_k)
        
        # Build results
        results = []
        metadata = self.metadata[index_name]
        
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < 0 or idx >= len(metadata):
                continue
            
            meta = metadata[idx]
            
            # Convert distance to similarity (0-1)
            # FAISS L2 distance: lower is better
            similarity = np.exp(-dist)
            
            results.append({
                'code': meta.get('code_name', 'unknown'),
                'score': similarity,
                'metadata': meta,
                'distance': float(dist),
                'rank': i + 1
            })
        
        return results
    
    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Search across all 4 sub-indices with weighted scoring.
        
        Args:
            query: Natural language query
            top_k: Number of results to return
            
        Returns:
            List of dicts with 'code', 'score', and details
        """
        # Search each sub-index
        regimes_results = self._search_physics_regimes(query, top_k=10)
        capabilities_results = self._search_solver_capabilities(query, top_k=10)
        lineage_results = self._search_code_lineage(query, top_k=10)
        cross_results = self._search_cross_cutting(query, top_k=10)
        
        # Combine scores by solver
        solver_scores = self._combine_scores(
            regimes_results,
            capabilities_results,
            lineage_results,
            cross_results
        )
        
        # Sort and return top_k
        ranked = sorted(
            solver_scores.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        
        return [
            {
                'code': code,
                'score': info['score'],
                'details': info
            }
            for code, info in ranked[:top_k]
        ]
    
    def _search_physics_regimes(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search physics_regimes index."""
        return self._search_index('physics_regimes', query, top_k)
    
    def _search_solver_capabilities(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search solver_capabilities index."""
        return self._search_index('solver_capabilities', query, top_k)
    
    def _search_code_lineage(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search code_lineage index."""
        return self._search_index('code_lineage', query, top_k)
    
    def _search_cross_cutting(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search cross_cutting_guidance index."""
        results = self._search_index('cross_cutting_guidance', query, top_k)
        # Cross-cutting may not have 'code_name', so add fallback
        for r in results:
            if 'code' not in r or not r['code'] or r['code'] == 'unknown':
                r['code'] = 'general'
        return results
    
    def _combine_scores(self, regimes, capabilities, lineage, cross) -> Dict:
        """
        Combine scores from all sub-indices using weights.
        
        Returns:
            Dict mapping solver_name -> {score, details}
        """
        solver_scores = {}
        
        # Aggregate scores by solver
        for result in regimes:
            code = result['code']
            if code not in solver_scores:
                solver_scores[code] = {'regimes': [], 'capabilities': [], 'lineage': [], 'cross': []}
            solver_scores[code]['regimes'].append(result['score'])
        
        for result in capabilities:
            code = result['code']
            if code not in solver_scores:
                solver_scores[code] = {'regimes': [], 'capabilities': [], 'lineage': [], 'cross': []}
            solver_scores[code]['capabilities'].append(result['score'])
        
        for result in lineage:
            code = result['code']
            if code not in solver_scores:
                solver_scores[code] = {'regimes': [], 'capabilities': [], 'lineage': [], 'cross': []}
            solver_scores[code]['lineage'].append(result['score'])
        
        for result in cross:
            code = result.get('code')
            if code and code != 'general':
                if code not in solver_scores:
                    solver_scores[code] = {'regimes': [], 'capabilities': [], 'lineage': [], 'cross': []}
                solver_scores[code]['cross'].append(result['score'])
        
        # Compute weighted scores
        final_scores = {}
        for code, scores in solver_scores.items():
            weighted = self._compute_weighted_score({
                'physics_regimes': max(scores['regimes']) if scores['regimes'] else 0.0,
                'solver_capabilities': max(scores['capabilities']) if scores['capabilities'] else 0.0,
                'code_lineage': max(scores['lineage']) if scores['lineage'] else 0.0,
                'cross_cutting_guidance': max(scores['cross']) if scores['cross'] else 0.0,
            })
            
            final_scores[code] = {
                'score': weighted,
                'breakdown': scores
            }
        
        return final_scores
    
    def _compute_weighted_score(self, scores: Dict[str, float]) -> float:
        """
        Compute weighted score using PRD weights.
        
        Args:
            scores: Dict with keys matching WEIGHTS
            
        Returns:
            Weighted sum (0-1)
        """
        total = 0.0
        for index_name, weight in self.WEIGHTS.items():
            score = scores.get(index_name, 0.0)
            total += score * weight
        
        return total

    def _count_index_entries(self) -> int:
        """Estimate corpus size from Level-0 sub-index populations.

        We use the maximum sub-index size instead of the sum because the same
        logical corpus is represented in multiple sub-indices with different
        facets/metadata.
        """
        max_count = 0
        for index_name in self.WEIGHTS:
            self._load_index(index_name)
            index = self.indices.get(index_name)
            if index is not None and hasattr(index, "ntotal"):
                max_count = max(max_count, int(index.ntotal))
        return max_count

    def evaluate_index_growth_accuracy_drift(
        self,
        baseline_accuracy: float,
        current_accuracy: float,
        index_count: Optional[int] = None,
    ) -> Dict:
        """
        Evaluate the 100+ index growth gate with a max 2% accuracy drop.

        Baseline/current values are expected as ratios in [0.0, 1.0].
        """
        for label, value in (
            ("baseline_accuracy", baseline_accuracy),
            ("current_accuracy", current_accuracy),
        ):
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{label} must be between 0.0 and 1.0")

        observed_index_count = int(index_count if index_count is not None else self._count_index_entries())
        accuracy_drop = max(0.0, float(baseline_accuracy) - float(current_accuracy))
        gate_active = observed_index_count >= self.INDEX_GROWTH_MIN_INDICES
        drift_within_target = accuracy_drop <= self.MAX_ACCURACY_DRIFT
        passed = (not gate_active) or drift_within_target

        return {
            "index_count": observed_index_count,
            "baseline_accuracy": float(baseline_accuracy),
            "current_accuracy": float(current_accuracy),
            "accuracy_drop": accuracy_drop,
            "max_allowed_accuracy_drop": self.MAX_ACCURACY_DRIFT,
            "min_index_growth_threshold": self.INDEX_GROWTH_MIN_INDICES,
            "gate_active": gate_active,
            "drift_within_target": drift_within_target,
            "passed": passed,
        }
