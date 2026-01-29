"""
Level 2 Searcher - Weighted Case Metadata Search

Searches 7 sub-indices with weighted scoring per PRD 5.4.

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import faiss
import numpy as np
import logging

logger = logging.getLogger(__name__)

class Level2Searcher:
    """Multi-index case metadata searcher."""
    
    # PRD Section 5.4: Exact weights
    WEIGHTS = {
        'physics_parameters': 0.30,
        'grid_specifications': 0.20,
        'development_activity': 0.10,
        'configuration_complexity': 0.10,
        'path_hierarchy': 0.15,
        'domain_models': 0.10,
        'resource_requirements': 0.05,
    }
    
    def __init__(self, code: str, index_dir: Path, embedder=None):
        """
        Initialize searcher.
        
        Args:
            code: Code name (e.g., 'PeleC', 'PeleLMeX', 'ERF', 'WarpX', 'incflo')
            index_dir: Directory containing Level 2 indices
            embedder: Embedding service
        """
        self.code = code
        self.index_dir = index_dir
        self.embedder = embedder
        
        # Lazy-loaded indices
        self.indices = {}
        self.metadata = {}
        
        # Discover available indices
        self.available_indices = self._discover_indices()
    
    def _discover_indices(self) -> Dict[str, Path]:
        """Discover all case indices for this code."""
        code_lower = self.code.lower()
        pattern = f"{code_lower}_case_*.faiss"
        
        indices = {}
        for index_file in self.index_dir.glob(pattern):
            # Extract index type
            # e.g., pelec_case_physics_parameters.faiss -> physics_parameters
            name = index_file.stem
            index_type = name.replace(f"{code_lower}_case_", "")
            indices[index_type] = index_file
        
        logger.debug(f"Discovered {len(indices)} case indices for {self.code}")
        return indices
    
    def _load_index(self, index_type: str):
        """Lazy load FAISS index and metadata."""
        if index_type in self.indices:
            return  # Already loaded
        
        if index_type not in self.available_indices:
            logger.debug(f"Index type not available: {index_type}")
            self.indices[index_type] = None
            self.metadata[index_type] = []
            return
        
        index_path = self.available_indices[index_type]
        meta_path = index_path.parent / f"{index_path.stem}_metadata.json"
        
        try:
            # Load FAISS index
            self.indices[index_type] = faiss.read_index(str(index_path))
            
            # Load metadata
            with open(meta_path) as f:
                self.metadata[index_type] = json.load(f)
            
            logger.debug(f"Loaded {index_type}: {self.indices[index_type].ntotal} vectors")
        except Exception as e:
            logger.error(f"Failed to load {index_type}: {e}")
            self.indices[index_type] = None
            self.metadata[index_type] = []
    
    def _search_index(self, index_type: str, query: str, top_k: int = 10) -> List[Dict]:
        """Search a single case index."""
        # Lazy load
        self._load_index(index_type)
        
        if not self.indices.get(index_type):
            return []
        
        # Embed query
        if not self.embedder:
            logger.error("No embedder provided")
            return []
        
        # Get embedding
        if hasattr(self.embedder, 'embeddings'):
            query_vector = self.embedder.embeddings.embed_query(query)
        elif hasattr(self.embedder, 'embed_query'):
            query_vector = self.embedder.embed_query(query)
        else:
            logger.error(f"Embedder has no embed_query method")
            return []
        
        query_vector = np.array([query_vector], dtype=np.float32)

        # Get the FAISS index first
        index = self.indices[index_type]

        # Then check dimensions
        if index.d != query_vector.shape[1]:
            logger.warning(f"Skipping {index_type}: dimension mismatch (index={index.d}, query={query_vector.shape[1]})")
            return []

        # Search FAISS
        distances, indices = index.search(query_vector, top_k)
        
        # Build results
        results = []
        metadata = self.metadata[index_type]
        
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < 0 or idx >= len(metadata):
                continue
            
            meta = metadata[idx]
            
            # Convert distance to similarity
            similarity = np.exp(-dist)
            
            results.append({
                'case': meta.get('repo_path', meta.get('case_name', 'unknown')),
                'score': similarity,
                'metadata': meta,
                'distance': float(dist),
                'rank': i + 1
            })
        
        return results
    
    def search_all_cases(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search across all case metadata indices with weighted scoring.
        
        Args:
            query: Natural language query
            top_k: Number of results
            
        Returns:
            Combined and ranked results
        """
        # Search each index
        index_results = {}
        for index_type in self.available_indices.keys():
            results = self._search_index(index_type, query, top_k=20)
            index_results[index_type] = results
        
        # Combine scores by case
        case_scores = self._combine_scores(index_results)
        
        # Sort and return top_k
        ranked = sorted(
            case_scores.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        
        # Filter out submodule cases
        filtered_ranked = [
            (case, info) for case, info in ranked
            if "Submodules" not in case and "submodules" not in case
        ]
        
        return [
            {
                'case': case,
                'score': info['score'],
                'metadata': info.get('metadata', {}),
                'breakdown': info.get('breakdown', {})
            }
            for case, info in filtered_ranked[:top_k]
        ]
    
    def _combine_scores(self, index_results: Dict[str, List[Dict]]) -> Dict:
        """
        Combine scores from all indices using weights.
        
        Returns:
            Dict mapping case_path -> {score, metadata, breakdown}
        """
        case_scores = {}
        
        # Aggregate scores by case
        for index_type, results in index_results.items():
            for result in results:
                case = result['case']
                
                if case not in case_scores:
                    case_scores[case] = {
                        'scores': {},
                        'metadata': result.get('metadata', {})
                    }
                
                # Store best score for this index
                if index_type not in case_scores[case]['scores']:
                    case_scores[case]['scores'][index_type] = result['score']
                else:
                    case_scores[case]['scores'][index_type] = max(
                        case_scores[case]['scores'][index_type],
                        result['score']
                    )
        
        # Compute weighted scores
        final_scores = {}
        for case, data in case_scores.items():
            weighted = self._compute_weighted_score(data['scores'])
            
            final_scores[case] = {
                'score': weighted,
                'metadata': data['metadata'],
                'breakdown': data['scores']
            }
        
        return final_scores
    
    def _compute_weighted_score(self, scores: Dict[str, float]) -> float:
        """Compute weighted score using PRD weights."""
        total = 0.0
        for index_name, weight in self.WEIGHTS.items():
            score = scores.get(index_name, 0.0)
            total += score * weight
        
        return total
