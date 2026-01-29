"""
Level 1 Searcher - Multi-Document Index Search

Searches across all documentation indices for a code.
Combines results from multiple doc types.

PRD: Section 5.3 (FR-3)

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import faiss
import numpy as np
import logging

logger = logging.getLogger(__name__)

class Level1Searcher:
    """Multi-document index searcher."""
    
    def __init__(self, code: str, index_dir: Path, embedder=None):
        """
        Initialize searcher.
        
        Args:
            code: Code name (e.g., 'PeleC', 'PeleLMeX', 'ERF', 'WarpX', 'incflo')
            index_dir: Directory containing Level 1 indices
            embedder: Embedding service (for query embedding)
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
        """Discover all doc indices for this code."""
        code_lower = self.code.lower()
        pattern = f"{code_lower}_doc_*.faiss"
        
        indices = {}
        for index_file in self.index_dir.glob(pattern):
            # Extract index type from filename
            # e.g., pelec_doc_solver_readme.faiss -> solver_readme
            name = index_file.stem
            index_type = name.replace(f"{code_lower}_doc_", "")
            indices[index_type] = index_file
        
        logger.debug(f"Discovered {len(indices)} doc indices for {self.code}")
        return indices
    
    def _load_index(self, index_type: str):
        """Lazy load FAISS index and metadata."""
        if index_type in self.indices:
            return  # Already loaded
        
        if index_type not in self.available_indices:
            logger.warning(f"Index type not available: {index_type}")
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
    
    def search_all_docs(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search across all documentation indices.
        
        Args:
            query: Natural language query
            top_k: Number of results per index
            
        Returns:
            Combined and ranked results
        """
        all_results = []
        
        # Search each available index
        for index_type in self.available_indices.keys():
            results = self._search_single_index(
                index_type,
                query,
                top_k
            )
            
            # Add index type to results
            for result in results:
                result['doc_type'] = index_type
            
            all_results.extend(results)
        
        # Sort by score
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return all_results[:top_k * 2]  # Return more for diversity
    
    def _search_single_index(self, index_type: str, query: str,
                             top_k: int = 5) -> List[Dict]:
        """Search a single index."""
        # Lazy load
        self._load_index(index_type)
        
        if not self.indices.get(index_type):
            logger.debug(f"Index {index_type} not available")
            return []
        
        # Embed query
        if not self.embedder:
            logger.error("No embedder provided")
            return []
        
        # Get embedding (handle both EmbeddingService and raw embedder)
        if hasattr(self.embedder, 'embeddings'):
            query_vector = self.embedder.embeddings.embed_query(query)
        elif hasattr(self.embedder, 'embed_query'):
            query_vector = self.embedder.embed_query(query)
        else:
            logger.error(f"Embedder has no embed_query method")
            return []
        
        query_vector = np.array([query_vector], dtype=np.float32)
        
        # Search FAISS
        index = self.indices[index_type]
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
                'score': similarity,
                'metadata': meta,
                'distance': float(dist),
                'rank': i + 1,
                'source': index_type
            })
        
        return results
